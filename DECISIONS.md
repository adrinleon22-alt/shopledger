# Architecture Decision Records

## ADR-001: FastAPI over other frameworks

**Decision:** Used FastAPI as the web framework for ShopLedger.

**Why FastAPI?** Auto-generates Swagger UI for testing, built-in Pydantic validation, and Python-native which matches our stack.

---

## ADR-002: SQLite for Local Persistence

**Decision:** Replaced in-memory list storage with SQLite via Python's built-in `sqlite3` library.

**Why not keep the list in memory?** Data stored in RAM is lost when the process stops. Every server restart would wipe all sales records — unusable for a real shop.

**Why SQLite over PostgreSQL?** SQLite requires no separate server process. The entire database lives in a single file (`shopledger.db`) on disk. For a single-user local application at this stage, this is simpler and sufficient. PostgreSQL will be considered when the app needs multiple concurrent users or a hosted deployment.