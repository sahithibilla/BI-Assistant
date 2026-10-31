"""Data layer: load CSV -> clean -> SQLite.

Every row is kept in `sales_raw` with an `is_valid` flag and `invalid_reason`,
so nothing is silently dropped. The `sales` view exposes only valid rows with a
computed `revenue` column; all analytics query that view.
"""
import sqlite3
from pathlib import Path

import pandas as pd

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "sales_data.csv"


def clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [c.strip() for c in df.columns]
    for col in ["Transaction_Id", "Product", "Category", "Region", "Sales_channel", "Status"]:
        df[col] = df[col].astype("string").str.strip()
    # Dates are DD-MM-YYYY in the source file
    df["Order_date"] = pd.to_datetime(df["Order_date"], format="%d-%m-%Y", errors="coerce")
    for col in ["Quantity", "Unit_price", "Discount_amount"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["Discount_amount"] = df["Discount_amount"].fillna(0)

    reasons = []
    for _, r in df.iterrows():
        why = []
        if pd.isna(r["Order_date"]):
            why.append("invalid date")
        if pd.isna(r["Unit_price"]):
            why.append("missing unit price")
        if pd.isna(r["Quantity"]) or r["Quantity"] <= 0:
            why.append("quantity <= 0")
        if r["Status"] != "Completed":
            why.append(f"status={r['Status']}")
        reasons.append("; ".join(why))
    df["invalid_reason"] = reasons
    df["is_valid"] = (df["invalid_reason"] == "").astype(int)
    df["order_month"] = df["Order_date"].dt.strftime("%Y-%m")
    df["Order_date"] = df["Order_date"].dt.strftime("%Y-%m-%d")
    return df.drop_duplicates(subset="Transaction_Id")


def build_db(csv_path=DATA_PATH, db_path=":memory:") -> sqlite3.Connection:
    df = clean(pd.read_csv(csv_path))
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    df.to_sql("sales_raw", conn, index=False, if_exists="replace")
    conn.execute("DROP VIEW IF EXISTS sales")
    conn.execute(
        """CREATE VIEW sales AS
           SELECT Transaction_Id, Order_date, order_month, Product, Category, Region,
                  Sales_channel, Quantity, Unit_price, Discount_amount,
                  Quantity * Unit_price - Discount_amount AS revenue
           FROM sales_raw WHERE is_valid = 1"""
    )
    conn.commit()
    return conn


def data_quality(conn) -> dict:
    total = conn.execute("SELECT COUNT(*) FROM sales_raw").fetchone()[0]
    valid = conn.execute("SELECT COUNT(*) FROM sales").fetchone()[0]
    excluded = [dict(r) for r in conn.execute(
        "SELECT Transaction_Id, invalid_reason FROM sales_raw WHERE is_valid = 0")]
    return {"total_rows": total, "valid_rows": valid, "excluded": excluded}
