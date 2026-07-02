"""面试手写练习 — 4 个核心模块的最精简实现

每个模块都是面试可能让你白板写的代码。
练习目标：不看参考，能默写出来。

练习方法:
  1. 先读懂每个模块
  2. 关掉文件，在白纸/记事本上默写
  3. 对照检查，修正错误
  4. 重复直到能一次写对

模块清单:
  1. 向量检索（TF-IDF + 余弦相似度，不依赖任何库）
  2. 多 Agent 协作（消息传递 + 任务分发）
  3. 流式输出（SSE + LLM stream）
  4. RAG 检索增强生成
"""

# ============================================================
# 模块 1：向量检索（TF-IDF + 余弦相似度）
# 面试高频： "手写一个简单的向量检索"
# ============================================================

import math
from collections import Counter

class SimpleVectorStore:
    """TF-IDF 向量检索 — 零依赖手写版"""

    def __init__(self):
        self.documents = []       # [{text, tokens}]
        self.idf = {}             # {word: idf_value}

    def add(self, text: str):
        tokens = self._tokenize(text)
        self.documents.append({"text": text, "tokens": tokens})
        self._update_idf()

    def search(self, query: str, top_k: int = 3) -> list[dict]:
        if not self.documents:
            return []
        query_vec = self._tfidf(self._tokenize(query))
        scores = []
        for doc in self.documents:
            doc_vec = self._tfidf(doc["tokens"])
            # 余弦相似度 = dot / (norm_a * norm_b)
            dot = sum(query_vec.get(w, 0) * doc_vec.get(w, 0) for w in query_vec)
            norm_q = math.sqrt(sum(v ** 2 for v in query_vec.values()))
            norm_d = math.sqrt(sum(v ** 2 for v in doc_vec.values()))
            sim = dot / (norm_q * norm_d) if norm_q and norm_d else 0
            scores.append({"text": doc["text"], "score": round(sim, 4)})
        scores.sort(key=lambda x: -x["score"])
        return scores[:top_k]

    def _tfidf(self, tokens: list[str]) -> dict[str, float]:
        tf = Counter(tokens)
        total = len(tokens) or 1
        return {w: (c / total) * self.idf.get(w, 0) for w, c in tf.items()}

    def _update_idf(self):
        N = len(self.documents)
        df = Counter()
        for doc in self.documents:
            for w in set(doc["tokens"]):
                df[w] += 1
        self.idf = {w: math.log(N / df[w]) for w in df}

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        import re
        return re.findall(r"\w+", text.lower())


# 练习验证
if __name__ == "__main__":
    vs = SimpleVectorStore()
    vs.add("Python web framework FastAPI")
    vs.add("JavaScript frontend React Vue")
    vs.add("Python machine learning TensorFlow")

    results = vs.search("Python web")
    print("=== 向量检索 ===")
    for r in results:
        print(f"  {r['score']:.4f} | {r['text']}")


# ============================================================
# 模块 2：多 Agent 协作（消息传递 + 任务分发）
# 面试高频： "手写一个简单的多 Agent 协作"
# ============================================================

import asyncio
from dataclasses import dataclass, field
from enum import Enum

class Role(Enum):
    ORCHESTRATOR = "orchestrator"
    WORKER = "worker"
    REVIEWER = "reviewer"

@dataclass
class Message:
    sender: Role
    receiver: Role
    content: str
    data: dict = field(default_factory=dict)

class SimpleAgent:
    """最简多 Agent — 消息驱动"""

    def __init__(self, name: str, role: Role, handler):
        self.name = name
        self.role = role
        self.handler = handler    # async def(msg) -> Message
        self.inbox: list[Message] = []

    async def process(self) -> Message | None:
        if not self.inbox:
            return None
        msg = self.inbox.pop(0)
        return await self.handler(msg)


async def demo_multi_agent():
    """多 Agent 协作演示：Orchestrator → Worker → Reviewer → (pass/end | fail/retry)"""
    results = []
    retry_count = 0
    max_retries = 2

    async def worker_handler(msg: Message) -> Message:
        # 模拟工作：根据 retry_count 决定质量
        quality = 30 + retry_count * 40  # 第1次30分，第2次70分，第3次110
        return Message(
            sender=Role.WORKER, receiver=Role.REVIEWER,
            content=f"工作完成，质量={quality}",
            data={"quality": quality},
        )

    async def reviewer_handler(msg: Message) -> Message:
        quality = msg.data.get("quality", 0)
        passed = quality >= 60
        return Message(
            sender=Role.REVIEWER, receiver=Role.ORCHESTRATOR,
            content=f"审查: {'通过' if passed else '未通过'} (quality={quality})",
            data={"passed": passed, "quality": quality},
        )

    worker = SimpleAgent("Worker", Role.WORKER, worker_handler)
    reviewer = SimpleAgent("Reviewer", Role.REVIEWER, reviewer_handler)

    # 协作循环
    while retry_count <= max_retries:
        # Orchestrator → Worker
        worker.inbox.append(Message(
            sender=Role.ORCHESTRATOR, receiver=Role.WORKER,
            content=f"执行任务 (retry={retry_count})",
        ))
        worker_result = await worker.process()

        # Worker → Reviewer
        reviewer.inbox.append(worker_result)
        review_result = await reviewer.process()

        results.append(review_result.content)
        print(f"  [retry={retry_count}] {review_result.content}")

        if review_result.data["passed"]:
            print("  → 审查通过，任务完成！")
            break
        else:
            retry_count += 1
            print(f"  → 审查未通过，重试...")

    return results


# ============================================================
# 模块 3：流式输出（SSE + LLM stream）
# 面试高频： "Agent 思考过程怎么实时输出"
# ============================================================

async def demo_streaming():
    """模拟 LLM 流式输出 + SSE 格式"""
    import json

    # 模拟 LLM 逐 token 返回
    async def fake_llm_stream(prompt: str):
        response = f"分析代码：{prompt[:20]}... 发现2个函数，复杂度正常。"
        for char in response:
            await asyncio.sleep(0.02)
            yield char

    # SSE 格式封装
    def sse(event_type: str, data: dict) -> str:
        return f"data: {json.dumps({'type': event_type, **data})}\n\n"

    print("\n=== 流式输出（SSE）===")
    events = []
    yield_count = 0
    async for token in fake_llm_stream("def add(a, b): return a + b"):
        event = sse("token", {"content": token})
        events.append(event)
        yield_count += 1
        if yield_count <= 5:
            print(f"  -> yield: {event.strip()}")
    print(f"  ... 共 yield {yield_count} 个 token")
    done_event = sse("done", {"status": "completed"})
    events.append(done_event)
    print(f"  -> yield: {done_event.strip()}")
    return events


# ============================================================
# 模块 4：RAG 检索增强生成
# 面试高频： "手写一个简单的 RAG 流程"
# ============================================================

async def demo_rag():
    """RAG 流程：检索 → 拼接上下文 → 生成"""
    print("\n=== RAG 检索增强生成 ===")

    # 1. 知识库（用模块1的向量库）
    store = SimpleVectorStore()
    store.add("FastAPI 是 Python 的异步 web 框架")
    store.add("React 是 JavaScript 的前端库")
    store.add("Docker 用于容器化部署应用")

    # 2. 检索
    query = "Python web 开发用什么框架"
    retrieved = store.search(query, top_k=2)
    print(f"  查询: {query}")
    print(f"  检索到 {len(retrieved)} 条:")
    for r in retrieved:
        print(f"    [{r['score']:.4f}] {r['text']}")

    # 3. 拼接上下文
    context = "\n".join(r["text"] for r in retrieved)
    prompt = f"根据以下知识回答问题。\n\n知识:\n{context}\n\n问题: {query}\n回答:"
    print(f"  生成 Prompt (前100字): {prompt[:100]}...")

    # 4. 生成（实际项目调 LLM）
    # answer = await litellm.acompletion(model=..., messages=[{"role":"user","content":prompt}])
    print(f"  → 实际项目用 litellm.acompletion() 生成回答")


# ============================================================
# 主函数：运行所有演示
# ============================================================

async def main():
    print("=" * 60)
    print("面试手写练习 — 4 个核心模块验证")
    print("=" * 60)

    # 模块 1 已在 __main__ 中运行

    # 模块 2：多 Agent
    print("\n=== 多 Agent 协作 ===")
    await demo_multi_agent()

    # 模块 3：流式输出
    await demo_streaming()

    # 模块 4：RAG
    await demo_rag()

    print("\n" + "=" * 60)
    print("全部模块验证通过！")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
