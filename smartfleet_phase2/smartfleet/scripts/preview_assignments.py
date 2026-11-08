
"""Preview delivery assignments without modifying the database."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.database.db import get_connection
from src.planning.assignments import assign_deliveries


def main():
    with get_connection() as conn:
        result = assign_deliveries(conn)

    assignments = result["assignments"]
    unassigned = result["unassigned"]
    summaries = result["shift_summaries"]

    print("\n========== SMARTFLEET ASSIGNMENT PREVIEW ==========")
    print("Pending deliveries:", result["pending_count"])
    print("Assigned deliveries:", len(assignments))
    print("Unassigned deliveries:", len(unassigned))
    print("Shifts used:", len(summaries))

    if result["pending_count"]:
        percentage = (
            len(assignments) / result["pending_count"]
        ) * 100
        print(f"Assignment rate: {percentage:.2f}%")

    print("\n========== UNASSIGNED REASONS ==========")

    reason_counts = {}

    for item in unassigned:
        reason = item["reason"]
        reason_counts[reason] = reason_counts.get(reason, 0) + 1

    if reason_counts:
        for reason, count in sorted(reason_counts.items()):
            print(f"{reason}: {count}")
    else:
        print("No unassigned deliveries.")

    print("\n========== DAILY SUMMARY ==========")

    daily = {}

    for item in assignments:
        day = item["planning_date"]
        daily[day] = daily.get(day, 0) + 1

    for day, count in sorted(daily.items()):
        print(f"{day}: {count} deliveries assigned")

    print("\n========== SAMPLE ASSIGNMENTS ==========")

    for item in assignments[:10]:
        print(
            f"{item['delivery_id']} -> "
            f"{item['vehicle_id']} -> "
            f"{item['shift_id']} "
            f"({item['planning_date']})"
        )

    print("\n========== SHIFT CAPACITY SAMPLES ==========")

    for item in summaries[:10]:
        print(
            f"{item['shift_id']} | "
            f"{item['vehicle_id']} | "
            f"Deliveries: {item['delivery_count']} | "
            f"Units: {item['used_units']}/"
            f"{item['capacity_units']} | "
            f"Weight: {item['used_weight_kg']}/"
            f"{item['capacity_weight_kg']} kg"
        )

    print("\n========== DATABASE SAFETY CHECK ==========")

    with get_connection() as conn:
        status_counts = conn.execute("""
            SELECT delivery_status, COUNT(*) AS total
            FROM deliveries
            GROUP BY delivery_status
        """).fetchall()

    for row in status_counts:
        print(f"{row['delivery_status']}: {row['total']}")

    print("\nAssignment preview completed.")
    print("No database records were modified.")


if __name__ == "__main__":
    main()
