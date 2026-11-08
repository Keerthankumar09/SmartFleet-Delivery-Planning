
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.database.db import get_connection


def main():
    with get_connection() as conn:

        print("\n========== DELIVERY SAMPLES ==========")

        rows = conn.execute("""
            SELECT
                d.delivery_id,
                d.delivery_status,
                d.demand_units,
                d.demand_weight_kg,
                d.required_vehicle_type,
                o.order_date,
                o.priority,
                s.site_id,
                tw.window_start,
                tw.window_end,
                tw.window_type
            FROM deliveries d
            JOIN orders o ON d.order_pk = o.order_pk
            JOIN customer_sites s ON d.site_pk = s.site_pk
            LEFT JOIN time_windows tw
                ON d.delivery_pk = tw.delivery_pk
            ORDER BY d.delivery_pk
            LIMIT 5
        """).fetchall()

        for row in rows:
            print(dict(row))

        print("\n========== VEHICLE SAMPLES ==========")

        rows = conn.execute("""
            SELECT
                v.vehicle_id,
                v.vehicle_type,
                v.max_route_minutes,
                vc.capacity_units,
                vc.capacity_weight_kg,
                vc.effective_from,
                vc.effective_to
            FROM vehicles v
            JOIN vehicle_capacities vc
                ON v.vehicle_pk = vc.vehicle_pk
            ORDER BY v.vehicle_pk
            LIMIT 5
        """).fetchall()

        for row in rows:
            print(dict(row))

        print("\n========== DRIVER SHIFT SAMPLES ==========")

        rows = conn.execute("""
            SELECT
                sh.shift_id,
                dr.driver_id,
                v.vehicle_id,
                sh.shift_start,
                sh.shift_end,
                sh.break_minutes,
                sh.shift_status
            FROM shifts sh
            JOIN drivers dr ON sh.driver_pk = dr.driver_pk
            LEFT JOIN vehicles v ON sh.vehicle_pk = v.vehicle_pk
            ORDER BY sh.shift_pk
            LIMIT 5
        """).fetchall()

        for row in rows:
            print(dict(row))

        print("\n========== VEHICLE TYPES ==========")

        rows = conn.execute("""
            SELECT vehicle_type, COUNT(*) AS total
            FROM vehicles
            GROUP BY vehicle_type
        """).fetchall()

        for row in rows:
            print(dict(row))

        print("\n========== VEHICLE RESTRICTIONS ==========")

        count = conn.execute("""
            SELECT COUNT(*) FROM vehicle_restrictions
        """).fetchone()[0]

        print("Total restrictions:", count)

        print("\n========== DELIVERY STATUS COUNTS ==========")

        rows = conn.execute("""
            SELECT delivery_status, COUNT(*) AS total
            FROM deliveries
            GROUP BY delivery_status
        """).fetchall()

        for row in rows:
            print(dict(row))


if __name__ == "__main__":
    main()
