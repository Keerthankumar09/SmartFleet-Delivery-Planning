
from datetime import datetime, timezone

from src.planning.route_planner import (
    build_route_preview,
    load_base_travel_matrix,
)


ROUTE_ID_PREFIX = "SFL-"


def _iso(value):
    """Convert a datetime or timestamp into an ISO string."""
    if value is None:
        return None
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def save_route_preview(conn, scenario_name="NORMAL"):
    """
    Build, validate basic references, and persist route preview records.

    Existing routes created by this script are replaced on reruns.
    Other route records are left untouched.
    """

    print("Building route preview...")
    result = build_route_preview(conn, scenario_name=scenario_name)

    routes = [
        route for route in result["routes"]
        if route.get("stops")
    ]

    if not routes:
        raise ValueError("No routes with planned stops were produced.")

    # Load database ID mappings.
    shift_map = {
        row["shift_id"]: row["shift_pk"]
        for row in conn.execute(
            "SELECT shift_id, shift_pk FROM shifts"
        )
    }

    vehicle_map = {
        row["vehicle_id"]: row["vehicle_pk"]
        for row in conn.execute(
            "SELECT vehicle_id, vehicle_pk FROM vehicles"
        )
    }
    delivery_map = {
    row["delivery_id"]: row["delivery_pk"]
    for row in conn.execute(
        "SELECT delivery_id, delivery_pk FROM deliveries"
    )
    }

    distance_map = {
    (row["from_site_pk"], row["to_site_pk"]): row["distance_km"]
    for row in conn.execute(
        """
        SELECT from_site_pk, to_site_pk, distance_km
        FROM travel_time_matrix
        WHERE scenario_name = 'BASE'
        """
    )
}

    # Check references and duplicate deliveries before writing.
    seen_deliveries = set()
    prepared_routes = []

    for route in routes:
        shift_id = route["shift_id"]
        vehicle_id = route["vehicle_id"]
        planning_date = route["planning_date"]
        stops = sorted(
            route["stops"],
            key=lambda stop: stop["sequence"],
        )

        if shift_id not in shift_map:
            raise ValueError(f"Unknown shift: {shift_id}")

        if vehicle_id not in vehicle_map:
            raise ValueError(f"Unknown vehicle: {vehicle_id}")

        if len(stops) != route["stop_count"]:
            raise ValueError(
                f"Stop count mismatch for shift {shift_id}"
            )

        for stop in stops:
            delivery_id = stop["delivery_id"]

            if delivery_id not in delivery_map:
                raise ValueError(
                    f"Unknown delivery: {delivery_id}"
                )

            if delivery_id in seen_deliveries:
                raise ValueError(
                    f"Delivery appears more than once: {delivery_id}"
                )

            seen_deliveries.add(delivery_id)

        # Sum base distance between consecutive stops.
        distance_km = 0.0

        for previous, current in zip(stops, stops[1:]):
            from_site = previous["site_pk"]
            to_site = current["site_pk"]

            if from_site == to_site:
                continue

            key = (from_site, to_site)

            if key not in distance_map:
                raise ValueError(
                    f"Missing travel distance for {key}"
                )

            # Matrix values contain distance and travel minutes.
            distance_km += float(distance_map[key])

        prepared_routes.append({
            "route": route,
            "stops": stops,
            "shift_pk": shift_map[shift_id],
            "vehicle_pk": vehicle_map[vehicle_id],
            "distance_km": round(distance_km, 3),
        })

    created_at = datetime.now(timezone.utc).isoformat(
        timespec="seconds"
    )

    saved_route_count = 0
    saved_stop_count = 0

    print("Saving routes and stops...")

    # One transaction: either the complete save succeeds or none does.
    with conn:
        # Remove only records previously created by this script.
        old_routes = conn.execute(
            """
            SELECT route_pk
            FROM routes
            WHERE route_id LIKE ?
            """,
            (ROUTE_ID_PREFIX + "%",),
        ).fetchall()

        old_route_pks = [row["route_pk"] for row in old_routes]

        if old_route_pks:
            placeholders = ",".join("?" for _ in old_route_pks)

            conn.execute(
                f"""
                DELETE FROM route_stops
                WHERE route_pk IN ({placeholders})
                """,
                old_route_pks,
            )

            conn.execute(
                f"""
                DELETE FROM routes
                WHERE route_pk IN ({placeholders})
                """,
                old_route_pks,
            )

        for item in prepared_routes:
            route = item["route"]
            planning_date = route["planning_date"]
            shift_id = route["shift_id"]

            route_id = (
                f"{ROUTE_ID_PREFIX}"
                f"{planning_date.replace('-', '')}-"
                f"{shift_id}"
            )

            cursor = conn.execute(
                """
                INSERT INTO routes (
                    route_id,
                    vehicle_pk,
                    shift_pk,
                    planning_date,
                    route_status,
                    planned_distance_km,
                    planned_duration_minutes,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    route_id,
                    item["vehicle_pk"],
                    item["shift_pk"],
                    planning_date,
                    "PLANNED",
                    item["distance_km"],
                    int(round(route["duration_minutes"])),
                    created_at,
                ),
            )

            route_pk = cursor.lastrowid
            saved_route_count += 1

            for stop in item["stops"]:
                stop_id = (
                    f"{route_id}-"
                    f"S{stop['sequence']:03d}"
                )

                conn.execute(
                    """
                    INSERT INTO route_stops (
                        stop_id,
                        route_pk,
                        delivery_pk,
                        stop_sequence,
                        planned_arrival,
                        planned_departure,
                        actual_arrival,
                        actual_departure,
                        stop_status
                    )
                    VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, ?)
                    """,
                    (
                        stop_id,
                        route_pk,
                        delivery_map[stop["delivery_id"]],
                        stop["sequence"],
                        _iso(stop["arrival"]),
                        _iso(stop["departure"]),
                        "PLANNED",
                    ),
                )

                saved_stop_count += 1

        # Check foreign-key integrity before committing.
        violations = conn.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()

        if violations:
            raise ValueError(
                f"Foreign-key violations detected: {violations}"
            )

    print("\n===== PHASE 6 SAVE COMPLETE =====")
    print(f"Routes saved: {saved_route_count}")
    print(f"Route stops saved: {saved_stop_count}")
    print(f"Unique planned deliveries: {len(seen_deliveries)}")
    print(f"Traffic scenario: {scenario_name}")
    print("Delivery statuses were not changed.")

    return {
        "routes_saved": saved_route_count,
        "stops_saved": saved_stop_count,
        "deliveries_saved": len(seen_deliveries),
    }
