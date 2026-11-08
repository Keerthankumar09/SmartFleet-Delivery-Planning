
import csv
import sqlite3
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import GENERATED_DIR
from src.database.db import get_connection

EXPECTED_SITES = 500
EXPECTED_MATRIX_ROWS = EXPECTED_SITES * (EXPECTED_SITES - 1)
EXPECTED_SCENARIO_ROWS = 90


def main():
    errors = []

    with get_connection() as conn:
        site_count = conn.execute(
            "SELECT COUNT(*) FROM customer_sites WHERE is_active = 1"
        ).fetchone()[0]

        matrix_count = conn.execute(
            """
            SELECT COUNT(*) FROM travel_time_matrix
            WHERE scenario_name = 'BASE'
            """
        ).fetchone()[0]

        distinct_pairs = conn.execute(
            """
            SELECT COUNT(*) FROM (
                SELECT from_site_pk, to_site_pk
                FROM travel_time_matrix
                WHERE scenario_name = 'BASE'
                GROUP BY from_site_pk, to_site_pk
            )
            """
        ).fetchone()[0]

        invalid_values = conn.execute(
            """
            SELECT COUNT(*) FROM travel_time_matrix
            WHERE scenario_name = 'BASE'
              AND (
                  distance_km <= 0
                  OR travel_minutes <= 0
                  OR from_site_pk = to_site_pk
              )
            """
        ).fetchone()[0]

        fk_errors = conn.execute("PRAGMA foreign_key_check").fetchall()

    print("TRAVEL MATRIX VALIDATION")
    print("------------------------")

    print(f"Active sites: {site_count}")
    if site_count != EXPECTED_SITES:
        errors.append("Expected 500 active customer sites.")

    print(f"Base matrix rows: {matrix_count}")
    if matrix_count != EXPECTED_MATRIX_ROWS:
        errors.append(
            f"Expected {EXPECTED_MATRIX_ROWS} base matrix rows."
        )

    print(f"Unique directed pairs: {distinct_pairs}")
    if distinct_pairs != EXPECTED_MATRIX_ROWS:
        errors.append("Missing or duplicate directed site pairs.")

    print(f"Invalid matrix records: {invalid_values}")
    if invalid_values:
        errors.append("Invalid distance, travel time, or self-pair found.")

    print(f"Foreign-key violations: {len(fk_errors)}")
    if fk_errors:
        errors.append("Foreign-key violations found.")

    manifest_path = GENERATED_DIR / "traffic_scenarios.csv"
    print(f"Scenario manifest: {manifest_path}")

    if not manifest_path.exists():
        errors.append("traffic_scenarios.csv is missing.")
    else:
        with manifest_path.open(
            "r", newline="", encoding="utf-8"
        ) as file:
            rows = list(csv.DictReader(file))

        print(f"Traffic scenario records: {len(rows)}")

        if len(rows) != EXPECTED_SCENARIO_ROWS:
            errors.append("Expected 90 traffic scenario records.")

        expected_names = {"LOW", "NORMAL", "HEAVY"}
        actual_names = {row["scenario_name"] for row in rows}

        if actual_names != expected_names:
            errors.append("Unexpected traffic scenario names.")

        expected_dates = {
            f"2026-10-{day:02d}" for day in range(22, 32)
        } | {
            f"2026-11-{day:02d}" for day in range(1, 21)
        }

        actual_dates = {row["scenario_date"] for row in rows}

        if actual_dates != expected_dates:
            errors.append("Scenario dates do not cover the expected 30 days.")

        if any(
            not 0 < float(row["daily_multiplier"]) <= 2
            for row in rows
        ):
            errors.append("Invalid daily traffic multiplier.")

    if errors:
        print("\nVALIDATION FAILED")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)

    print("\nVALIDATION PASSED")


if __name__ == "__main__":
    main()
