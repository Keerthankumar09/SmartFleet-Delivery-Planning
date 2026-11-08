from src.database.db import get_connection, initialize_database, foreign_key_violations

def main():
    initialize_database()
    conn = get_connection()
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    fk_errors = foreign_key_violations(conn)
    print(f"Tables: {len(tables)}")
    for row in tables:
        print(f" - {row['name']}")
    print(f"Foreign-key violations: {len(fk_errors)}")
    if fk_errors:
        for error in fk_errors:
            print(tuple(error))
        raise SystemExit(1)
    print("Database structure check: PASS")
    conn.close()

if __name__ == "__main__":
    main()
