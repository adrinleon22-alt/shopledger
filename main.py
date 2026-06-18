import sqlite3
from fastapi import FastAPI, Query, HTTPException
from pydantic import BaseModel, Field
from datetime import datetime

app = FastAPI()

DATABASE = "shopledger.db"


def init_db():
    with sqlite3.connect(DATABASE) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS customers (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT    NOT NULL,
                phone       TEXT,
                created_at  TEXT    NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sales (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                item        TEXT    NOT NULL,
                quantity    INTEGER NOT NULL,
                price       REAL    NOT NULL,
                total       REAL    NOT NULL,
                customer_id INTEGER,
                created_at  TEXT    NOT NULL,
                FOREIGN KEY (customer_id) REFERENCES customers(id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                category    TEXT    NOT NULL,
                amount      REAL    NOT NULL,
                supplier    TEXT,
                created_at  TEXT    NOT NULL
            )
        """)
        
        conn.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                sale_id  INTEGER NOT NULL,
                amount   REAL    NOT NULL,
                paid_at  TEXT    NOT NULL,
                FOREIGN KEY (sale_id) REFERENCES sales(id) ON DELETE CASCADE
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

class CustomerCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    phone: str | None = None


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


@app.get("/summary")
def get_summary(month: str = Query(..., pattern=r"^\d{4}-\d{2}$")):
    pattern = f"{month}%"

    with sqlite3.connect(DATABASE) as conn:
        sales_result = conn.execute(
            "SELECT SUM(total) FROM sales WHERE created_at LIKE ?",
            (pattern,)
        ).fetchone()

        expenses_result = conn.execute(
            "SELECT SUM(amount) FROM expenses WHERE created_at LIKE ?",
            (pattern,)
        ).fetchone()

    total_sales = sales_result[0] or 0
    total_expenses = expenses_result[0] or 0
    profit = total_sales - total_expenses

    return {
        "month": month,
        "total_sales": total_sales,
        "total_expenses": total_expenses,
        "profit": profit,
    }

@app.delete("/sales/{sale_id}", status_code=204)
def delete_sale(sale_id: int):
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.execute(
            "DELETE FROM sales WHERE id = ?",
            (sale_id,)
        )
        conn.commit()

    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Sale not found")

@app.delete("/expenses/{expense_id}", status_code=204)
def delete_expense(expense_id: int):
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.execute(
            "DELETE FROM expenses WHERE id = ?",
            (expense_id,)
        )
        conn.commit()

    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Expense not found")

@app.put("/sales/{sale_id}")
def update_sale(sale_id: int, sale: SaleCreate):
    total = sale.quantity * sale.price

    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.execute(
            "UPDATE sales SET item = ?, quantity = ?, price = ?, total = ? WHERE id = ?",
            (sale.item, sale.quantity, sale.price, total, sale_id)
        )
        conn.commit()

    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Sale not found")

    return {
        "id": sale_id,
        "item": sale.item,
        "quantity": sale.quantity,
        "price": sale.price,
        "total": total,
    }        

@app.put("/expenses/{expense_id}")
def update_expense(expense_id: int, expense: ExpenseCreate):

    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.execute(
            "UPDATE expenses SET category = ?, amount = ?, supplier = ? WHERE id = ?",
            (expense.category, expense.amount, expense.supplier, expense_id)
        )
        conn.commit()

    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Expense not found")

    return {
        "id": expense_id,
        "category": expense.category,
        "amount": expense.amount,
        "supplier": expense.supplier,
    } 

@app.post("/customers", status_code=201)
def create_customer(customer: CustomerCreate):
    created_at = datetime.utcnow().isoformat()

    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.execute(
            "INSERT INTO customers (name, phone, created_at) VALUES (?, ?, ?)",
            (customer.name,customer.phone, created_at)
        )
        conn.commit()
        new_id = cursor.lastrowid

    return {
        "id": new_id,
        "name": customer.name,
        "phone": customer.phone,
        "created_at": created_at,
    }


@app.get("/customers")
def get_customers():
    with sqlite3.connect(DATABASE) as conn:
        conn.row_factory = sqlite3.Row
        customers = conn.execute("SELECT * FROM customers").fetchall()
    return {"customers": [dict(customer) for customer in customers]}

class PaymentCreate(BaseModel):
    sale_id: int
    amount: float = Field(gt=0)


@app.post("/payments", status_code=201)
def create_payment(payment: PaymentCreate):
    paid_at = datetime.utcnow().isoformat()

    with sqlite3.connect(DATABASE) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        
        sale = conn.execute(
            "SELECT total FROM sales WHERE id = ?",
            (payment.sale_id,)
        ).fetchone()
        
        if sale is None:
            raise HTTPException(status_code=404, detail="Sale not found")
        
        sale_total = sale[0]
        
        result = conn.execute(
            "SELECT SUM(amount) FROM payments WHERE sale_id = ?",
            (payment.sale_id,)
        ).fetchone()
        existing_paid = result[0] or 0
        
        if existing_paid + payment.amount > sale_total:
            remaining = sale_total - existing_paid
            raise HTTPException(
                status_code=400,
                detail=f"Payment exceeds remaining debt. Remaining: {remaining}"
            )
        
        cursor = conn.execute(
            "INSERT INTO payments (sale_id, amount, paid_at) VALUES (?, ?, ?)",
            (payment.sale_id, payment.amount, paid_at)
        )
        conn.commit()
        new_id = cursor.lastrowid

    return {
        "id": new_id,
        "sale_id": payment.sale_id,
        "amount": payment.amount,
        "paid_at": paid_at,
    }