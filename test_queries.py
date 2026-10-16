"""Run all 25 analytics queries and report row counts."""
from sql.queries import QUERIES
from utils.db_connection import run_query

ok = 0
for level, question, sql in QUERIES:
    try:
        df = run_query(sql)
        status = f"{len(df):4d} rows" if len(df) else "   EMPTY"
        ok += bool(len(df))
    except RuntimeError as e:
        status = f"ERROR: {e}"
    print(f"{question.split('.')[0]:4s} [{level:12s}] {status}")
print(f"\n{ok}/{len(QUERIES)} queries returned data")
