import pytest
from fastapi.testclient import TestClient

from app.main import app, conn
from app import interpreter

client = TestClient(app)


def ask(q):
    return client.post("/api/ask", json={"question": q})


@pytest.fixture(autouse=True)
def no_llm(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


def test_total_revenue_matches_independent_calc():
    r = ask("What is the total revenue?")
    assert r.status_code == 200
    expected = conn.execute(
        "SELECT SUM(Quantity*Unit_price-Discount_amount) FROM sales_raw WHERE is_valid=1").fetchone()[0]
    assert r.json()["rows"][0][4] == expected


def test_top_product():
    r = ask("Which product generated the highest revenue?")
    assert r.status_code == 200
    assert r.json()["rows"][0][0] == "Monitor"


def test_top_region_has_supporting_rows():
    r = ask("Which region generated the highest sales?")
    assert len(r.json()["rows"]) == 4 and r.json()["sql"]


def test_monthly_trend_six_months():
    r = ask("Show me the monthly revenue trend")
    assert [x[0] for x in r.json()["rows"]] == [f"2026-0{i}" for i in range(1, 7)]


def test_compare_months():
    r = ask("How did revenue change between March and April?")
    assert r.status_code == 200
    assert r.json()["params"] == {"month_a": "2026-03", "month_b": "2026-04"}
    assert r.json()["rows"][-1][0] == "change"


def test_invalid_data_excluded():
    ids = {e["Transaction_Id"] for e in client.get("/api/data-quality").json()["excluded"]}
    assert ids == {"TXN0033", "TXN0034", "TXN0051"}  # returned, qty 0, missing price


def test_unsupported_question():
    assert ask("What is the weather in Paris?").status_code == 422


def test_empty_question():
    assert ask("   ").status_code == 400


def test_edge_month_without_data():
    r = ask("Compare revenue between March and December")
    assert r.status_code == 422 and "2026-12" in r.json()["detail"]


def test_destructive_input_is_harmless():
    r = ask("DROP TABLE sales_raw; total revenue")
    assert conn.execute("SELECT COUNT(*) FROM sales_raw").fetchone()[0] == 51
    assert r.status_code == 200  # treated as plain text, routed to a fixed query


def test_llm_output_outside_whitelist_rejected():
    assert interpreter.validate({"intent": "DROP TABLE sales"}) is None
    assert interpreter.validate({"intent": "compare_months", "params": {"sql": "x"}})["params"] == {}
