"""Turns a natural-language question into {intent, params}.

Design choice: the LLM does NOT write SQL. It only picks one intent from a
fixed whitelist (+ month parameters). SQL is fixed and parameterised in
analytics.py, so destructive or hallucinated queries are impossible by
construction. If no API key is set (or the LLM output fails validation) a
rule-based interpreter is used instead.
"""
import json
import os
import re
import urllib.request

from .analytics import INTENTS

YEAR = 2026
MONTHS = ["january", "february", "march", "april", "may", "june", "july",
          "august", "september", "october", "november", "december"]


def extract_months(q: str):
    """Return months mentioned in the question as YYYY-MM, in order of appearance."""
    q = q.lower()
    found = []
    for m in re.finditer(r"\b(\d{4})-(\d{2})\b", q):
        found.append((m.start(), f"{m.group(1)}-{m.group(2)}"))
    for i, name in enumerate(MONTHS, 1):
        for pat in (name, name[:3]) if name != "may" else (name,):
            for m in re.finditer(rf"\b{pat}\b", q):
                found.append((m.start(), f"{YEAR}-{i:02d}"))
    found.sort()
    out = []
    for _, m in found:
        if m not in out:
            out.append(m)
    return out


def rule_based(question: str):
    q = question.lower()
    months = extract_months(q)
    if len(months) >= 2 and re.search(r"chang|compar|between|vs|versus|differ|from|grow|drop", q):
        return {"intent": "compare_months", "params": {"month_a": months[0], "month_b": months[1]}}
    if re.search(r"month|trend|over time", q):
        return {"intent": "monthly_trend", "params": {}}
    if "region" in q:
        return {"intent": "top_region", "params": {}}
    if "categor" in q:
        return {"intent": "top_category", "params": {}}
    if "product" in q or "item" in q:
        return {"intent": "top_product", "params": {}}
    if re.search(r"total|overall|revenue|sales", q):
        return {"intent": "total_revenue", "params": {}}
    return None


SYSTEM = f"""You route business questions about a sales dataset (Jan-Jun {YEAR}).
Reply with ONLY JSON: {{"intent": <one of {list(INTENTS)} or "unsupported">, "params": {{}}}}.
For compare_months set params month_a and month_b as YYYY-MM (order: earlier first as asked).
Use "unsupported" for anything not answerable by those intents. Never output SQL."""


def llm_route(question: str):
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return None
    body = json.dumps({
        "model": os.environ.get("LLM_MODEL", "claude-haiku-4-5"),
        "max_tokens": 200, "system": SYSTEM,
        "messages": [{"role": "user", "content": question}],
    }).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages", data=body,
        headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                 "content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        text = json.load(r)["content"][0]["text"]
    return json.loads(re.search(r"\{.*\}", text, re.S).group(0))


def validate(route):
    """Reject anything outside the whitelist; keep only expected params."""
    if not isinstance(route, dict):
        return None
    intent = route.get("intent")
    if intent not in INTENTS:
        return None
    params = route.get("params") or {}
    allowed = {"month_a", "month_b"} if intent == "compare_months" else set()
    return {"intent": intent, "params": {k: str(v) for k, v in params.items() if k in allowed}}


def interpret(question: str):
    """Returns (route or None, source)."""
    try:
        route = llm_route(question)
        if route and route.get("intent") == "unsupported":
            return None, "llm"
        route = validate(route)
        if route:
            return route, "llm"
    except Exception:
        pass  # network/parse failure -> fall back to rules
    return validate(rule_based(question)), "rules"
