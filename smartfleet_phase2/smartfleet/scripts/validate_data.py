"""Validate generated master-data counts and basic integrity."""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.database.db import get_connection

EXPECTED = {
    "customer_sites": 500,
    "vehicles": 100,
    "vehicle_capacities": 100,
    "drivers": 100,
    "shifts": 3000,
}


def main():
    errors = []
    with get_connection() as conn:
        for table, expected in EXPECTED.items():
            actual = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            print(f"{table}: {actual} (expected {expected})")
            if actual != expected:
                errors.append(f"{table}: expected {expected}, found {actual}")

        fk_errors = conn.execute("PRAGMA foreign_key_check").fetchall()
        if fk_errors:
            errors.append(f"Foreign-key violations: {len(fk_errors)}")
        else:
            print("Foreign-key check: PASS")

        site_bounds = conn.execute("""
            SELECT COUNT(*) FROM customer_sites
            WHERE latitude NOT BETWEEN 15.5 AND 17.5
               OR longitude NOT BETWEEN 80.5 AND 82.5
        """).fetchone()[0]
        if site_bounds:
            errors.append(f"{site_bounds} sites fall outside the configured region")
        else:
            print("Coordinate bounds: PASS")

        invalid_shifts = conn.execute("""
            SELECT COUNT(*) FROM shifts WHERE shift_end <= shift_start
        """).fetchone()[0]
        if invalid_shifts:
            errors.append(f"{invalid_shifts} shifts have invalid time ranges")
        else:
            print("Shift time ranges: PASS")

    if errors:
        print("\\nVALIDATION FAILED")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)
    print("\\nVALIDATION PASSED")


if __name__ == "__main__":
    main()
