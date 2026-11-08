from src.database.db import get_connection, initialize_database

def test_schema_initializes_and_has_core_entities():
    initialize_database()
    conn = get_connection()
    names = {
        row["name"] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    expected = {
        "customer_sites", "orders", "deliveries", "vehicles",
        "vehicle_capacities", "drivers", "shifts", "travel_time_matrix",
        "time_windows", "routes", "route_stops", "delivery_outcomes"
    }
    assert expected.issubset(names)
    conn.close()

def test_foreign_keys_are_enabled():
    conn = get_connection()
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    conn.close()
