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
---

## ADR-006: Separate payments table instead of `amount_paid` column on sales

**Decision:** Partial payments are tracked in a dedicated `payments` table linked to sales via a foreign key, rather than as an `amount_paid` column on the sales table.

**Reasoning:** A single column can only store the total amount paid — not when payments happened, how many payments were made, or in what order. For a bookkeeping app where customers pay debts in instalments (common in udhaar), losing this history makes the app useless as an audit trail. With a separate table, each payment is its own row, fully traceable. The total amount paid is then a *derived value* — computed by summing `payments.amount` for a given `sale_id` — rather than stored redundantly.

**Tradeoff:** More complex queries (joins / subqueries needed to compute remaining debt), one extra table to maintain, and `ON DELETE CASCADE` required to keep payments consistent when sales are deleted.

---

## ADR-007: Business rules enforced at the API layer, not in the database

**Decision:** Business rules like "payment must not exceed remaining debt" are enforced in the FastAPI endpoint logic, not via SQL `CHECK` constraints or triggers.

**Reasoning:** These rules depend on data across multiple rows and tables (sale total, sum of prior payments) — `CHECK` constraints can only inspect the row being inserted. Business rules also change over time, and updating a Python `if` statement is cheaper than running a schema migration. Finally, raising `HTTPException(400, "Payment exceeds remaining debt. Remaining: 1230")` gives the client a clear, actionable message; a `CHECK` failure returns an opaque database error.

**Tradeoff:** The rule is only enforced for requests that go through the API. Anyone with direct database access (a developer running raw SQL, a future admin tool, a misconfigured ORM) can bypass it. For a single-tenant app where the API is the only entry point, this is acceptable; in larger systems, critical invariants are often duplicated in both layers as defence in depth.
---

## ADR-008: LEFT JOIN over INNER JOIN for customer balance query

**Decision:** The `GET /customers/{id}/balance` endpoint uses `LEFT JOIN` between `sales` and `payments` rather than `INNER JOIN`.

**Reasoning:** The balance endpoint must show every sale belonging to the customer, including sales where no payment has been made yet — those are the pure udhaar cases that represent the largest portion of unpaid debt. An `INNER JOIN` would silently drop any sale with zero matching payment rows, making the outstanding balance incorrect. `LEFT JOIN` preserves all sales, and `COALESCE(SUM(payments.amount), 0)` handles the NULL that appears when a sale has no payments.

**Tradeoff:** `LEFT JOIN` is slightly slower than `INNER JOIN` on large datasets because the database can't drop unmatched rows early. At this scale the difference is negligible; in production with millions of rows, this query would likely need an index on `payments.sale_id`.