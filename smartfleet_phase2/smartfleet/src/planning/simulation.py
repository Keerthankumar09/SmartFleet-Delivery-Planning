
import json
import random
from datetime import datetime, timedelta, timezone


SIMULATION_SEED = 20261022
FAILURE_RATE = 0.05


def _iso(value):
    return value.isoformat(timespec="seconds")


def simulate_deliveries(conn, seed=SIMULATION_SEED):
    """
    Simulate execution of persisted routes.

    Planned deliveries receive DELIVERED or FAILED outcomes.
    Deliveries without route stops receive UNSERVED outcomes.

    This simulation can run only once on the current database state.
    """

    rng = random.Random(seed)
    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    # Prevent accidental duplicate simulation.
    existing_outcomes = conn.execute(
        "SELECT COUNT(*) FROM delivery_outcomes"
    ).fetchone()[0]

    if existing_outcomes:
        raise ValueError(
            "Simulation outcomes already exist. "
            "Do not run the simulation again without resetting its records."
        )

    non_pending = conn.execute(
        """
        SELECT COUNT(*)
        FROM deliveries
        WHERE delivery_status != 'PENDING'
        """
    ).fetchone()[0]

    if non_pending:
        raise ValueError(
            "Some deliveries are no longer PENDING. "
            "Simulation stopped to protect existing data."
        )

    # Load all persisted routes and their stops.
    routes = conn.execute(
        """
        SELECT route_pk, route_id
        FROM routes
        WHERE route_status = 'PLANNED'
        ORDER BY planning_date, route_pk
        """
    ).fetchall()

    stops = conn.execute(
        """
        SELECT
            rs.stop_pk,
            rs.stop_id,
            rs.route_pk,
            rs.delivery_pk,
            rs.stop_sequence,
            rs.planned_arrival,
            rs.planned_departure,
            d.delivery_id,
            d.service_minutes
        FROM route_stops rs
        JOIN deliveries d
            ON d.delivery_pk = rs.delivery_pk
        WHERE rs.stop_status = 'PLANNED'
        ORDER BY rs.route_pk, rs.stop_sequence
        """
    ).fetchall()

    if not routes or not stops:
        raise ValueError("No planned routes or stops found.")

    # Ensure each delivery appears at most once.
    planned_delivery_pks = {row["delivery_pk"] for row in stops}

    if len(planned_delivery_pks) != len(stops):
        raise ValueError("Duplicate delivery found in route stops.")

    all_deliveries = conn.execute(
        """
        SELECT delivery_pk, delivery_id, service_minutes
        FROM deliveries
        ORDER BY delivery_pk
        """
    ).fetchall()

    route_map = {row["route_pk"]: row for row in routes}
    stops_by_route = {row["route_pk"]: [] for row in routes}

    for stop in stops:
        stops_by_route[stop["route_pk"]].append(stop)

    delivered_count = 0
    failed_count = 0
    unserved_count = 0

    print("Starting delivery simulation...")

    # Keep all database modifications atomic.
    with conn:
        # Simulate each route.
        for route_pk, route in route_map.items():
            route_stops = stops_by_route[route_pk]

            first_arrival = None
            last_departure = None
            cumulative_delay = 0

            for stop in route_stops:
                planned_arrival = datetime.fromisoformat(
                    stop["planned_arrival"]
                )

                # Simulate small execution delays, accumulating along route.
                cumulative_delay += rng.randint(0, 8)
                actual_arrival = (
                    planned_arrival + timedelta(minutes=cumulative_delay)
                )

                actual_departure = actual_arrival + timedelta(
                    minutes=stop["service_minutes"]
                )

                if first_arrival is None:
                    first_arrival = actual_arrival

                last_departure = actual_departure

                failed = rng.random() < FAILURE_RATE

                if failed:
                    final_status = "FAILED"
                    stop_status = "FAILED"
                    reason = "CUSTOMER_UNAVAILABLE"
                    failed_count += 1
                else:
                    final_status = "DELIVERED"
                    stop_status = "COMPLETED"
                    reason = "DELIVERED_SUCCESSFULLY"
                    delivered_count += 1

                delivery_pk = stop["delivery_pk"]
                delivery_id = stop["delivery_id"]

                # Update actual execution timestamps.
                conn.execute(
                    """
                    UPDATE route_stops
                    SET actual_arrival = ?,
                        actual_departure = ?,
                        stop_status = ?
                    WHERE stop_pk = ?
                    """,
                    (
                        _iso(actual_arrival),
                        _iso(actual_departure),
                        stop_status,
                        stop["stop_pk"],
                    ),
                )

                # Delivery enters transit.
                conn.execute(
                    """
                    UPDATE deliveries
                    SET delivery_status = 'IN_TRANSIT'
                    WHERE delivery_pk = ?
                    """,
                    (delivery_pk,),
                )

                conn.execute(
                    """
                    INSERT INTO delivery_events (
                        event_id,
                        delivery_pk,
                        from_status,
                        to_status,
                        event_time,
                        reason_code,
                        event_payload_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        f"SIM-{delivery_id}-TRANSIT",
                        delivery_pk,
                        "PENDING",
                        "IN_TRANSIT",
                        _iso(actual_arrival),
                        "ROUTE_STOP_REACHED",
                        json.dumps({
                            "route_id": route["route_id"],
                            "stop_sequence": stop["stop_sequence"],
                        }),
                    ),
                )

                # Final delivery status.
                conn.execute(
                    """
                    UPDATE deliveries
                    SET delivery_status = ?
                    WHERE delivery_pk = ?
                    """,
                    (final_status, delivery_pk),
                )

                conn.execute(
                    """
                    INSERT INTO delivery_events (
                        event_id,
                        delivery_pk,
                        from_status,
                        to_status,
                        event_time,
                        reason_code,
                        event_payload_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        f"SIM-{delivery_id}-FINAL",
                        delivery_pk,
                        "IN_TRANSIT",
                        final_status,
                        _iso(actual_departure),
                        reason,
                        json.dumps({
                            "route_id": route["route_id"],
                            "stop_sequence": stop["stop_sequence"],
                        }),
                    ),
                )

                # Store the outcome.
                conn.execute(
                    """
                    INSERT INTO delivery_outcomes (
                        outcome_id,
                        delivery_pk,
                        route_pk,
                        outcome_status,
                        outcome_reason,
                        attempted_at,
                        completed_at,
                        ground_truth_label,
                        created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        f"OUT-{delivery_id}",
                        delivery_pk,
                        route_pk,
                        final_status,
                        reason,
                        _iso(actual_arrival),
                        _iso(actual_departure),
                        "SIMULATED",
                        created_at,
                    ),
                )

            # Complete route execution.
            conn.execute(
                """
                UPDATE routes
                SET route_status = 'COMPLETED'
                WHERE route_pk = ?
                """,
                (route_pk,),
            )

            conn.execute(
                """
                INSERT INTO route_events (
                    event_id,
                    route_pk,
                    event_type,
                    event_time,
                    event_payload_json
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    f"SIM-{route['route_id']}-START",
                    route_pk,
                    "ROUTE_STARTED",
                    _iso(first_arrival),
                    json.dumps({"simulation_seed": seed}),
                ),
            )

            conn.execute(
                """
                INSERT INTO route_events (
                    event_id,
                    route_pk,
                    event_type,
                    event_time,
                    event_payload_json
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    f"SIM-{route['route_id']}-COMPLETE",
                    route_pk,
                    "ROUTE_COMPLETED",
                    _iso(last_departure),
                    json.dumps({
                        "stop_count": len(route_stops),
                    }),
                ),
            )

        # Deliveries without a planned route become UNSERVED.
        for delivery in all_deliveries:
            if delivery["delivery_pk"] in planned_delivery_pks:
                continue

            delivery_pk = delivery["delivery_pk"]
            delivery_id = delivery["delivery_id"]

            conn.execute(
                """
                UPDATE deliveries
                SET delivery_status = 'UNSERVED'
                WHERE delivery_pk = ?
                """,
                (delivery_pk,),
            )

            conn.execute(
                """
                INSERT INTO delivery_events (
                    event_id,
                    delivery_pk,
                    from_status,
                    to_status,
                    event_time,
                    reason_code,
                    event_payload_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"SIM-{delivery_id}-UNSERVED",
                    delivery_pk,
                    "PENDING",
                    "UNSERVED",
                    created_at,
                    "NO_FEASIBLE_ROUTE",
                    json.dumps({"simulation_seed": seed}),
                ),
            )

            conn.execute(
                """
                INSERT INTO delivery_outcomes (
                    outcome_id,
                    delivery_pk,
                    route_pk,
                    outcome_status,
                    outcome_reason,
                    attempted_at,
                    completed_at,
                    ground_truth_label,
                    created_at
                )
                VALUES (?, ?, NULL, ?, ?, NULL, NULL, ?, ?)
                """,
                (
                    f"OUT-{delivery_id}",
                    delivery_pk,
                    "UNSERVED",
                    "NO_FEASIBLE_ROUTE",
                    "SIMULATED",
                    created_at,
                ),
            )

            unserved_count += 1

    print("\n===== PHASE 7 SIMULATION COMPLETE =====")
    print(f"Routes simulated: {len(routes)}")
    print(f"Planned stops simulated: {len(stops)}")
    print(f"Delivered: {delivered_count}")
    print(f"Failed: {failed_count}")
    print(f"Unserved: {unserved_count}")
    print(f"Total outcomes: {delivered_count + failed_count + unserved_count}")
    print(f"Random seed: {seed}")

    return {
        "routes": len(routes),
        "planned_stops": len(stops),
        "delivered": delivered_count,
        "failed": failed_count,
        "unserved": unserved_count,
    }
