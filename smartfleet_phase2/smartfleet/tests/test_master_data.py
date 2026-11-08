import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.database.db import get_connection, initialize_database
from src.generators.master_data import generate_master_data


def test_master_data_counts_and_relationships():
    initialize_database()
    with get_connection() as conn:
        # This test database is the project DB; clear only the master tables
        # and their dependent records to keep the test repeatable.
        for table in [
            "delivery_events", "route_events", "delivery_outcomes", "route_stops",
            "routes", "time_windows", "travel_time_matrix", "vehicle_restrictions",
            "ground_truth", "deliveries", "orders", "shifts",
            "vehicle_capacities", "drivers", "vehicles", "customer_sites",
        ]:
            conn.execute(f"DELETE FROM {table}")
        counts = generate_master_data(conn, seed=123)
        conn.commit()

        assert counts == {
            "customer_sites": 500,
            "vehicles": 100,
            "vehicle_capacities": 100,
            "drivers": 100,
            "shifts": 3000,
        }
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        assert conn.execute("""
            SELECT COUNT(*) FROM shifts s
            LEFT JOIN drivers d ON d.driver_pk = s.driver_pk
            LEFT JOIN vehicles v ON v.vehicle_pk = s.vehicle_pk
            WHERE d.driver_pk IS NULL OR v.vehicle_pk IS NULL
        """).fetchone()[0] == 0
