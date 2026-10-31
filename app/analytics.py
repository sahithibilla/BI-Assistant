"""Deterministic analytics. Each function runs one fixed, parameterised SQL query.

Revenue = Quantity * Unit_price - Discount_amount, over valid rows only
(Completed, quantity > 0, unit price present, date parseable).
"""
import re

_MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def _rows(conn, sql, params=()):
    cur = conn.execute(sql, params)
    cols = [d[0] for d in cur.description]
    return cols, [list(r) for r in cur.fetchall()], sql.strip()


def _fmt(x):
    return f"₹{x:,.0f}"


def total_revenue(conn, **_):
    cols, rows, sql = _rows(conn, """SELECT COUNT(*) AS transactions, SUM(Quantity) AS units,
        SUM(Quantity*Unit_price) AS gross, SUM(Discount_amount) AS discounts,
        SUM(revenue) AS net_revenue FROM sales""")
    return f"Total net revenue is {_fmt(rows[0][4])}.", cols, rows, sql, {}


def _top(conn, col):
    cols, rows, sql = _rows(conn, f"""SELECT {col} AS {col.lower()}, SUM(revenue) AS revenue,
        COUNT(*) AS transactions FROM sales GROUP BY {col} ORDER BY revenue DESC""")
    return cols, rows, sql


def top_product(conn, **_):
    cols, rows, sql = _top(conn, "Product")
    return f"{rows[0][0]} generated the highest revenue: {_fmt(rows[0][1])}.", cols, rows, sql, {}


def top_region(conn, **_):
    cols, rows, sql = _top(conn, "Region")
    return f"{rows[0][0]} region generated the highest sales: {_fmt(rows[0][1])}.", cols, rows, sql, {}


def top_category(conn, **_):
    cols, rows, sql = _top(conn, "Category")
    return f"{rows[0][0]} generated the highest revenue: {_fmt(rows[0][1])}.", cols, rows, sql, {}


def monthly_trend(conn, **_):
    cols, rows, sql = _rows(conn, """SELECT order_month AS month, SUM(revenue) AS revenue,
        COUNT(*) AS transactions FROM sales GROUP BY order_month ORDER BY order_month""")
    best = max(rows, key=lambda r: r[1])
    first, last = rows[0], rows[-1]
    return (f"Monthly revenue runs from {_fmt(first[1])} ({first[0]}) to {_fmt(last[1])} ({last[0]}); "
            f"peak month is {best[0]} at {_fmt(best[1])}."), cols, rows, sql, {}


def compare_months(conn, month_a=None, month_b=None, **_):
    for m in (month_a, month_b):
        if not m or not _MONTH_RE.match(m):
            raise ValueError("compare_months needs two months in YYYY-MM format")
    cols, rows, sql = _rows(conn, """SELECT order_month AS month, SUM(revenue) AS revenue
        FROM sales WHERE order_month IN (?, ?) GROUP BY order_month ORDER BY order_month""",
                            (month_a, month_b))
    found = {r[0]: r[1] for r in rows}
    missing = [m for m in (month_a, month_b) if m not in found]
    if missing:
        raise ValueError(f"No valid sales data for: {', '.join(missing)}")
    a, b = found[month_a], found[month_b]
    diff = b - a
    pct = diff / a * 100 if a else float("nan")
    word = "increased" if diff > 0 else "decreased" if diff < 0 else "did not change"
    rows.append(["change", diff])
    return (f"Revenue {word} from {_fmt(a)} in {month_a} to {_fmt(b)} in {month_b} "
            f"({diff:+,.0f}, {pct:+.1f}%)."), cols, rows, sql, {"month_a": month_a, "month_b": month_b}


INTENTS = {
    "total_revenue": total_revenue,
    "top_product": top_product,
    "top_region": top_region,
    "top_category": top_category,
    "monthly_trend": monthly_trend,
    "compare_months": compare_months,
}
