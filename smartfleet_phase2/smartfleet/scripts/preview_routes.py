
"""Run the SmartFleet route-planning preview."""
"""Run the SmartFleet route-planning preview."""

import sys
from pathlib import Path
from collections import Counter

# Add the project root to Python's import path.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.database.db import get_connection
from src.planning.route_planner import build_route_preview


def main():
    conn = get_connection()

    try:
        result = build_route_preview(
            conn,
            scenario_name="NORMAL",
        )

        status_counts = conn.execute("""
            SELECT delivery_status, COUNT(*)
            FROM deliveries
            GROUP BY delivery_status
        """).fetchall()

    finally:
        conn.close()

    total_unplanned = (
        len(result["assignment_unassigned"])
        + result["route_unplanned_count"]
    )

    print("\n========== SMARTFLEET ROUTE PREVIEW ==========")

    print(f"Pending deliveries: {result['pending_count']}")
    print(f"Preliminary assignments: {result['assignment_count']}")
    print(f"Routes created in preview: {len(result['routes'])}")
    print(f"Successfully planned stops: {result['planned_count']}")
    print(f"Route-stage unplanned: {result['route_unplanned_count']}")
    print(f"Assignment-stage unassigned: {len(result['assignment_unassigned'])}")
    print(f"Total unplanned: {total_unplanned}")

    print("\nTRAFFIC SCENARIO: NORMAL")

    print("\nROUTE SUMMARY:")

    for route in result["routes"][:10]:
        print(
            f"{route['planning_date']} | "
            f"{route['shift_id']} | "
            f"{route['vehicle_id']} | "
            f"Stops: {route['stop_count']} | "
            f"Duration: {route['duration_minutes']} min | "
            f"Traffic multiplier: {route['traffic_multiplier']}"
        )

    if len(result["routes"]) > 10:
        print(f"... and {len(result['routes']) - 10} more routes")

    print("\nFIRST 10 PLANNED STOPS:")

    displayed = 0

    for route in result["routes"]:
        for stop in route["stops"]:
            print(
                f"{route['planning_date']} | "
                f"{route['shift_id']} | "
                f"Stop {stop['sequence']} | "
                f"{stop['delivery_id']} | "
                f"Travel: {stop['travel_minutes']} min | "
                f"Wait: {stop['wait_minutes']} min | "
                f"Arrival: {stop['arrival']} | "
                f"Departure: {stop['departure']} | "
                f"Window: {stop['window_type']} | "
                f"Late: {stop['lateness_minutes']} min"
            )

            displayed += 1

            if displayed >= 10:
                break

        if displayed >= 10:
            break

    print("\nUNPLANNED REASONS:")

    reasons = Counter(
        item["reason"]
        for item in (
            result["assignment_unassigned"]
            + result["route_unplanned"]
        )
    )

    if reasons:
        for reason, count in sorted(reasons.items()):
            print(f"{reason}: {count}")
    else:
        print("No unplanned deliveries.")

    print("\nDATABASE DELIVERY STATUSES:")

    for row in status_counts:
        print(f"{row[0]}: {row[1]}")

    print("\n==============================================")
    print("Preview completed. No database records were modified.")


if __name__ == "__main__":
    main()
