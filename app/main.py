from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from . import analytics, db, interpreter

app = FastAPI(title="Mini AI BI Assistant")
conn = db.build_db()
STATIC = Path(__file__).resolve().parent.parent / "static"

SUPPORTED = ["total revenue", "top product", "top region", "top category",
             "monthly trend", "compare two months"]


class Ask(BaseModel):
    question: str


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/data-quality")
def quality():
    return db.data_quality(conn)


@app.post("/api/ask")
def ask(body: Ask):
    q = body.question.strip()
    if not q:
        raise HTTPException(400, "Question cannot be empty.")
    if len(q) > 300:
        raise HTTPException(400, "Question too long (max 300 characters).")
    route, source = interpreter.interpret(q)
    if route is None:
        raise HTTPException(422, f"Unsupported question. I can answer: {', '.join(SUPPORTED)}.")
    try:
        answer, cols, rows, sql, params = analytics.INTENTS[route["intent"]](conn, **route["params"])
    except ValueError as e:
        raise HTTPException(422, str(e))
    return {"question": q, "intent": route["intent"], "interpreted_by": source,
            "answer": answer, "columns": cols, "rows": rows, "sql": sql,
            "params": route["params"], "data_quality": db.data_quality(conn)}
