
import sys
import csv
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.database.db import get_connection
from src.planning.route_planner import (
    build_route_preview,
    load_traffic_multipliers,
)


def main():
    conn = get_connection()

    try:
        print("\nBuilding NORMAL traffic route preview...")

        result = build_route_preview(
            conn,
            scenario_name="NORMAL",
        )

        traffic = load_traffic_multipliers("NORMAL")

        late_deliveries = []

        for route in result["routes"]:
            planning_date = route["planning_date"]

            for stop in route["stops"]:
                if stop["window_type"] != "SOFT":
                    continue

                lateness = int(stop["lateness_minutes"])

                if lateness <= 0:
                    continue

                delivery = conn.execute("""
                    SELECT
                        d.delivery_id,
                        o.priority,
                        tw.window_start,
                        tw.window_end,
                        tw.window_type
                    FROM deliveries d
                    JOIN orders o
                        ON o.order_pk = d.order_pk
                    JOIN time_windows tw
                        ON tw.delivery_pk = d.delivery_pk
                    WHERE d.delivery_id = ?
                """, (stop["delivery_id"],)).fetchone()

                if delivery is None:
                    continue

                late_deliveries.append({
                    "planning_date": planning_date,
                    "delivery_id": delivery["delivery_id"],
                    "priority": delivery["priority"],
                    "shift_id": route["shift_id"],
                    "vehicle_id": route["vehicle_id"],
                    "window_start": delivery["window_start"],
                    "window_end": delivery["window_end"],
                    "actual_arrival": stop["arrival"].isoformat(
                        sep=" "
                    ),
                    "lateness_minutes": lateness,
                    "lateness_hours": round(
                        lateness / 60, 2
                    ),
                    "traffic_scenario": "NORMAL",
                    "traffic_multiplier": traffic[planning_date],
                })

        late_deliveries.sort(
            key=lambda item: (
                -item["lateness_minutes"],
                item["planning_date"],
                item["delivery_id"],
            )
        )

        export_dir = PROJECT_ROOT / "data" / "exports"
        export_dir.mkdir(parents=True, exist_ok=True)

        report_path = (
            export_dir / "soft_window_lateness.csv"
        )

        fieldnames = [
            "planning_date",
            "delivery_id",
            "priority",
            "shift_id",
            "vehicle_id",
            "window_start",
            "window_end",
            "actual_arrival",
            "lateness_minutes",
            "lateness_hours",
            "traffic_scenario",
            "traffic_multiplier",
        ]

        with report_path.open(
            "w",
            newline="",
            encoding="utf-8",
        ) as csvfile:

            writer = csv.DictWriter(
                csvfile,
                fieldnames=fieldnames,
            )

            writer.writeheader()
            writer.writerows(late_deliveries)

        print("\n===== SOFT WINDOW LATENESS REPORT =====")

        print(
            "Total pending deliveries:",
            result["pending_count"],
        )

        print(
            "Planned deliveries:",
            result["planned_count"],
        )

        print(
            "Late SOFT-window deliveries:",
            len(late_deliveries),
        )

        print("\nTOP 10 LATE DELIVERIES:")

        for item in late_deliveries[:10]:
            print(
                f"{item['delivery_id']} | "
                f"Priority: {item['priority']} | "
                f"Vehicle: {item['vehicle_id']} | "
                f"Late: {item['lateness_minutes']} min | "
                f"Arrival: {item['actual_arrival']}"
            )

        if late_deliveries:
            maximum = max(
                item["lateness_minutes"]
                for item in late_deliveries
            )

            average = sum(
                item["lateness_minutes"]
                for item in late_deliveries
            ) / len(late_deliveries)

            print("\nLATENESS STATISTICS:")
            print("Maximum lateness:", maximum, "minutes")
            print("Average lateness:", round(average, 2), "minutes")

        print("\nCSV REPORT CREATED:")
        print(report_path)

        print("\nDatabase records were not modified.")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
