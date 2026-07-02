import sys, json, logging, math, re
from collections import Counter
from typing import Optional

logger = logging.getLogger("testforge")

try:
    import chromadb
    from chromadb.config import Settings as ChromaSettings
    _HAS_CHROMADB = True
except ImportError:
    _HAS_CHROMADB = False

try:
    from sentence_transformers import SentenceTransformer
    _HAS_ST = True
except ImportError:
    _HAS_ST = False

try:
    import litellm
    _HAS_LITELLM = True
except ImportError:
    _HAS_LITELLM = False


class EmbeddingModel:
    def __init__(self):
        self._model = None
        self._initialized = False
        self._backend = "none"

    def _init(self):
        if self._initialized:
            return
        self._initialized = True
        if _HAS_ST:
            try:
                self._model = SentenceTransformer("BAAI/bge-small-zh-v1.5")
                self._backend = "sentence-transformers"
                logger.info("Embedding: sentence-transformers loaded")
                return
            except Exception as e:
                logger.warning("sentence-transformers failed: %s", e)
        from backend.config import settings
        if _HAS_LITELLM and settings.llm_api_key:
            self._backend = "litellm"
            logger.info("Embedding: LiteLLM API")
            return
        self._backend = "none"
        logger.info("Embedding unavailable, TF-IDF fallback")

    def embed(self, texts):
        self._init()
        if self._backend == "sentence-transformers" and self._model:
            embeddings = self._model.encode(texts, normalize_embeddings=True)
            return embeddings.tolist()
        if self._backend == "litellm":
            from backend.config import settings
            try:
                response = litellm.embedding(
                    model=settings.llm_provider + "/text-embedding-3-small",
                    input=texts,
                    api_key=settings.llm_api_key,
                    api_base=settings.llm_api_base,
                )
                return [d["embedding"] for d in response.data]
            except Exception as e:
                logger.warning("LiteLLM embedding failed: %s", e)
                return []
        return []

    def embed_one(self, text):
        result = self.embed([text])
        return result[0] if result else []

    @property
    def backend(self):
        self._init()
        return self._backend


embedding_model = EmbeddingModel()


class ChromaVectorStore:
    def __init__(self, collection_name="test_cases", persist_dir="./chroma_db"):
        self.collection_name = collection_name
        self.persist_dir = persist_dir
        self._client = None
        self._collection = None

    def _init(self):
        if self._client:
            return
        self._client = chromadb.PersistentClient(
            path=self.persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info("ChromaDB initialized: %s (%d)", self.persist_dir, self._collection.count())

    def add(self, test_case):
        self.add_batch([test_case])

    def add_batch(self, test_cases):
        if not test_cases:
            return
        self._init()
        texts = [self._tc_to_text(tc) for tc in test_cases]
        ids = [tc.get("id", "tc_%d" % i) for i, tc in enumerate(test_cases)]
        metadatas = []
        for tc in test_cases:
            metadatas.append({
                "name": tc.get("name", ""),
                "type": tc.get("type", "functional"),
                "created_by": tc.get("created_by", "manual"),
                "tags": ",".join(tc.get("tags", [])),
            })
        embeddings = embedding_model.embed(texts)
        if embeddings and len(embeddings) == len(texts):
            self._collection.upsert(ids=ids, documents=texts, embeddings=embeddings, metadatas=metadatas)
        else:
            self._collection.upsert(ids=ids, documents=texts, metadatas=metadatas)
        logger.info("ChromaDB added %d cases (total %d)", len(test_cases), self._collection.count())

    def search(self, query, top_k=3, where=None):
        self._init()
        query_embedding = embedding_model.embed_one(query)
        kwargs = {"query_embeddings": [query_embedding], "n_results": top_k}
        if where:
            kwargs["where"] = where
        results = self._collection.query(**kwargs)
        output = []
        if results and results.get("ids") and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                output.append({
                    "id": doc_id,
                    "text": results["documents"][0][i] if results.get("documents") else "",
                    "metadata": results["metadatas"][0][i] if results.get("metadatas") else {},
                    "distance": results["distances"][0][i] if results.get("distances") else 0,
                })
        return output

    def size(self):
        self._init()
        return self._collection.count()

    def clear(self):
        self._init()
        self._collection.delete(where={})
        logger.info("ChromaDB cleared")

    @staticmethod
    def _tc_to_text(tc):
        desc = tc.get("description") or tc.get("desc") or ""
        parts = [
            "Name: " + tc.get("name", ""),
            "Type: " + tc.get("type", "functional"),
            "Description: " + desc,
        ]
        steps = tc.get("steps", [])
        for s in steps:
            s_text = "Step: " + (s.get("description") or s.get("desc") or "")
            if s.get("query"):
                s_text += " | Query: " + s["query"]
            parts.append(s_text)
        return "\n".join(parts)


class TestCaseVectorStore:
    def __init__(self):
        self._store = {}
        self._idf = Counter()

    def add(self, tc):
        self.add_batch([tc])

    def add_batch(self, test_cases):
        for tc in test_cases:
            tc_id = tc.get("id", "tfidf_%d" % len(self._store))
            self._store[tc_id] = tc
            text = ChromaVectorStore._tc_to_text(tc)
            words = set(re.findall(r"\w+", text.lower()))
            for w in words:
                self._idf[w] += 1
        logger.info("TF-IDF added %d cases (total %d)", len(test_cases), len(self._store))

    def search(self, query, top_k=3):
        query_words = set(re.findall(r"\w+", query.lower()))
        total_docs = max(len(self._store), 1)
        scores = []
        for tc_id, tc in self._store.items():
            text = ChromaVectorStore._tc_to_text(tc)
            text_words = set(re.findall(r"\w+", text.lower()))
            common = query_words & text_words
            if not common:
                continue
            score = sum(math.log(total_docs / max(self._idf.get(w, 1), 1)) for w in common)
            scores.append({"id": tc_id, "tc": tc, "score": score})
        scores.sort(key=lambda x: x["score"], reverse=True)
        return scores[:top_k]

    def size(self):
        return len(self._store)

    def clear(self):
        self._store.clear()
        self._idf.clear()
        logger.info("TF-IDF cleared")


class UnifiedVectorStore:
    def __init__(self):
        self._chroma = None
        self._tfidf = TestCaseVectorStore()
        self._backend = "tfidf"
        if _HAS_CHROMADB:
            try:
                self._chroma = ChromaVectorStore()
                self._backend = "chromadb"
                logger.info("RAG backend: ChromaDB (lazy init)")
            except Exception as e:
                logger.warning("ChromaDB init failed, fallback TF-IDF: %s", e)
                self._backend = "tfidf"
        else:
            logger.info("RAG backend: TF-IDF (ChromaDB not installed)")

    def add(self, test_case):
        if self._backend == "chromadb" and self._chroma:
            self._chroma.add(test_case)
        self._tfidf.add(test_case)

    def add_batch(self, test_cases):
        if self._backend == "chromadb" and self._chroma:
            self._chroma.add_batch(test_cases)
        self._tfidf.add_batch(test_cases)

    def search(self, query, top_k=3, where=None):
        if self._backend == "chromadb" and self._chroma:
            return self._chroma.search(query, top_k, where)
        return self._tfidf.search(query, top_k)

    def size(self):
        if self._backend == "chromadb" and self._chroma:
            return self._chroma.size()
        return self._tfidf.size()

    def clear(self):
        if self._backend == "chromadb" and self._chroma:
            self._chroma.clear()
        self._tfidf.clear()

    @property
    def backend_name(self):
        return self._backend

    @property
    def embedding_backend(self):
        try:
            return embedding_model.backend
        except Exception:
            return "lazy"

    def stats(self):
        return {
            "vector_store_backend": self._backend,
            "embedding_backend": "lazy",
            "size": self.size(),
            "chromadb_available": _HAS_CHROMADB,
            "sentence_transformers_available": _HAS_ST,
        }


vector_store = UnifiedVectorStore()


async def generate_with_rag(source_code, language="python", context="", top_k=3):
    similar = vector_store.search(source_code, top_k=top_k)
    rag_context = ""
    if similar:
        rag_context = "Similar test cases:\n"
        for s in similar:
            tc = s.get("tc", {})
            name = tc.get("name", "")
            desc = tc.get("description") or tc.get("desc") or ""
            rag_context += "- " + name + ": " + desc[:200] + "\n"
    return {
        "rag_context": rag_context,
        "similar_cases": [
            {"name": s.get("tc", {}).get("name", ""), "score": s.get("score", 0)}
            for s in similar
        ],
        "vector_store_size": vector_store.size(),
        "vector_store_backend": vector_store.backend_name,
        "embedding_backend": vector_store.embedding_backend,
    }


def load_from_database():
    import asyncio
    from backend.models.store import list_tests

    async def _load():
        tests = await list_tests()
        if tests:
            cases_data = [tc.model_dump() for tc in tests]
            vector_store.add_batch(cases_data)
        return len(tests)

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(_load())
        else:
            loop.run_until_complete(_load())
    except RuntimeError:
        asyncio.run(_load())
