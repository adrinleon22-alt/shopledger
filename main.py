import os
import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
from io import BytesIO
from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from datetime import datetime
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from openpyxl import Workbook

app = FastAPI()

DATABASE_URL = os.environ["DATABASE_URL"]

SHOP_NAME = "ALVA'S Hardware"
SHOP_ADDRESS = "123 Main Road, Bengaluru, KA"
SHOP_PHONE = "+91 9876543210"
SHOP_GSTIN = "29ABCDE1234F1Z5"


@contextmanager
def get_conn():
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS customers (
                    id          SERIAL PRIMARY KEY,
                    name        TEXT    NOT NULL,
                    phone       TEXT,
                    created_at  TEXT    NOT NULL
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS sales (
                    id          SERIAL PRIMARY KEY,
                    item        TEXT    NOT NULL,
                    quantity    INTEGER NOT NULL,
                    price       REAL    NOT NULL,
                    total       REAL    NOT NULL,
                    customer_id INTEGER REFERENCES customers(id),
                    created_at  TEXT    NOT NULL
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS expenses (
                    id          SERIAL PRIMARY KEY,
                    category    TEXT    NOT NULL,
                    amount      REAL    NOT NULL,
                    supplier    TEXT,
                    created_at  TEXT    NOT NULL
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS payments (
                    id       SERIAL PRIMARY KEY,
                    sale_id  INTEGER NOT NULL REFERENCES sales(id) ON DELETE CASCADE,
                    amount   REAL    NOT NULL,
                    paid_at  TEXT    NOT NULL
                )
            """)
        conn.commit()


init_db()


class SaleCreate(BaseModel):
    item: str = Field(min_length=1, max_length=100)
    quantity: int = Field(gt=0)
    price: float = Field(gt=0)
    customer_id: int | None = None


class ExpenseCreate(BaseModel):
    category: str = Field(min_length=1, max_length=100)
    amount: float = Field(gt=0)
    supplier: str | None = None


class CustomerCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    phone: str | None = None


class PaymentCreate(BaseModel):
    sale_id: int
    amount: float = Field(gt=0)


@app.get("/sales")
def get_sales():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM sales")
            sales = cur.fetchall()
    return {"sales": [dict(s) for s in sales]}


@app.post("/sales", status_code=201)
def create_sale(sale: SaleCreate):
    total = sale.quantity * sale.price
    created_at = datetime.utcnow().isoformat()
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO sales (item, quantity, price, total, customer_id, created_at) VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
                (sale.item, sale.quantity, sale.price, total, sale.customer_id, created_at)
            )
            new_id = cur.fetchone()["id"]
        conn.commit()
    return {
        "id": new_id, "item": sale.item, "quantity": sale.quantity,
        "price": sale.price, "total": total, "customer_id": sale.customer_id,
        "created_at": created_at,
    }


@app.get("/expenses")
def get_expenses():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM expenses")
            expenses = cur.fetchall()
    return {"expenses": [dict(e) for e in expenses]}


@app.post("/expenses", status_code=201)
def create_expense(expense: ExpenseCreate):
    created_at = datetime.utcnow().isoformat()
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO expenses (category, amount, supplier, created_at) VALUES (%s, %s, %s, %s) RETURNING id",
                (expense.category, expense.amount, expense.supplier, created_at)
            )
            new_id = cur.fetchone()["id"]
        conn.commit()
    return {
        "id": new_id, "category": expense.category, "amount": expense.amount,
        "supplier": expense.supplier, "created_at": created_at,
    }


@app.get("/summary")
def get_summary(month: str = Query(..., pattern=r"^\d{4}-\d{2}$")):
    pattern = f"{month}%"
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COALESCE(SUM(total), 0) AS total FROM sales WHERE created_at LIKE %s", (pattern,))
            total_sales = cur.fetchone()["total"]
            cur.execute("SELECT COALESCE(SUM(amount), 0) AS total FROM expenses WHERE created_at LIKE %s", (pattern,))
            total_expenses = cur.fetchone()["total"]
    return {
        "month": month, "total_sales": total_sales,
        "total_expenses": total_expenses, "profit": total_sales - total_expenses,
    }


@app.delete("/sales/{sale_id}", status_code=204)
def delete_sale(sale_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM sales WHERE id = %s", (sale_id,))
            rowcount = cur.rowcount
        conn.commit()
    if rowcount == 0:
        raise HTTPException(status_code=404, detail="Sale not found")


@app.delete("/expenses/{expense_id}", status_code=204)
def delete_expense(expense_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM expenses WHERE id = %s", (expense_id,))
            rowcount = cur.rowcount
        conn.commit()
    if rowcount == 0:
        raise HTTPException(status_code=404, detail="Expense not found")


@app.put("/sales/{sale_id}")
def update_sale(sale_id: int, sale: SaleCreate):
    total = sale.quantity * sale.price
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE sales SET item = %s, quantity = %s, price = %s, total = %s WHERE id = %s",
                (sale.item, sale.quantity, sale.price, total, sale_id)
            )
            rowcount = cur.rowcount
        conn.commit()
    if rowcount == 0:
        raise HTTPException(status_code=404, detail="Sale not found")
    return {
        "id": sale_id, "item": sale.item, "quantity": sale.quantity,
        "price": sale.price, "total": total,
    }


@app.put("/expenses/{expense_id}")
def update_expense(expense_id: int, expense: ExpenseCreate):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE expenses SET category = %s, amount = %s, supplier = %s WHERE id = %s",
                (expense.category, expense.amount, expense.supplier, expense_id)
            )
            rowcount = cur.rowcount
        conn.commit()
    if rowcount == 0:
        raise HTTPException(status_code=404, detail="Expense not found")
    return {
        "id": expense_id, "category": expense.category,
        "amount": expense.amount, "supplier": expense.supplier,
    }


@app.post("/customers", status_code=201)
def create_customer(customer: CustomerCreate):
    created_at = datetime.utcnow().isoformat()
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO customers (name, phone, created_at) VALUES (%s, %s, %s) RETURNING id",
                (customer.name, customer.phone, created_at)
            )
            new_id = cur.fetchone()["id"]
        conn.commit()
    return {
        "id": new_id, "name": customer.name,
        "phone": customer.phone, "created_at": created_at,
    }


@app.get("/customers")
def get_customers():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    customers.id, customers.name, customers.phone,
                    COALESCE(SUM(DISTINCT sales.total), 0) - COALESCE(SUM(payments.amount), 0) AS outstanding_balance
                FROM customers
                LEFT JOIN sales ON sales.customer_id = customers.id
                LEFT JOIN payments ON payments.sale_id = sales.id
                GROUP BY customers.id
            """)
            customers = cur.fetchall()
    return {"customers": [dict(c) for c in customers]}


@app.post("/payments", status_code=201)
def create_payment(payment: PaymentCreate):
    paid_at = datetime.utcnow().isoformat()
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT total FROM sales WHERE id = %s", (payment.sale_id,))
            sale = cur.fetchone()
            if sale is None:
                raise HTTPException(status_code=404, detail="Sale not found")
            sale_total = sale["total"]

            cur.execute("SELECT COALESCE(SUM(amount), 0) AS total FROM payments WHERE sale_id = %s", (payment.sale_id,))
            existing_paid = cur.fetchone()["total"]

            if existing_paid + payment.amount > sale_total:
                remaining = sale_total - existing_paid
                raise HTTPException(
                    status_code=400,
                    detail=f"Payment exceeds remaining debt. Remaining: {remaining}"
                )

            cur.execute(
                "INSERT INTO payments (sale_id, amount, paid_at) VALUES (%s, %s, %s) RETURNING id",
                (payment.sale_id, payment.amount, paid_at)
            )
            new_id = cur.fetchone()["id"]
        conn.commit()
    return {"id": new_id, "sale_id": payment.sale_id, "amount": payment.amount, "paid_at": paid_at}


@app.get("/udhaar/total")
def get_total_udhaar():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    COALESCE(SUM(sales.total), 0) - COALESCE(SUM(payments.amount), 0) AS total_udhaar
                FROM sales
                LEFT JOIN payments ON payments.sale_id = sales.id
                WHERE sales.customer_id IS NOT NULL
            """)
            result = cur.fetchone()
    return {"total_udhaar": result["total_udhaar"]}


@app.get("/customers/{customer_id}/balance")
def get_customer_balance(customer_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name, phone FROM customers WHERE id = %s", (customer_id,))
            customer = cur.fetchone()
            if customer is None:
                raise HTTPException(status_code=404, detail="Customer not found")

            cur.execute(
                """
                SELECT 
                    sales.id, sales.item, sales.total, sales.created_at,
                    COALESCE(SUM(payments.amount), 0) AS amount_paid
                FROM sales
                LEFT JOIN payments ON payments.sale_id = sales.id
                WHERE sales.customer_id = %s
                GROUP BY sales.id
                """,
                (customer_id,)
            )
            sales_rows = cur.fetchall()

    sales = []
    outstanding_balance = 0
    for row in sales_rows:
        pending = row["total"] - row["amount_paid"]
        outstanding_balance += pending
        sales.append({
            "sale_id": row["id"], "item": row["item"], "total": row["total"],
            "amount_paid": row["amount_paid"], "amount_pending": pending,
            "created_at": row["created_at"],
        })

    return {
        "customer": {"id": customer["id"], "name": customer["name"], "phone": customer["phone"]},
        "outstanding_balance": outstanding_balance,
        "sales": sales,
    }


@app.get("/sales/{sale_id}/receipt")
def get_sale_receipt(sale_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM sales WHERE id = %s", (sale_id,))
            sale = cur.fetchone()
            if sale is None:
                raise HTTPException(status_code=404, detail="Sale not found")

            customer = None
            if sale["customer_id"] is not None:
                cur.execute("SELECT name, phone FROM customers WHERE id = %s", (sale["customer_id"],))
                customer = cur.fetchone()

            cur.execute("SELECT COALESCE(SUM(amount), 0) AS total FROM payments WHERE sale_id = %s", (sale_id,))
            amount_paid = cur.fetchone()["total"]

    amount_pending = sale["total"] - amount_paid
    if amount_pending == 0:
        status = "PAID"
    elif amount_paid == 0:
        status = "UNPAID (UDHAAR)"
    else:
        status = f"PARTIAL ({amount_paid}/{sale['total']})"

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    y = height - 50
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(50, y, SHOP_NAME)
    pdf.setFont("Helvetica", 10)
    y -= 20; pdf.drawString(50, y, SHOP_ADDRESS)
    y -= 15; pdf.drawString(50, y, f"Phone: {SHOP_PHONE}")
    y -= 15; pdf.drawString(50, y, f"GSTIN: {SHOP_GSTIN}")
    y -= 30; pdf.line(50, y, width - 50, y)
    y -= 25
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(50, y, f"Receipt #{sale['id']}")
    pdf.setFont("Helvetica", 10)
    pdf.drawString(width - 200, y, f"Date: {sale['created_at'][:10]}")

    if customer is not None:
        y -= 25
        pdf.setFont("Helvetica-Bold", 11)
        pdf.drawString(50, y, "Customer:")
        pdf.setFont("Helvetica", 10)
        y -= 15; pdf.drawString(50, y, f"Name: {customer['name']}")
        if customer["phone"]:
            y -= 15; pdf.drawString(50, y, f"Phone: {customer['phone']}")

    y -= 30; pdf.line(50, y, width - 50, y)
    y -= 25
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(50, y, "Item"); pdf.drawString(280, y, "Qty")
    pdf.drawString(360, y, "Price"); pdf.drawString(460, y, "Total")
    y -= 20
    pdf.setFont("Helvetica", 10)
    pdf.drawString(50, y, sale["item"])
    pdf.drawString(280, y, str(sale["quantity"]))
    pdf.drawString(360, y, f"INR {sale['price']:.2f}")
    pdf.drawString(460, y, f"INR {sale['total']:.2f}")
    y -= 30; pdf.line(50, y, width - 50, y)
    y -= 25
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(360, y, "TOTAL:")
    pdf.drawString(460, y, f"INR {sale['total']:.2f}")
    y -= 25
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(50, y, f"Status: {status}")
    y -= 60
    pdf.setFont("Helvetica-Oblique", 9)
    pdf.drawString(50, y, "Thank you for your business")

    pdf.showPage()
    pdf.save()
    pdf_bytes = buffer.getvalue()

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="receipt-{sale_id}.pdf"'}
    )


@app.get("/export/ledger")
def export_ledger(month: str = Query(..., pattern=r"^\d{4}-\d{2}$")):
    pattern = f"{month}%"
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 
                    created_at AS date, 'Sale' AS type, item AS description,
                    total AS amount_in, 0 AS amount_out
                FROM sales
                WHERE created_at LIKE %s
                UNION ALL
                SELECT 
                    created_at AS date, 'Expense' AS type, COALESCE(supplier, category) AS description,
                    0 AS amount_in, amount AS amount_out
                FROM expenses
                WHERE created_at LIKE %s
                ORDER BY date
                """,
                (pattern, pattern)
            )
            rows = cur.fetchall()

    wb = Workbook()
    ws = wb.active
    ws.title = f"Ledger {month}"
    headers = ["Date", "Type", "Description", "Amount In (INR)", "Amount Out (INR)"]
    ws.append(headers)
    total_in = 0
    total_out = 0
    for row in rows:
        ws.append([row["date"][:10], row["type"], row["description"], row["amount_in"], row["amount_out"]])
        total_in += row["amount_in"]
        total_out += row["amount_out"]
    ws.append([])
    ws.append(["", "", "TOTALS", total_in, total_out])
    ws.append(["", "", "NET", total_in - total_out, ""])

    buffer = BytesIO()
    wb.save(buffer)
    excel_bytes = buffer.getvalue()

    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="ledger-{month}.xlsx"'}
    )


app.mount("/", StaticFiles(directory="static", html=True), name="static")