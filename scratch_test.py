import requests, time

base = "http://127.0.0.1:8000"

tests = [
    # Structured / PostgreSQL
    {"q": "how many tickets are in the database?",     "expect": "structured"},
    {"q": "show me tickets by department",              "expect": "structured"},
    {"q": "list open unresolved tickets",               "expect": "structured"},
    {"q": "breakdown of tickets by priority",           "expect": "structured"},
    {"q": "how many tickets does engineering have?",    "expect": "structured"},
    {"q": "give me recent tickets",                     "expect": "structured"},
    {"q": "which department has the most critical tickets?", "expect": "structured"},
    # RAG / documents
    {"q": "what about audit logs?",                     "expect": "semantic"},
    {"q": "what projects are listed in the resume?",    "expect": "semantic"},
]

for t in tests:
    t0 = time.time()
    try:
        r = requests.post(
            f"{base}/v1/ask",
            json={"question": t["q"], "retrieval_mode": "hybrid"},
            timeout=200,
        )
        d = r.json()
        route = d.get("route", "?")
        answer = d.get("answer", "")[:130].replace("\n", " ")
        conf = d.get("confidence", {}).get("composite", 0)
        sql = d.get("sql_query") or ""
        ok = "OK" if route == t["expect"] else "WRONG"
        elapsed = time.time() - t0
        print(f"[{ok}][{route}] ({elapsed:.0f}s) {t['q'][:55]}")
        print(f"  Answer: {answer}")
        if sql:
            print(f"  SQL: {sql[:110]}")
    except Exception as e:
        print(f"[ERR] {t['q']}: {e}")
    print()
