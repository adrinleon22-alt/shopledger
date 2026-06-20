import sqlite3
from fastapi import FastAPI, Query, HTTPException
from pydantic import BaseModel, Field
from datetime import datetime
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from fastapi.responses import Response
from openpyxl import Workbook
from fastapi.staticfiles import StaticFiles
app = FastAPI()

DATABASE = "shopledger.db"

SHOP_NAME = "ALVA'S HARDWARE"
SHOP_ADDRESS = "Main Road, Moodubelle - 576120"
SHOP_PHONE = "+91 9483231871"
SHOP_GSTIN = "29ABCDE1234F1Z5"


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
    customer_id: int | None = None


class ExpenseCreate(BaseModel):
    category: str = Field(min_length=1, max_length=100)
    amount: float = Field(gt=0)
    supplier: str | None = None

class CustomerCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    phone: str | None = None


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
            "INSERT INTO sales (item, quantity, price, total,customer_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (sale.item, sale.quantity, sale.price, total, sale.customer_id, created_at)
        )
        conn.commit()
        new_id = cursor.lastrowid

    return {
        "id": new_id,
        "item": sale.item,
        "quantity": sale.quantity,
        "price": sale.price,
        "total": total,
        "customer_id": sale.customer_id,
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

@app.get("/customers/{customer_id}/balance")
def get_customer_balance(customer_id: int):
    with sqlite3.connect(DATABASE) as conn:
        conn.row_factory = sqlite3.Row
        
        customer = conn.execute(
            "SELECT id, name, phone FROM customers WHERE id = ?",
            (customer_id,)
        ).fetchone()
        
        if customer is None:
            raise HTTPException(status_code=404, detail="Customer not found")
        
        # Query 2 — get sales with payment sums (the JOIN)
        sales_rows = conn.execute(
            """
            SELECT 
                sales.id,
                sales.item,
                sales.total,
                sales.created_at,
                COALESCE(SUM(payments.amount), 0) AS amount_paid
            FROM sales
            LEFT JOIN payments ON payments.sale_id = sales.id
            WHERE sales.customer_id = ?
            GROUP BY sales.id
            """,
            (customer_id,)
        ).fetchall()
    
    sales = []
    outstanding_balance = 0
    for row in sales_rows:
        pending = row["total"] - row["amount_paid"]
        outstanding_balance += pending
        sales.append({
            "sale_id": row["id"],
            "item": row["item"],
            "total": row["total"],
            "amount_paid": row["amount_paid"],
            "amount_pending": pending,
            "created_at": row["created_at"],
        })
    
    return {
        "customer": {
            "id": customer["id"],
            "name": customer["name"],
            "phone": customer["phone"],
        },
        "outstanding_balance": outstanding_balance,
        "sales": sales,
    }

@app.get("/sales/{sale_id}/receipt")
def get_sale_receipt(sale_id: int):
    with sqlite3.connect(DATABASE) as conn:
        conn.row_factory = sqlite3.Row

        sale = conn.execute(
            "SELECT * FROM sales WHERE id = ?",
            (sale_id,)
        ).fetchone()

        if sale is None:
            raise HTTPException(status_code=404, detail="Sale not found")

        customer = None
        if sale["customer_id"] is not None:
            customer = conn.execute(
                "SELECT name, phone FROM customers WHERE id = ?",
                (sale["customer_id"],)
            ).fetchone()

        paid_result = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM payments WHERE sale_id = ?",
            (sale_id,)
        ).fetchone()
        amount_paid = paid_result[0]

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
    y -= 20
    pdf.drawString(50, y, SHOP_ADDRESS)
    y -= 15
    pdf.drawString(50, y, f"Phone: {SHOP_PHONE}")
    y -= 15
    pdf.drawString(50, y, f"GSTIN: {SHOP_GSTIN}")

    y -= 30
    pdf.line(50, y, width - 50, y)

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
        y -= 15
        pdf.drawString(50, y, f"Name: {customer['name']}")
        if customer["phone"]:
            y -= 15
            pdf.drawString(50, y, f"Phone: {customer['phone']}")

    y -= 30
    pdf.line(50, y, width - 50, y)

    y -= 25
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(50, y, "Item")
    pdf.drawString(280, y, "Qty")
    pdf.drawString(360, y, "Price")
    pdf.drawString(460, y, "Total")

    y -= 20
    pdf.setFont("Helvetica", 10)
    pdf.drawString(50, y, sale["item"])
    pdf.drawString(280, y, str(sale["quantity"]))
    pdf.drawString(360, y, f"INR {sale['price']:.2f}")
    pdf.drawString(460, y, f"INR {sale['total']:.2f}")

    y -= 30
    pdf.line(50, y, width - 50, y)

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
        headers={
            "Content-Disposition": f'attachment; filename="receipt-{sale_id}.pdf"'
        }
    )

@app.get("/export/ledger")
def export_ledger(month: str = Query(..., pattern=r"^\d{4}-\d{2}$")):
    pattern = f"{month}%"

    with sqlite3.connect(DATABASE) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT 
                created_at AS date,
                'Sale' AS type,
                item AS description,
                total AS amount_in,
                0 AS amount_out
            FROM sales
            WHERE created_at LIKE ?

            UNION ALL

            SELECT 
                created_at AS date,
                'Expense' AS type,
                COALESCE(supplier, category) AS description,
                0 AS amount_in,
                amount AS amount_out
            FROM expenses
            WHERE created_at LIKE ?

            ORDER BY date
            """,
            (pattern, pattern)
        ).fetchall()

    wb = Workbook()
    ws = wb.active
    ws.title = f"Ledger {month}"

    headers = ["Date", "Type", "Description", "Amount In (INR)", "Amount Out (INR)"]
    ws.append(headers)

    total_in = 0
    total_out = 0
    for row in rows:
        ws.append([
            row["date"][:10],
            row["type"],
            row["description"],
            row["amount_in"],
            row["amount_out"],
        ])
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
        headers={
            "Content-Disposition": f'attachment; filename="ledger-{month}.xlsx"'
        }
    )

app.mount("/", StaticFiles(directory="static", html=True), name="static")