"""REST API for near-real-time sales transaction ingestion and metrics."""
import sqlite3
from datetime import date
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from src.database import DB_PATH, initialize_database, query_sales

app = FastAPI(title="AI Sales Intelligence API", version="1.0.0",
              description="Ingest sales transactions and query live aggregate metrics.")

class SaleIn(BaseModel):
    order_id: str = Field(min_length=1, max_length=100)
    order_date: date
    customer_id: str = Field(min_length=1, max_length=100)
    product: str = Field(min_length=1, max_length=200)
    category: str = Field(min_length=1, max_length=100)
    quantity: int = Field(gt=0, le=100000)
    unit_price: float = Field(ge=0)
    unit_cost: float = Field(ge=0)

@app.on_event("startup")
def startup():
    initialize_database(DB_PATH)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/metrics")
def metrics():
    df = query_sales(DB_PATH)
    if df.empty:
        return {"transactions": 0, "revenue": 0.0, "orders": 0, "customers": 0, "profit": 0.0}
    return {"transactions": int(len(df)), "revenue": float(df.revenue.sum()),
            "orders": int(df.order_id.nunique()), "customers": int(df.customer_id.nunique()),
            "profit": float(df.profit.sum())}

@app.get("/sales")
def list_sales(limit: int = 100):
    if limit < 1 or limit > 5000:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 5000")
    df = query_sales(DB_PATH).tail(limit).copy()
    if not df.empty:
        df["order_date"] = df["order_date"].astype(str)
    return df.where(df.notna(), None).to_dict("records")

@app.post("/sales", status_code=201)
def create_sale(sale: SaleIn):
    row = sale.model_dump()
    try:
        with sqlite3.connect(DB_PATH, timeout=10) as conn:
            conn.execute("""INSERT INTO sales
                (order_id, order_date, customer_id, product, category, quantity, unit_price, unit_cost)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (row["order_id"], row["order_date"].isoformat(), row["customer_id"], row["product"],
                 row["category"], row["quantity"], row["unit_price"], row["unit_cost"]))
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=409, detail="Transaction could not be inserted; check duplicate ID or constraints.") from exc
    return {"status": "created", "order_id": row["order_id"]}
