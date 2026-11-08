
"""Diagnose whether unplanned deliveries are individually feasible."""

import sys
from pathlib import Path
from collections import Counter
from datetime import datetime, timedelta

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.database.db import get_connection
from src.planning.assignments import assign_deliveries
from src.planning.route_planner import build_route_preview


def parse_time(value):
    return datetime.fromisoformat(value).replace(tzinfo=None)


def main():
    conn = get_connection()

    try:
        assignments_result = assign_deliveries(conn)
        preview = build_route_preview(conn, "NORMAL")

        assignment_by_delivery = {
            item["delivery_id"]: item
            for item in assignments_result["assignments"]
        }

        shift_rows = conn.execute("""
            SELECT
                sh.shift_id,
                sh.shift_start,
                sh.shift_end,
                sh.break_minutes,
                v.max_route_minutes
            FROM shifts sh
            JOIN vehicles v ON v.vehicle_pk = sh.vehicle_pk
        """).fetchall()

        shifts = {
            row["shift_id"]: dict(row)
            for row in shift_rows
        }

        individually_feasible = Counter()
        individually_infeasible = Counter()
        missing_assignment = 0

        for item in preview["route_unplanned"]:
            delivery = assignment_by_delivery.get(
                item["delivery_id"]
            )

            if delivery is None:
                missing_assignment += 1
                continue

            shift = shifts.get(item["shift_id"])

            if shift is None:
                individually_infeasible["SHIFT_NOT_FOUND"] += 1
                continue

            shift_start = parse_time(shift["shift_start"])
            shift_end = parse_time(shift["shift_end"])

            window_start = parse_time(delivery["window_start"])
            window_end = parse_time(delivery["window_end"])

            # Assume this delivery is the first stop:
            # no travel from a depot is included.
            arrival = max(shift_start, window_start)

            departure = arrival + timedelta(
                minutes=delivery["service_minutes"]
            )

            route_minutes = (
                departure - shift_start
            ).total_seconds() / 60

            latest_finish = shift_end - timedelta(
                minutes=shift["break_minutes"]
            )

            failures = []

            if (
                delivery["window_type"] == "HARD"
                and arrival > window_end
            ):
                failures.append("HARD_WINDOW_IMPOSSIBLE_ALONE")

            if departure > latest_finish:
                failures.append("SHIFT_LIMIT_IMPOSSIBLE_ALONE")

            if route_minutes > shift["max_route_minutes"]:
                failures.append("VEHICLE_LIMIT_IMPOSSIBLE_ALONE")

            if failures:
                for failure in failures:
                    individually_infeasible[failure] += 1
            else:
                individually_feasible[item["reason"]] += 1

        print("\n======= ROUTE FEASIBILITY DIAGNOSTIC =======")

        print("\nUnplanned deliveries that appear feasible individually:")
        for reason, count in sorted(individually_feasible.items()):
            print(f"{reason}: {count}")

        print("\nUnplanned deliveries that appear infeasible individually:")
        for reason, count in sorted(individually_infeasible.items()):
            print(f"{reason}: {count}")

        print(f"\nMissing assignment records: {missing_assignment}")

        print("\nInterpretation:")
        print(
            "Individually feasible deliveries may have become "
            "unplanned because of route sequencing or accumulated "
            "travel and waiting time."
        )
        print(
            "Individually infeasible deliveries may need a different "
            "shift, vehicle, or time-window assignment."
        )

        print("\n============================================")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
