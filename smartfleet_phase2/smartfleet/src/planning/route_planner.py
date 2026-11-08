
"""Deterministic, traffic-aware delivery route planning preview.

Uses the existing assignment preview and does not modify the database.
"""

import csv
from collections import defaultdict
from datetime import datetime, timedelta
from math import ceil

from config.settings import DATA_DIR
from src.planning.assignments import (
    assign_deliveries,
    PRIORITY_ORDER,
)

TRAFFIC_SCENARIO = "NORMAL"
BEAM_WIDTH =40 

def parse_timestamp(value):
    """Parse generated timestamps into naive UTC datetimes."""
    parsed = datetime.fromisoformat(value)
    return parsed.replace(tzinfo=None)


def load_traffic_multipliers(scenario_name=TRAFFIC_SCENARIO):
    """Load daily traffic multipliers from the generated CSV."""

    manifest_path = DATA_DIR / "generated" / "traffic_scenarios.csv"

    multipliers = {}

    with manifest_path.open(
        "r", encoding="utf-8", newline=""
    ) as file:
        reader = csv.DictReader(file)

        for row in reader:
            if row["scenario_name"] == scenario_name:
                multipliers[row["scenario_date"]] = float(
                    row["daily_multiplier"]
                )

    return multipliers


def load_base_travel_matrix(conn):
    """Load the compact BASE directed travel-time matrix."""

    rows = conn.execute("""
        SELECT
            from_site_pk,
            to_site_pk,
            travel_minutes
        FROM travel_time_matrix
        WHERE scenario_name = 'BASE'
    """).fetchall()

    return {
        (row["from_site_pk"], row["to_site_pk"]):
            row["travel_minutes"]
        for row in rows
    }


def evaluate_candidate(
    delivery,
    current_site_pk,
    current_time,
    shift_start,
    shift_end,
    max_route_minutes,
    break_minutes,
    travel_matrix,
    traffic_multiplier,
):
    """Check whether a delivery can be the next route stop."""

    if current_site_pk is None:
        base_travel = 0
    elif current_site_pk == delivery["site_pk"]:
        base_travel = 0
    else:
        key = (current_site_pk, delivery["site_pk"])

        if key not in travel_matrix:
            return None, "MISSING_TRAVEL_TIME"

        base_travel = travel_matrix[key]

    adjusted_travel = ceil(
        base_travel * traffic_multiplier
    )

    estimated_arrival = current_time + timedelta(
        minutes=adjusted_travel
    )

    window_start = parse_timestamp(delivery["window_start"])
    window_end = parse_timestamp(delivery["window_end"])

    # Arriving early means waiting until the window opens.
    arrival = max(estimated_arrival, window_start)

    lateness = max(
        0,
        ceil((arrival - window_end).total_seconds() / 60),
    )

    window_type = (delivery["window_type"] or "HARD").upper()

    # A HARD time window cannot be violated.
    if window_type == "HARD" and lateness > 0:
        return None, "HARD_WINDOW_MISSED"

    service_minutes = int(delivery["service_minutes"])

    departure = arrival + timedelta(
        minutes=service_minutes
    )

    elapsed_minutes = (
        departure - shift_start
    ).total_seconds() / 60

    # Reserve the driver's break at the end of the shift.
    latest_route_finish = shift_end - timedelta(
        minutes=break_minutes
    )

    if elapsed_minutes > max_route_minutes:
        return None, "VEHICLE_ROUTE_DURATION_EXCEEDED"

    if departure > latest_route_finish:
        return None, "SHIFT_OR_BREAK_LIMIT_EXCEEDED"

    wait_minutes = ceil(
        (arrival - estimated_arrival).total_seconds() / 60
    )

    result = {
    "delivery": delivery,
    "delivery_id": delivery["delivery_id"],
    "window_type": window_type,
    "travel_minutes": adjusted_travel,
    "arrival": arrival,
    "departure": departure,
    "wait_minutes": wait_minutes,
    "lateness_minutes": lateness,
}

    score = (
    lateness,
    window_end,
    adjusted_travel,
    PRIORITY_ORDER.get(delivery["priority"], 99),
    delivery["delivery_id"],
    )

    return (score, result), None



def plan_shift_route(
    deliveries,
    shift,
    travel_matrix,
    traffic_multiplier,
):
    """Build a deterministic route using bounded beam search.

    Explores multiple feasible stop sequences instead of committing
    to the locally best next stop at every iteration.
    """

    shift_start = parse_timestamp(shift["shift_start"])
    shift_end = parse_timestamp(shift["shift_end"])

    initial_state = {
        "current_site_pk": None,
        "current_time": shift_start,
        "remaining": list(deliveries),
        "planned_stops": [],
        "total_lateness": 0,
        "total_travel": 0,
        "priority_score": 0,
        "sequence_key": (),
    }

    beam = [initial_state]
    best_state = initial_state

    def state_score(state):
        """Rank states deterministically.

        Earlier completion leaves more time for subsequent deliveries.
        Lateness and travel are secondary objectives.
        """
        return (
            state["current_time"],
            state["total_lateness"],
            state["total_travel"],
            state["priority_score"],
            state["sequence_key"],
        )

    while beam:
        expanded_states = []

        for state in beam:
            candidates = []

            for delivery in state["remaining"]:
                evaluated, reason = evaluate_candidate(
                    delivery=delivery,
                    current_site_pk=state["current_site_pk"],
                    current_time=state["current_time"],
                    shift_start=shift_start,
                    shift_end=shift_end,
                    max_route_minutes=shift["max_route_minutes"],
                    break_minutes=shift["break_minutes"],
                    travel_matrix=travel_matrix,
                    traffic_multiplier=traffic_multiplier,
                )

                if evaluated is not None:
                    score, stop = evaluated
                    candidates.append((score, stop))

            candidates.sort(key=lambda item: item[0])

            for _, selected_stop in candidates:
                selected_delivery = selected_stop["delivery"]

                new_remaining = [
                    delivery
                    for delivery in state["remaining"]
                    if delivery["delivery_id"]
                    != selected_delivery["delivery_id"]
                ]

                new_planned_stops = list(state["planned_stops"])

                new_planned_stops.append({
                    "sequence": len(new_planned_stops) + 1,
                    "delivery_id": selected_delivery["delivery_id"],
                    "site_pk": selected_delivery["site_pk"],
                    "priority": selected_delivery["priority"],
                    "travel_minutes": selected_stop["travel_minutes"],
                    "wait_minutes": selected_stop["wait_minutes"],
                    "arrival": selected_stop["arrival"],
                    "departure": selected_stop["departure"],
                    "window_type": selected_delivery["window_type"],
                    "service_minutes": selected_delivery["service_minutes"],
                    "lateness_minutes": selected_stop["lateness_minutes"],
                })

                new_state = {
                    "current_site_pk": selected_delivery["site_pk"],
                    "current_time": selected_stop["departure"],
                    "remaining": new_remaining,
                    "planned_stops": new_planned_stops,
                    "total_lateness": (
                        state["total_lateness"]
                        + selected_stop["lateness_minutes"]
                    ),
                    "total_travel": (
                        state["total_travel"]
                        + selected_stop["travel_minutes"]
                    ),
                    "priority_score": (
                        state["priority_score"]
                        + PRIORITY_ORDER.get(
                            selected_delivery["priority"], 99
                        )
                    ),
                    "sequence_key": (
                        state["sequence_key"]
                        + (selected_delivery["delivery_id"],)
                    ),
                }

                expanded_states.append(new_state)

        # No sequence can add another feasible delivery.
        if not expanded_states:
            break

        expanded_states.sort(key=state_score)

        # Retain only the best candidate sequences.
        beam = expanded_states[:BEAM_WIDTH]
        best_state = beam[0]

    planned_stops = best_state["planned_stops"]
    unplanned = []

    # Explain why deliveries remaining in the best sequence could
    # not be added at the end of that sequence.
    for delivery in best_state["remaining"]:
        _, reason = evaluate_candidate(
            delivery=delivery,
            current_site_pk=best_state["current_site_pk"],
            current_time=best_state["current_time"],
            shift_start=shift_start,
            shift_end=shift_end,
            max_route_minutes=shift["max_route_minutes"],
            break_minutes=shift["break_minutes"],
            travel_matrix=travel_matrix,
            traffic_multiplier=traffic_multiplier,
        )

        unplanned.append({
            "delivery_id": delivery["delivery_id"],
            "shift_id": shift["shift_id"],
            "reason": reason or "NO_FEASIBLE_NEXT_STOP",
        })

    route = None

    if planned_stops:
        route_end = planned_stops[-1]["departure"]

        route_duration = (
            route_end - shift_start
        ).total_seconds() / 60

        route = {
            "planning_date": shift["planning_date"],
            "shift_id": shift["shift_id"],
            "vehicle_id": shift["vehicle_id"],
            "driver_pk": shift["driver_pk"],
            "stop_count": len(planned_stops),
            "route_start": shift_start,
            "route_end": route_end,
            "duration_minutes": round(route_duration, 2),
            "stops": planned_stops,
        }

    return route, unplanned


def build_route_preview(conn, scenario_name=TRAFFIC_SCENARIO):
    """Build route previews without writing anything to SQLite."""

    assignment_result = assign_deliveries(conn)

    assignments = assignment_result["assignments"]

    traffic_multipliers = load_traffic_multipliers(
        scenario_name
    )

    travel_matrix = load_base_travel_matrix(conn)

    # Group assigned deliveries by date and shift.
    deliveries_by_shift = defaultdict(list)

    for delivery in assignments:
        key = (
            delivery["planning_date"],
            delivery["shift_pk"],
        )
        deliveries_by_shift[key].append(delivery)

    # Load the shift and vehicle information needed for routing.
    shift_rows = conn.execute("""
        SELECT
            sh.shift_pk,
            sh.shift_id,
            sh.driver_pk,
            sh.shift_start,
            sh.shift_end,
            sh.break_minutes,
            v.vehicle_id,
            v.max_route_minutes
        FROM shifts sh
        JOIN vehicles v
            ON v.vehicle_pk = sh.vehicle_pk
    """).fetchall()

    shifts_by_pk = {
        row["shift_pk"]: dict(row)
        for row in shift_rows
    }

    routes = []
    route_unplanned = []

    for (planning_date, shift_pk) in sorted(
        deliveries_by_shift
    ):
        shift = shifts_by_pk.get(shift_pk)

        if shift is None:
            for delivery in deliveries_by_shift[
                (planning_date, shift_pk)
            ]:
                route_unplanned.append({
                    "delivery_id": delivery["delivery_id"],
                    "shift_id": "UNKNOWN",
                    "reason": "SHIFT_NOT_FOUND",
                })
            continue

        multiplier = traffic_multipliers.get(planning_date)

        if multiplier is None:
            for delivery in deliveries_by_shift[
                (planning_date, shift_pk)
            ]:
                route_unplanned.append({
                    "delivery_id": delivery["delivery_id"],
                    "shift_id": shift["shift_id"],
                    "reason": "MISSING_TRAFFIC_SCENARIO",
                })
            continue

        shift["planning_date"] = planning_date

        route, unplanned = plan_shift_route(
            deliveries=deliveries_by_shift[
                (planning_date, shift_pk)
            ],
            shift=shift,
            travel_matrix=travel_matrix,
            traffic_multiplier=multiplier,
        )

        if route:
            route["traffic_scenario"] = scenario_name
            route["traffic_multiplier"] = multiplier
            routes.append(route)

        route_unplanned.extend(unplanned)

    return {
        "pending_count": assignment_result["pending_count"],
        "assignment_count": len(assignments),
        "assignment_unassigned": assignment_result["unassigned"],
        "routes": routes,
        "route_unplanned": route_unplanned,
        "planned_count": sum(
            route["stop_count"] for route in routes
        ),
        "route_unplanned_count": len(route_unplanned),
    }
