# Architecture Decision Records

## ADR-001: FastAPI over other frameworks

**Decision:** Used FastAPI as the web framework for ShopLedger.

**Why FastAPI?** Auto-generates Swagger UI for testing, built-in Pydantic validation, and Python-native which matches our stack.

---

## ADR-002: SQLite for Local Persistence

**Decision:** Replaced in-memory list storage with SQLite via Python's built-in `sqlite3` library.

**Why not keep the list in memory?** Data stored in RAM is lost when the process stops. Every server restart would wipe all sales records — unusable for a real shop.

**Why SQLite over PostgreSQL?** SQLite requires no separate server process. The entire database lives in a single file (`shopledger.db`) on disk. For a single-user local application at this stage, this is simpler and sufficient. PostgreSQL will be considered when the app needs multiple concurrent users or a hosted deployment.

---

## ADR-003: Nullable `supplier` column in expenses table

**Decision:** The `supplier` column in the `expenses` table is nullable (no `NOT NULL` constraint).

**Reasoning:** Not every expense has a supplier. Categories like rent, electricity, or staff wages are paid to fixed recipients that don't need to be tracked per transaction. Supplier matters mainly for restocking expenses where the shop pays different vendors (e.g. Bosch India, Tata Steel). Forcing every expense to have a supplier would require fake values like "N/A" for non-supplier expenses — bad data hygiene.
---

## ADR-004: Validation at the API boundary; profit calculated in Python

**Decision on validation:** All user input — including query parameters like `month` — is validated server-side using FastAPI's `Query()` with a regex pattern.

**Reasoning:** UI-level validation (Swagger UI, frontend forms) can be bypassed by anyone who hits the API directly via URL or HTTP client. The server cannot trust that input was filtered before it arrived. Boundary validation is the only real defence — without it, malformed inputs like `month=banana` would silently return null results instead of clear errors.

**Decision on profit calculation:** Profit (`total_sales − total_expenses`) is calculated in Python after running two separate SQL queries, not in a single combined SQL query.

**Reasoning:** Sales and expenses live in different tables. Combining them in SQL would require a `JOIN`, which adds complexity not yet justified at this scale. Profit is a derived value rather than stored data — by convention, raw data lives in the database and derived values are computed in application code. This keeps queries simple and logic readable.

---

## ADR-005: PUT (full replacement) over PATCH (partial update)

**Decision:** Update endpoints use `PUT` with full-object replacement rather than `PATCH` with partial updates.

**Reasoning:** PATCH requires dynamic SQL construction based on which fields the client sent, plus extra handling for edge cases like empty bodies or unknown fields. PUT keeps the SQL static and the validation logic simple — every request must contain the full object, validated by the existing Pydantic model. The frontend solves the UX concern by pre-filling the edit form with current values, so users don't manually re-enter unchanged fields.

**Tradeoff:** True partial updates are not supported. Every update sends the complete object over the network, even when only one field changed. For this app's scale and traffic this is negligible; if needed later, a PATCH endpoint can be added without breaking PUT.