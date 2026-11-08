
import sys
from pathlib import Path
from collections import Counter

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.database.db import get_connection
from src.planning.route_planner import build_route_preview


def main():
    conn = get_connection()

    try:
        result = build_route_preview(conn, scenario_name="NORMAL")

        routes = result["routes"]
        all_stops = [
            stop
            for route in routes
            for stop in route["stops"]
        ]

        delivery_ids = [
            stop["delivery_id"]
            for stop in all_stops
        ]

        duplicates = [
            delivery_id
            for delivery_id, count in Counter(delivery_ids).items()
            if count > 1
        ]

        hard_late = [
            stop for stop in all_stops
            if stop["window_type"] == "HARD"
            and stop["lateness_minutes"] > 0
        ]

        invalid_sequence = []

        for route in routes:
            expected = list(range(1, len(route["stops"]) + 1))
            actual = [
                stop["sequence"]
                for stop in route["stops"]
            ]

            if actual != expected:
                invalid_sequence.append(route["shift_id"])

        missing_departure = [
            stop for stop in all_stops
            if stop["departure"] < stop["arrival"]
        ]

        total = result["pending_count"]
        planned = len(all_stops)
        unplanned = result["route_unplanned_count"]

        print("\n===== ROUTE PREVIEW VALIDATION =====")
        print("Pending deliveries:", total)
        print("Planned deliveries:", planned)
        print("Unplanned deliveries:", unplanned)

        print("\nVALIDATION CHECKS:")
        print("Duplicate deliveries:", len(duplicates))
        print("HARD window violations:", len(hard_late))
        print("Invalid route sequences:", len(invalid_sequence))
        print("Invalid departure times:", len(missing_departure))

        print("\nRECONCILIATION:")
        print("Planned + unplanned:", planned + unplanned)
        print("Matches pending count:", planned + unplanned == total)

        print("\nRESULT:")
        checks_passed = (
            len(duplicates) == 0
            and len(hard_late) == 0
            and len(invalid_sequence) == 0
            and len(missing_departure) == 0
            and planned + unplanned == total
        )

        print("PASS" if checks_passed else "FAIL")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
