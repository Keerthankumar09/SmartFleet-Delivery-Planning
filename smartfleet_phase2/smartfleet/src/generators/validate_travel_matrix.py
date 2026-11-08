
"""Validate SmartFleet Phase 4 travel-time data."""

import csv
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import GENERATED_DIR
from src.database.db import get_connection


EXPECTED_SITES = 500
EXPECTED_PAIRS = EXPECTED_SITES * (EXPECTED_SITES - 1)
EXPECTED_SCENARIOS = 90


def main():
    errors = []

    with get_connection() as conn:
        print("\n========== PHASE 4 VALIDATION ==========\n")

        site_count = conn.execute("""
            SELECT COUNT(*)
            FROM customer_sites
            WHERE is_active = 1
        """).fetchone()[0]

        print(f"Active sites: {site_count}")

        if site_count != EXPECTED_SITES:
            errors.append(
                f"Expected {EXPECTED_SITES} active sites, found {site_count}"
            )

        matrix_count = conn.execute("""
            SELECT COUNT(*)
            FROM travel_time_matrix
            WHERE scenario_name = 'BASE'
        """).fetchone()[0]

        print(
            f"Base travel records: {matrix_count} "
            f"(expected {EXPECTED_PAIRS})"
        )

        if matrix_count != EXPECTED_PAIRS:
            errors.append(
                f"Expected {EXPECTED_PAIRS} base records, "
                f"found {matrix_count}"
            )

        distinct_pairs = conn.execute("""
            SELECT COUNT(*)
            FROM (
                SELECT from_site_pk, to_site_pk
                FROM travel_time_matrix
                WHERE scenario_name = 'BASE'
                GROUP BY from_site_pk, to_site_pk
            )
        """).fetchone()[0]

        print(f"Unique directed pairs: {distinct_pairs}")

        if distinct_pairs != matrix_count:
            errors.append("Duplicate directed site pairs found")

        invalid_values = conn.execute("""
            SELECT COUNT(*)
            FROM travel_time_matrix
            WHERE scenario_name = 'BASE'
              AND (
                  distance_km <= 0
                  OR travel_minutes <= 0
                  OR from_site_pk = to_site_pk
              )
        """).fetchone()[0]

        print(
            "Distance and travel-time values: "
            + ("PASS" if invalid_values == 0 else "FAIL")
        )

        if invalid_values:
            errors.append(
                f"{invalid_values} invalid travel matrix records"
            )

        fk_errors = conn.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()

        print(
            "Foreign-key check: "
            + ("PASS" if not fk_errors else "FAIL")
        )

        if fk_errors:
            errors.append(
                f"{len(fk_errors)} foreign-key violations"
            )

    # Validate the daily traffic scenario manifest.
    manifest_path = GENERATED_DIR / "traffic_scenarios.csv"

    print("\nTraffic scenario manifest:")

    if not manifest_path.exists():
        errors.append("traffic_scenarios.csv is missing")
        print("Manifest: FAIL")
    else:
        with manifest_path.open(
            "r", newline="", encoding="utf-8"
        ) as file:
            scenarios = list(csv.DictReader(file))

        print(
            f"Scenario records: {len(scenarios)} "
            f"(expected {EXPECTED_SCENARIOS})"
        )

        if len(scenarios) != EXPECTED_SCENARIOS:
            errors.append(
                f"Expected {EXPECTED_SCENARIOS} scenario records, "
                f"found {len(scenarios)}"
            )

        expected_names = {"LOW", "NORMAL", "HEAVY"}

        actual_names = {
            row["scenario_name"] for row in scenarios
        }

        if actual_names != expected_names:
            errors.append("Traffic scenario names are incorrect")

        expected_dates = {
            f"2026-10-{day:02d}" for day in range(22, 32)
        } | {
            f"2026-11-{day:02d}" for day in range(1, 21)
        }

        actual_dates = {
            row["scenario_date"] for row in scenarios
        }

        if actual_dates != expected_dates:
            errors.append("Traffic scenario dates are incorrect")

        if len(scenarios) == EXPECTED_SCENARIOS:
            print("Traffic scenario dates and names: PASS")

    print("\n========================================")

    if errors:
        print("VALIDATION FAILED")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)

    print("VALIDATION PASSED")


if __name__ == "__main__":
    main()
