
"""Validate SmartFleet Phase 3 transaction data."""

import sys
from pathlib import Path

# Add project root to Python path.
PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.database.db import get_connection


EXPECTED_COUNTS = {
    "orders": 2000,
    "deliveries": 2000,
    "time_windows": 2000,
}


def validate_transactions():
    errors = []

    with get_connection() as conn:

        print("\n========== PHASE 3 VALIDATION ==========\n")

        # 1. Check record counts.
        print("1. RECORD COUNT CHECK")

        for table, expected in EXPECTED_COUNTS.items():
            actual = conn.execute(
                f"SELECT COUNT(*) FROM {table}"
            ).fetchone()[0]

            status = "PASS" if actual == expected else "FAIL"

            print(
                f"{table}: {actual} "
                f"(expected {expected}) - {status}"
            )

            if actual != expected:
                errors.append(
                    f"{table}: expected {expected}, found {actual}"
                )

        # 2. Check foreign-key relationships.
        print("\n2. FOREIGN KEY CHECK")

        fk_errors = conn.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()

        if fk_errors:
            print("Foreign-key check: FAIL")
            errors.append(
                f"{len(fk_errors)} foreign-key violations found"
            )
        else:
            print("Foreign-key check: PASS")

        # 3. Check order and delivery site relationships.
        print("\n3. ORDER-DELIVERY RELATIONSHIP CHECK")

        mismatch = conn.execute("""
            SELECT COUNT(*)
            FROM deliveries d
            JOIN orders o ON o.order_pk = d.order_pk
            WHERE d.site_pk != o.site_pk
        """).fetchone()[0]

        if mismatch == 0:
            print("Order/delivery site relationship: PASS")
        else:
            print(
                f"Order/delivery site relationship: FAIL "
                f"({mismatch} mismatches)"
            )
            errors.append(
                f"{mismatch} deliveries have mismatched customer sites"
            )

        # 4. Check that every delivery has a time window.
        print("\n4. TIME WINDOW COVERAGE CHECK")

        missing_windows = conn.execute("""
            SELECT COUNT(*)
            FROM deliveries d
            LEFT JOIN time_windows w
                ON w.delivery_pk = d.delivery_pk
            WHERE w.delivery_pk IS NULL
        """).fetchone()[0]

        if missing_windows == 0:
            print("Delivery time-window coverage: PASS")
        else:
            print(
                f"Delivery time-window coverage: FAIL "
                f"({missing_windows} missing)"
            )
            errors.append(
                f"{missing_windows} deliveries have no time window"
            )

        # 5. Check time-window ranges.
        print("\n5. TIME WINDOW RANGE CHECK")

        invalid_windows = conn.execute("""
            SELECT COUNT(*)
            FROM time_windows
            WHERE window_end <= window_start
        """).fetchone()[0]

        if invalid_windows == 0:
            print("Time-window ranges: PASS")
        else:
            print(
                f"Time-window ranges: FAIL "
                f"({invalid_windows} invalid)"
            )
            errors.append(
                f"{invalid_windows} invalid time windows found"
            )

        # 6. Check duplicate business IDs.
        print("\n6. DUPLICATE ID CHECK")

        duplicate_checks = {
            "orders": "order_id",
            "deliveries": "delivery_id",
            "time_windows": "window_id",
        }

        for table, column in duplicate_checks.items():
            duplicates = conn.execute(
                f"""
                SELECT COUNT(*)
                FROM (
                    SELECT {column}
                    FROM {table}
                    GROUP BY {column}
                    HAVING COUNT(*) > 1
                )
                """
            ).fetchone()[0]

            if duplicates == 0:
                print(f"{table} duplicate IDs: PASS")
            else:
                print(f"{table} duplicate IDs: FAIL")
                errors.append(
                    f"{duplicates} duplicate IDs in {table}"
                )

        # 7. Check positive demand and valid service duration.
        print("\n7. DELIVERY VALUE CHECK")

        invalid_deliveries = conn.execute("""
            SELECT COUNT(*)
            FROM deliveries
            WHERE demand_units <= 0
               OR demand_weight_kg < 0
               OR service_minutes < 0
        """).fetchone()[0]

        if invalid_deliveries == 0:
            print("Delivery demand and service values: PASS")
        else:
            print(
                f"Delivery demand and service values: FAIL "
                f"({invalid_deliveries} invalid)"
            )
            errors.append(
                f"{invalid_deliveries} deliveries contain invalid values"
            )

    # Final result.
    print("\n========================================")

    if errors:
        print("VALIDATION FAILED")
        for error in errors:
            print(f"- {error}")
        return False

    print("VALIDATION PASSED")
    print("All Phase 3 transaction checks completed successfully.")
    return True


def main():
    success = validate_transactions()

    if not success:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
