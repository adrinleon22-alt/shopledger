import sqlite3
from fastapi import FastAPI
from pydantic import BaseModel, Field
from datetime import datetime

app = FastAPI()

# The database is now a file on disk, not a Python list in RAM
DATABASE = "shopledger.db"


def init_db():
    conn = sqlite3.connect(DATABASE)
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
    conn.commit()
    conn.close()


# Runs once when the server starts
init_db()


class SaleCreate(BaseModel):
    item: str = Field(min_length=1, max_length=100)
    quantity: int = Field(gt=0)
    price: float = Field(gt=0)


@app.get("/")
def root():
    return {"message": "ShopLedger API"}


@app.get("/sales")
def get_sales():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    sales = conn.execute("SELECT * FROM sales").fetchall()
    conn.close()
    return {"sales": [dict(sale) for sale in sales]}


@app.post("/sales", status_code=201)
def create_sale(sale: SaleCreate):
    total = sale.quantity * sale.price
    created_at = datetime.utcnow().isoformat()

    conn = sqlite3.connect(DATABASE)
    cursor = conn.execute(
        "INSERT INTO sales (item, quantity, price, total, created_at) VALUES (?, ?, ?, ?, ?)",
        (sale.item, sale.quantity, sale.price, total, created_at)
    )
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()

    return {
        "id": new_id,
        "item": sale.item,
        "quantity": sale.quantity,
        "price": sale.price,
        "total": total,
        "created_at": created_at,
    }