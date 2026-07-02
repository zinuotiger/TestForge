#!/usr/bin/env python3



import os, sys, json, hashlib, time, sqlite3, threading, asyncio, random, logging



from typing import Optional



from dataclasses import dataclass



from enum import Enum







logger = logging.getLogger("testforge")







class EvolutionEventType(str, Enum):



    EXECUTION_COMPLETE = "execution_complete"



    HEAL_SUCCESS = "heal_success"



    HEAL_FAILURE = "heal_failure"



    FLAKY_DETECTED = "flaky_detected"



    STRATEGY_CALLED = "strategy_called"



    KNOWLEDGE_EXTRACTED = "knowledge_extracted"



    CROSS_PROJECT_MATCH = "cross_project_match"



    HEALTH_DEGRADED = "health_degraded"



    HEALTH_IMPROVED = "health_improved"







class StrategyType(str, Enum):



    TEMPLATE = "template"



    PROPERTY = "property"



    AI = "ai"



    SEARCH = "search"



    TRAFFIC = "traffic"







@dataclass



class StrategyPerformance:



    name: str



    total_calls: int = 0



    total_cases: int = 0



    successful_cases: int = 0



    failed_cases: int = 0



    avg_duration_ms: float = 0.0



    current_weight: float = 1.0



    last_updated: float = 0.0



    @property



    def success_rate(self) -> float:



        total = self.successful_cases + self.failed_cases



        return self.successful_cases / max(total, 1)



    @property



    def cost_per_case(self) -> float:



        if self.name == "template": return 0.0



        if self.name == "property": return 0.0



        if self.name == "ai": return 0.05



        return 0.01







@dataclass



class KnowledgeEntry:



    id: int



    category: str



    source_type: str



    domain: str



    title: str



    content: dict



    score: float



    use_count: int



    created_at: float



    project_hash: str = ""







INITIAL_STRATEGY_WEIGHTS = {"template": 2.0, "property": 1.5, "ai": 1.0, "search": 0.5, "traffic": 0.5}



STRATEGY_COSTS = {"template": 0.0, "property": 0.0, "ai": 0.5, "search": 0.1, "traffic": 0.1}







def _get_db_path():



    p = os.path.abspath(__file__)



    for _ in range(3):



        p = os.path.dirname(p)



    return os.path.join(p, "testforge.db")



DB_PATH = _get_db_path()







class EvolutionDB:



    def __init__(self, db_path: str = ""):



        self._db_path = db_path or DB_PATH



        self._local = threading.local()



        self._initialized = False



    @property



    def _conn(self):



        if not hasattr(self._local, "conn") or self._local.conn is None:



            self._local.conn = sqlite3.connect(self._db_path, check_same_thread=False)



            self._local.conn.row_factory = sqlite3.Row



            self._local.conn.execute("PRAGMA journal_mode=WAL")



        return self._local.conn



    def _ensure_init(self):



        if not self._initialized:



            self._init_tables()



            self._initialized = True



    def _init_tables(self):



        c = self._conn



        c.executescript("""



            CREATE TABLE IF NOT EXISTS evolution_events (



                id INTEGER PRIMARY KEY AUTOINCREMENT,



                project_id TEXT DEFAULT 'default',



                event_type TEXT NOT NULL,



                data TEXT NOT NULL,



                created_at REAL NOT NULL



            );



            CREATE INDEX IF NOT EXISTS idx_ev_events_type ON evolution_events(event_type);



            CREATE INDEX IF NOT EXISTS idx_ev_events_project ON evolution_events(project_id);



            CREATE INDEX IF NOT EXISTS idx_ev_events_created ON evolution_events(created_at);



            CREATE TABLE IF NOT EXISTS evolution_knowledge (



                id INTEGER PRIMARY KEY AUTOINCREMENT,



                category TEXT NOT NULL,



                source_type TEXT NOT NULL,



                domain TEXT DEFAULT '',



                title TEXT NOT NULL,



                content TEXT NOT NULL,



                score REAL DEFAULT 0.5,



                use_count INTEGER DEFAULT 0,



                created_at REAL NOT NULL,



                project_hash TEXT DEFAULT ''



            );



            CREATE INDEX IF NOT EXISTS idx_ev_knowledge_category ON evolution_knowledge(category);



            CREATE INDEX IF NOT EXISTS idx_ev_knowledge_source ON evolution_knowledge(source_type);



            CREATE TABLE IF NOT EXISTS evolution_strategies (



                name TEXT PRIMARY KEY,



                total_calls INTEGER DEFAULT 0,



                total_cases INTEGER DEFAULT 0,



                successful_cases INTEGER DEFAULT 0,



                failed_cases INTEGER DEFAULT 0,



                avg_duration_ms REAL DEFAULT 0.0,



                current_weight REAL DEFAULT 1.0,



                last_updated REAL NOT NULL



            );



            CREATE TABLE IF NOT EXISTS evolution_project_patterns (



                project_id TEXT PRIMARY KEY,



                project_hash TEXT NOT NULL,



                patterns TEXT NOT NULL,



                created_at REAL NOT NULL



            );



        """)



        self._conn.commit()



    def log_event(



        self, event_type: str, data: dict, project_id: str = "default"):



        c = self._conn



        c.execute("INSERT INTO evolution_events (project_id, event_type, data, created_at) VALUES (?, ?, ?, ?)",



                  (project_id, event_type, json.dumps(data, ensure_ascii=False, default=str), time.time()))



        self._conn.commit()



    def get_recent_events(



        self, event_type: str = "", project_id: str = "", limit: int = 50) -> list:



        c = self._conn



        clauses = []; params = []



        if event_type: clauses.append("event_type = ?"); params.append(event_type)



        if project_id: clauses.append("project_id = ?"); params.append(project_id)



        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""



        cur = c.execute(f"SELECT * FROM evolution_events {where} ORDER BY created_at DESC LIMIT ?", [*params, limit])



        return [dict(row) for row in cur.fetchall()]



    def get_event_count(



        self, event_type: str = "", project_id: str = "") -> int:



        c = self._conn



        clauses = []; params = []



        if event_type: clauses.append("event_type = ?"); params.append(event_type)



        if project_id: clauses.append("project_id = ?"); params.append(project_id)



        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""



        cur = c.execute(f"SELECT COUNT(*) FROM evolution_events {where}", params)



        return cur.fetchone()[0]



    def upsert_knowledge(



        self, category: str, source_type: str, domain: str, title: str, content: dict, project_hash: str = "") -> int:



        c = self._conn



        content_json = json.dumps(content, ensure_ascii=False, default=str)



        now = time.time()



        existing = c.execute("SELECT id, use_count FROM evolution_knowledge WHERE title = ? AND category = ?", (title, category)).fetchone()



        if existing:



            c.execute("UPDATE evolution_knowledge SET content=?, use_count=?, created_at=? WHERE id=?",



                      (content_json, existing["use_count"] + 1, now, existing["id"]))



            self._conn.commit()



            return existing["id"]



        else:



            cur = c.execute("INSERT INTO evolution_knowledge (category, source_type, domain, title, content, score, use_count, created_at, project_hash) VALUES (?, ?, ?, ?, ?, 0.5, 0, ?, ?)",



                      (category, source_type, domain, title, content_json, now, project_hash))



            self._conn.commit()



            return cur.lastrowid



    def search_knowledge(



        self, query: str = "", category: str = "", limit: int = 20) -> list:



        c = self._conn



        clauses = []; params = []



        if query: clauses.append("(title LIKE ? OR content LIKE ?)"); q = f"%{query}%"; params.extend([q, q])



        if category: clauses.append("category = ?"); params.append(category)



        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""



        cur = c.execute(f"SELECT * FROM evolution_knowledge {where} ORDER BY score DESC, use_count DESC LIMIT ?", [*params, limit])



        results = []



        for row in cur.fetchall():



            r = dict(row)



            try: r["content"] = json.loads(r["content"])



            except (json.JSONDecodeError, TypeError): pass



            results.append(r)



        return results



    def knowledge_count(



        self) -> int:



        return self._conn.execute("SELECT COUNT(*) FROM evolution_knowledge").fetchone()[0]



    def get_strategy_performance(



        self, name: str) -> Optional[StrategyPerformance]:



        row = self._conn.execute("SELECT * FROM evolution_strategies WHERE name = ?", (name,)).fetchone()



        if not row: return None



        return StrategyPerformance(name=row["name"], total_calls=row["total_calls"], total_cases=row["total_cases"],



                                   successful_cases=row["successful_cases"], failed_cases=row["failed_cases"],



                                   avg_duration_ms=row["avg_duration_ms"], current_weight=row["current_weight"],



                                   last_updated=row["last_updated"])



    def get_all_strategies(



        self) -> list:



        rows = self._conn.execute("SELECT * FROM evolution_strategies ORDER BY name").fetchall()



        return [StrategyPerformance(name=r["name"], total_calls=r["total_calls"], total_cases=r["total_cases"],



                                    successful_cases=r["successful_cases"], failed_cases=r["failed_cases"],



                                    avg_duration_ms=r["avg_duration_ms"], current_weight=r["current_weight"],



                                    last_updated=r["last_updated"]) for r in rows]



    def upsert_strategy(



        self, name: str, total_calls: int = 0, total_cases: int = 0,



                        successful_cases: int = 0, failed_cases: int = 0,



                        avg_duration_ms: float = 0.0, current_weight: float = 1.0):



        c = self._conn; now = time.time()



        existing = c.execute("SELECT name FROM evolution_strategies WHERE name = ?", (name,)).fetchone()



        if existing:



            c.execute("UPDATE evolution_strategies SET total_calls=?, total_cases=?, successful_cases=?, failed_cases=?, avg_duration_ms=?, current_weight=?, last_updated=? WHERE name=?",



                      (total_calls, total_cases, successful_cases, failed_cases, avg_duration_ms, current_weight, now, name))



        else:



            c.execute("INSERT INTO evolution_strategies (name, total_calls, total_cases, successful_cases, failed_cases, avg_duration_ms, current_weight, last_updated) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",



                      (name, total_calls, total_cases, successful_cases, failed_cases, avg_duration_ms, current_weight, now))



        self._conn.commit()



    def save_project_pattern(



        self, project_id: str, project_hash: str, patterns: dict):



        c = self._conn; now = time.time()



        c.execute("INSERT OR REPLACE INTO evolution_project_patterns (project_id, project_hash, patterns, created_at) VALUES (?, ?, ?, ?)",



                  (project_id, project_hash, json.dumps(patterns, ensure_ascii=False, default=str), now))



        self._conn.commit()



    def get_all_project_patterns(



        self) -> list:



        rows = self._conn.execute("SELECT project_id, project_hash, patterns FROM evolution_project_patterns").fetchall()



        return [dict(row) for row in rows]



    def get_knowledge_by_project_hash(



        self, project_hash: str, limit: int = 20) -> list:



        rows = self._conn.execute("SELECT * FROM evolution_knowledge WHERE project_hash = ? ORDER BY score DESC LIMIT ?", (project_hash, limit)).fetchall()



        results = []



        for row in rows:



            r = dict(row)



            try: r["content"] = json.loads(r["content"])



            except (json.JSONDecodeError, TypeError): pass



            results.append(r)



        return results







class KnowledgeBuilder:



    def __init__(self, db: EvolutionDB): self.db = db



    def from_execution_results(self, results: list, project_hash: str = ""):



        strategy_results = {}



        for r in results:



            s = r.get("strategy", "unknown")



            if s not in strategy_results: strategy_results[s] = {"passed": 0, "failed": 0}



            if r.get("passed"): strategy_results[s]["passed"] += 1



            else: strategy_results[s]["failed"] += 1



        for strategy, counts in strategy_results.items():



            total = counts["passed"] + counts["failed"]



            if total >= 3:



                self.db.upsert_knowledge(category="strategy_performance", source_type="execution", domain=strategy,



                                         title=f"Strategy {strategy} performance pattern",



                                         content={"strategy": strategy, "success_rate": round(counts["passed"]/total, 3),



                                                  "sample_size": total, "passed": counts["passed"], "failed": counts["failed"]},



                                         project_hash=project_hash)



        for r in results:



            if not r.get("passed") and r.get("error"):



                error_msg = str(r["error"])[:200]



                self.db.upsert_knowledge(category="failure_pattern", source_type="execution", domain=r.get("strategy", "unknown"),



                                         title=f"Failure: {error_msg[:80]}",



                                         content={"error": error_msg, "strategy": r.get("strategy"), "test_name": r.get("test_name", "")},



                                         project_hash=project_hash)



    def from_heal_event(self, layer: str, original: str, healed: str, success: bool):



        self.db.upsert_knowledge(category="heal_pattern" if success else "heal_failure", source_type="heal", domain=layer,



                                 title=f"Heal: {layer} - {str(original)[:60]} -> {str(healed)[:60]}",



                                 content={"layer": layer, "original": str(original)[:200], "healed": str(healed)[:200], "success": success})



    def from_flaky_detection(self, test_name: str, flaky_score: float, root_cause: str):



        self.db.upsert_knowledge(category="flaky_pattern", source_type="flaky_detector", domain="flaky",



                                 title=f"Flaky: {test_name} (score={flaky_score:.2f})",



                                 content={"test_name": test_name, "flaky_score": flaky_score, "root_cause": root_cause})







class StrategyAdapter:



    def __init__(self, db: EvolutionDB): self.db = db



    def sample_weights(self) -> dict:



        import random as rnd



        strategies = self.db.get_all_strategies()



        existing = {s.name: s for s in strategies}



        samples = {}



        for name, initial_weight in INITIAL_STRATEGY_WEIGHTS.items():



            sp = existing.get(name)



            if sp and (sp.successful_cases + sp.failed_cases) >= 1:



                alpha = sp.successful_cases + 1



                beta = sp.failed_cases + 1



                sample = rnd.betavariate(alpha, beta)



                cost_penalty = 1.0 / (1.0 + STRATEGY_COSTS.get(name, 0) * 0.5)



                samples[name] = sample * cost_penalty * initial_weight



            else:



                exploration_bonus = 1.0 + 0.5 / max(sp.total_calls, 1) if sp else 2.0



                samples[name] = initial_weight * exploration_bonus



        total = sum(samples.values()) or 1.0



        return {k: round(v / total, 4) for k, v in samples.items()}



    def get_recommended_order(self) -> list:



        weights = self.sample_weights()



        sorted_items = sorted(weights.items(), key=lambda x: x[1], reverse=True)



        result = []



        for name, weight in sorted_items:



            sp = self.db.get_strategy_performance(name)



            result.append({"name": name, "weight": weight, "calls": sp.total_calls if sp else 0,
                           "cases": sp.total_cases if sp else 0,
                           "success_rate": round(sp.success_rate, 3) if sp else 0.0,
                           "avg_duration_ms": round(sp.avg_duration_ms, 1) if sp else 0.0,
                           "recommended_weight": round(weight, 4),
                           "cost_per_call": STRATEGY_COSTS.get(name, 0)})



        return result



    def update_from_execution(self, strategy: str, case_count: int, passed_count: int, failed_count: int, duration_ms: float):



        sp = self.db.get_strategy_performance(strategy)



        if sp:



            tc = sp.total_calls + 1; tca = sp.total_cases + case_count



            sc = sp.successful_cases + passed_count; fc = sp.failed_cases + failed_count



            n = max(tc, 1); ad = (sp.avg_duration_ms * (n - 1) + duration_ms) / n



        else:



            tc = 1; tca = case_count; sc = passed_count; fc = failed_count; ad = duration_ms



        self.db.upsert_strategy(name=strategy, total_calls=tc, total_cases=tca,



                                successful_cases=sc, failed_cases=fc, avg_duration_ms=ad,



                                current_weight=INITIAL_STRATEGY_WEIGHTS.get(strategy, 1.0))







class ProjectTransfer:



    def __init__(self, db: EvolutionDB): self.db = db



    def compute_project_hash(self, project_id: str, samples: list) -> str:



        if not samples: return hashlib.md5(project_id.encode()).hexdigest()[:12]



        features = []



        type_counts = {}; pass_count = 0; durations = []; tags = set()



        for s in samples:



            strategy = s.get("strategy", ""); type_counts[strategy] = type_counts.get(strategy, 0) + 1



            if s.get("passed"): pass_count += 1



            dur = s.get("duration_ms", 0)



            if dur > 0: durations.append(dur)



            for tag in (s.get("tags") or []): tags.add(str(tag))



        total = max(len(samples), 1)



        for strategy in sorted(type_counts): features.append(f"{strategy}:{type_counts[strategy]}")



        features.append(f"pass_rate:{round(pass_count / total, 2)}")



        if durations: features.append(f"avg_dur:{round(sum(durations) / len(durations))}")



        if tags: features.append(f"tags:{','.join(sorted(tags)[:10])}")



        raw = "|".join(features)



        hash_val = hashlib.md5(raw.encode()).hexdigest()



        self.db.save_project_pattern(project_id, hash_val, {"features": features, "sample_count": len(samples),



                                     "type_distribution": type_counts, "pass_rate": round(pass_count / total, 3)})



        return hash_val



    def find_similar_projects(self, source_project: str, top_k: int = 5) -> list:



        all_patterns = self.db.get_all_project_patterns()



        source_pattern = None; others = []



        for p in all_patterns:



            if p["project_id"] == source_project: source_pattern = p



            else: others.append(p)



        if not source_pattern or not others: return []



        results = []



        for other in others:



            sim = self._jaccard_similarity(source_pattern["project_hash"], other["project_hash"])



            results.append({"project_id": other["project_id"], "project_hash": other["project_hash"], "similarity": round(sim, 4)})



        results.sort(key=lambda x: x["similarity"], reverse=True)



        return results[:top_k]



    def recommend_knowledge_transfer(self, source_project: str, all_projects: list, knowledge_limit: int = 10) -> list:



        similar = self.find_similar_projects(source_project, top_k=min(len(all_projects), 5))



        if not similar: return []



        transferred = []; seen_ids = set()



        for proj in similar:



            if proj["similarity"] < 0.3: continue



            items = self.db.get_knowledge_by_project_hash(proj["project_hash"], limit=knowledge_limit)



            for item in items:



                if item["id"] not in seen_ids:



                    seen_ids.add(item["id"])



                    transferred.append({**item, "source_project": proj["project_id"], "transfer_similarity": proj["similarity"]})



        return transferred[:knowledge_limit]



    @staticmethod



    def _jaccard_similarity(hash_a: str, hash_b: str) -> float:



        if not hash_a or not hash_b: return 0.0



        def ngrams(s, n=3): return {s[i:i+n] for i in range(len(s)-n+1)}



        a_grams = ngrams(hash_a.lower()); b_grams = ngrams(hash_b.lower())



        if not a_grams or not b_grams: return 0.0



        return len(a_grams & b_grams) / len(a_grams | b_grams)







class EvolutionLoop:



    def __init__(self, db_path: str = ""):



        self.db = EvolutionDB(db_path)



        self.knowledge_builder = KnowledgeBuilder(self.db)



        self.strategy_adapter = StrategyAdapter(self.db)



        self._lock = asyncio.Lock()



        self._current_project = "default"



    def set_project(self, project_id: str): self._current_project = project_id



    async def on_execution_complete(self, results: list) -> dict:



        async with self._lock:



            try:



                project = self._current_project



                self.db.log_event(EvolutionEventType.EXECUTION_COMPLETE.value,



                                  {"project_id": project, "total": len(results),



                                   "passed": sum(1 for r in results if r.get("passed")),



                                   "failed": sum(1 for r in results if not r.get("passed"))}, project_id=project)



                sp = {}



                for r in results:



                    s = r.get("strategy", "template")



                    if s not in sp: sp[s] = {"cases": 0, "passed": 0, "failed": 0, "dur": 0.0}



                    sp[s]["cases"] += 1



                    if r.get("passed"): sp[s]["passed"] += 1



                    else: sp[s]["failed"] += 1



                    sp[s]["dur"] += r.get("duration_ms", 0)



                for s, p in sp.items():



                    self.strategy_adapter.update_from_execution(strategy=s, case_count=p["cases"],



                        passed_count=p["passed"], failed_count=p["failed"],



                        duration_ms=p["dur"] / max(p["cases"], 1))



                self.knowledge_builder.from_execution_results(results)



                weights = self.strategy_adapter.sample_weights()



                passed = sum(1 for r in results if r.get("passed"))



                return {"total": len(results), "passed": passed, "failed": len(results) - passed,



                        "updated_weights": weights, "knowledge_total": self.db.knowledge_count()}



            except Exception as e:



                logger.exception("Evolution on_execution_complete failed: %s", e)



                return {"error": str(e)}



    async def on_strategy_called(self, strategy: str, case_count: int = 1, duration_ms: int = 0):



        async with self._lock:



            try:



                self.db.log_event(EvolutionEventType.STRATEGY_CALLED.value,



                                  {"strategy": strategy, "case_count": case_count, "duration_ms": duration_ms,



                                   "project_id": self._current_project}, project_id=self._current_project)



            except Exception as e:



                logger.exception("Evolution on_strategy_called failed: %s", e)



    async def on_heal_event(self, layer: str, original: str, healed: str, success: bool):



        async with self._lock:



            try:



                et = EvolutionEventType.HEAL_SUCCESS.value if success else EvolutionEventType.HEAL_FAILURE.value



                self.db.log_event(et, {"layer": layer, "original": str(original)[:200],



                                       "healed": str(healed)[:200], "success": success}, project_id=self._current_project)



                self.knowledge_builder.from_heal_event(layer, original, healed, success)



            except Exception as e:



                logger.exception("Evolution on_heal_event failed: %s", e)



    async def on_flaky_detected(self, test_name: str, flaky_score: float, root_cause: str):



        async with self._lock:



            try:



                self.db.log_event(EvolutionEventType.FLAKY_DETECTED.value,



                                  {"test_name": test_name, "flaky_score": flaky_score, "root_cause": root_cause},



                                  project_id=self._current_project)



                self.knowledge_builder.from_flaky_detection(test_name, flaky_score, root_cause)



            except Exception as e:



                logger.exception("Evolution on_flaky_detected failed: %s", e)



    def search_knowledge(self, query: str = "", category: str = "", limit: int = 20) -> list:



        return self.db.search_knowledge(query=query, category=category, limit=limit)



    def get_recommended_strategies(self) -> list:



        return self.strategy_adapter.get_recommended_order()



    def knowledge_count(self) -> int:



        return self.db.knowledge_count()



    def get_evolution_report(self) -> dict:



        strategies = self.get_recommended_strategies()



        total_events = self.db.get_event_count()



        total_knowledge = self.db.knowledge_count()



        recent = self.db.get_recent_events(limit=100)



        ed = {}



        for e in recent: t = e.get("event_type", ""); ed[t] = ed.get(t, 0) + 1



        sd = []



        for s in strategies:



            sp = self.db.get_strategy_performance(s["name"])



            if sp: sd.append({"name": sp.name, "calls": sp.total_calls, "cases": sp.total_cases,



                              "success_rate": round(sp.success_rate, 3), "avg_duration_ms": round(sp.avg_duration_ms, 1),



                              "recommended_weight": s["weight"]})



        rk = self.db.search_knowledge(limit=5)



        return {"summary": {"total_events": total_events, "total_knowledge": total_knowledge, "total_strategies": len(strategies),



                            "primary_strategy": strategies[0]["name"] if strategies else "template"},



                "strategies": sd,



                "recent_event_distribution": ed,



                "recent_knowledge": [{"id": k["id"], "category": k["category"], "title": k["title"], "score": k["score"]} for k in rk]}



    def get_cross_project_recommendations(self, source_project: str, all_projects: list) -> list:



        transfer = ProjectTransfer(self.db)



        return transfer.recommend_knowledge_transfer(source_project, all_projects)







evolution_loop = EvolutionLoop()







if __name__ == "__main__":



    print("Self-evolution module loaded successfully.")



    print(f"Knowledge count: {evolution_loop.knowledge_count()}")



    print(f"Recommended strategies: {evolution_loop.get_recommended_strategies()}")



    print(f"DB path: {DB_PATH}")



