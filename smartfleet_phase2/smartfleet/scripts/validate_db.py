import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.database.db import get_connection, initialize_database, foreign_key_violations

def main():
    initialize_database()
    with get_connection() as conn:
        tables = conn.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name NOT LIKE 'sqlite_%'
            ORDER BY name
        """).fetchall()
        violations = foreign_key_violations(conn)

    print(f"Tables found: {len(tables)}")
    for row in tables:
        print(f"- {row['name']}")
    if violations:
        print(f"Foreign-key violations: {len(violations)}")
        raise SystemExit(1)
    print("Foreign-key integrity: PASS")

if __name__ == "__main__":
    main()
