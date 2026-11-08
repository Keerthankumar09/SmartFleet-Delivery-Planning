
"""Constraint checking utilities for SmartFleet route planning."""

from datetime import datetime


def parse_datetime(value):
    """Convert an ISO-format timestamp into a datetime object."""
    if isinstance(value, datetime):
        return value

    return datetime.fromisoformat(value)


def check_vehicle_capacity(
    total_units,
    total_weight_kg,
    capacity_units,
    capacity_weight_kg,
):
    """Check whether total delivery demand fits vehicle capacity."""

    violations = []

    if total_units > capacity_units:
        violations.append(
            f"Unit capacity exceeded: {total_units} > {capacity_units}"
        )

    if total_weight_kg > capacity_weight_kg:
        violations.append(
            f"Weight capacity exceeded: "
            f"{total_weight_kg} > {capacity_weight_kg} kg"
        )

    return {
        "valid": len(violations) == 0,
        "violations": violations,
        "unit_utilization": round(
            total_units / capacity_units, 4
        ),
        "weight_utilization": round(
            total_weight_kg / capacity_weight_kg, 4
        ),
    }


def check_shift(route_start, route_end, shift_start, shift_end):
    """Check whether a route operates within the driver's shift."""

    route_start = parse_datetime(route_start)
    route_end = parse_datetime(route_end)
    shift_start = parse_datetime(shift_start)
    shift_end = parse_datetime(shift_end)

    violations = []

    if route_end <= route_start:
        violations.append("Route end must be after route start.")

    if route_start < shift_start:
        violations.append("Route starts before driver shift.")

    if route_end > shift_end:
        violations.append("Route ends after driver shift.")

    return {
        "valid": len(violations) == 0,
        "violations": violations,
    }


def check_time_window(arrival_time, window):
    """
    Check delivery arrival against its time window.

    HARD windows reject early or late arrival.
    SOFT windows allow it but calculate a penalty.
    """

    arrival = parse_datetime(arrival_time)
    window_start = parse_datetime(window["window_start"])
    window_end = parse_datetime(window["window_end"])

    if arrival < window_start:
        penalty = int(
            (window_start - arrival).total_seconds() // 60
        )
        violation = "Delivery arrived before its time window."

    elif arrival > window_end:
        penalty = int(
            (arrival - window_end).total_seconds() // 60
        )
        violation = "Delivery arrived after its time window."

    else:
        penalty = 0
        violation = None

    window_type = window["window_type"]

    if window_type == "HARD":
        valid = penalty == 0
    elif window_type == "SOFT":
        valid = True
    else:
        raise ValueError(f"Unknown time-window type: {window_type}")

    return {
        "valid": valid,
        "penalty_minutes": penalty,
        "violation": violation if not valid else None,
    }


def check_route_duration(
    route_start,
    route_end,
    max_route_minutes,
):
    """Check route duration against the vehicle's maximum."""

    route_start = parse_datetime(route_start)
    route_end = parse_datetime(route_end)

    duration = int(
        (route_end - route_start).total_seconds() // 60
    )

    violations = []

    if duration < 0:
        violations.append("Route end is before route start.")
    elif duration > max_route_minutes:
        violations.append(
            f"Maximum route duration exceeded: "
            f"{duration} > {max_route_minutes} minutes"
        )

    return {
        "valid": len(violations) == 0,
        "duration_minutes": duration,
        "violations": violations,
    }


def check_delivery_service(arrival_time, departure_time, service_minutes):
    """Check whether planned departure includes service duration."""

    arrival = parse_datetime(arrival_time)
    departure = parse_datetime(departure_time)

    actual_service = int(
        (departure - arrival).total_seconds() // 60
    )

    valid = (
        departure >= arrival
        and actual_service >= service_minutes
    )

    return {
        "valid": valid,
        "actual_service_minutes": actual_service,
        "violations": [] if valid else [
            "Departure does not include the required service duration."
        ],
    }
