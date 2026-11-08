"""Validate SmartFleet transaction data."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.database.db import get_connection


EXPECTED = {
    "orders": 2000,
    "deliveries": 2000,
    "time_windows": 2000,
}


def main():
    errors = []

    with get_connection() as conn:
        print("Phase 3 transaction validation")
        print("-" * 35)

        for table, expected in EXPECTED.items():
            actual = conn.execute(
                f"SELECT COUNT(*) FROM {table}"
            ).fetchone()[0]

            print(f"{table}: {actual} (expected {expected})")

            if actual != expected:
                errors.append(
                    f"{table}: expected {expected}, found {actual}"
                )

        fk_errors = conn.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()

        print(f"Foreign-key check: {'PASS' if not fk_errors else 'FAIL'}")

        if fk_errors:
            errors.append(f"Foreign-key violations: {len(fk_errors)}")

        mismatch = conn.execute("""
            SELECT COUNT(*)
            FROM deliveries d
            JOIN orders o ON o.order_pk = d.order_pk
            WHERE d.site_pk != o.site_pk
        """).fetchone()[0]

        print(
            "Order/delivery site relationship: "
            + ("PASS" if mismatch == 0 else "FAIL")
        )

        if mismatch:
            errors.append(f"{mismatch} deliveries have mismatched sites")

        missing_windows = conn.execute("""
            SELECT COUNT(*)
            FROM deliveries d
            LEFT JOIN time_windows w
                ON w.delivery_pk = d.delivery_pk
            WHERE w.delivery_pk IS NULL
        """).fetchone()[0]

        print(
            "Delivery time-window coverage: "
            + ("PASS" if missing_windows == 0 else "FAIL")
        )

        if missing_windows:
            errors.append(f"{missing_windows} deliveries have no time window")

        invalid_windows = conn.execute("""
            SELECT COUNT(*)
            FROM time_windows
            WHERE window_end <= window_start
        """).fetchone()[0]

        print(
            "Time-window ranges: "
            + ("PASS" if invalid_windows == 0 else "FAIL")
        )

        if invalid_windows:
            errors.append(f"{invalid_windows} invalid time windows")

        duplicate_ids = conn.execute("""
            SELECT COUNT(*)
            FROM (
                SELECT order_id
                FROM orders
                GROUP BY order_id
                HAVING COUNT(*) > 1
            )
        """).fetchone()[0]

        print(
            "Duplicate order IDs: "
            + ("PASS" if duplicate_ids == 0 else "FAIL")
        )

        if duplicate_ids:
            errors.append("Duplicate order IDs found")

    print("-" * 35)

    if errors:
        print("VALIDATION FAILED")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)

    print("VALIDATION PASSED")


if __name__ == "__main__":
    main()