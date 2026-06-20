# ShopLedger

A bookkeeping API for a small hardware shop in India. Built to replace a paper-based ledger with digital sales, expenses, customer credit tracking, and monthly profit calculation.

## Why this exists

My parents run a hardware shop that has tracked everything on paper ever since its initiation. ## Why this exists

ShopLedger is a digital bookkeeping system for small hardware shops still operating on paper-based ledgers — a common setup across small retail in India. The goal is to capture sales, expenses, and customer credit (udhaar) in a way that fits existing shop workflows rather than forcing a new one, then surface monthly profit and outstanding-balance reports the owner couldn't easily compute by hand.

## Stack

- **Python 3.14** + **FastAPI** (REST API)
- **SQLite** (persistent storage)
- **Pydantic** (request validation)
- **ReportLab** (PDF receipt generation)
- **openpyxl** (Excel ledger export)

## Features

- CRUD for sales, expenses, customers, payments
- Foreign key relationships with `ON DELETE CASCADE`
- Monthly summary endpoint with profit calculation
- Customer balance lookup with `LEFT JOIN` across sales and payments
- Partial payment tracking (udhaar) with business-rule validation
- PDF receipt download per sale
- Excel ledger export per month (`UNION ALL` across sales and expenses)
- Architecture Decision Records in [DECISIONS.md](./DECISIONS.md)
- Roadmap in [IDEAS.md](./IDEAS.md)

## Running locally

```bash
pip install -r requirements.txt
python -m uvicorn main:app --reload
```

Then open `http://127.0.0.1:8000/docs` for interactive API documentation.

## Roadmap

Phase 1 (backend) — complete  
Phase 2 — vanilla HTML/CSS/JS frontend  
Phase 3 — deploy to a hosted environment (PostgreSQL migration planned)