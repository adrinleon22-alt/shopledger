import sqlite3
from fastapi import FastAPI
from pydantic import BaseModel, Field
from datetime import datetime

app = FastAPI()

DATABASE = "shopledger.db"


def init_db():
    with sqlite3.connect(DATABASE) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sales (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                item       TEXT    NOT NULL,
                quantity   INTEGER NOT NULL,
                price      REAL    NOT NULL,
                total      REAL    NOT NULL,
                created_at TEXT    NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                category   TEXT    NOT NULL,
                amount     REAL    NOT NULL,
                supplier   TEXT,
                created_at TEXT    NOT NULL
            )
        """)
        conn.commit()


init_db()


class SaleCreate(BaseModel):
    item: str = Field(min_length=1, max_length=100)
    quantity: int = Field(gt=0)
    price: float = Field(gt=0)


class ExpenseCreate(BaseModel):
    category: str = Field(min_length=1, max_length=100)
    amount: float = Field(gt=0)
    supplier: str | None = None


@app.get("/")
def root():
    return {"message": "ShopLedger API"}


@app.get("/sales")
def get_sales():
    with sqlite3.connect(DATABASE) as conn:
        conn.row_factory = sqlite3.Row
        sales = conn.execute("SELECT * FROM sales").fetchall()
    return {"sales": [dict(sale) for sale in sales]}


@app.post("/sales", status_code=201)
def create_sale(sale: SaleCreate):
    total = sale.quantity * sale.price
    created_at = datetime.utcnow().isoformat()

    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.execute(
            "INSERT INTO sales (item, quantity, price, total, created_at) VALUES (?, ?, ?, ?, ?)",
            (sale.item, sale.quantity, sale.price, total, created_at)
        )
        conn.commit()
        new_id = cursor.lastrowid

    return {
        "id": new_id,
        "item": sale.item,
        "quantity": sale.quantity,
        "price": sale.price,
        "total": total,
        "created_at": created_at,
    }


@app.get("/expenses")
def get_expenses():
    with sqlite3.connect(DATABASE) as conn:
        conn.row_factory = sqlite3.Row
        expenses = conn.execute("SELECT * FROM expenses").fetchall()
    return {"expenses": [dict(expense) for expense in expenses]}


@app.post("/expenses", status_code=201)
def create_expense(expense: ExpenseCreate):
    created_at = datetime.utcnow().isoformat()

    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.execute(
            "INSERT INTO expenses (category, amount, supplier, created_at) VALUES (?, ?, ?, ?)",
            (expense.category, expense.amount, expense.supplier, created_at)
        )
        conn.commit()
        new_id = cursor.lastrowid

    return {
        "id": new_id,
        "category": expense.category,
        "amount": expense.amount,
        "supplier": expense.supplier,
        "created_at": created_at,
    }