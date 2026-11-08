
import sys
from pathlib import Path
from collections import Counter
from datetime import datetime, timedelta
from math import ceil

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.database.db import get_connection
from src.planning.route_planner import (
    build_route_preview,
    load_traffic_multipliers,
    load_base_travel_matrix,
)


def as_datetime(value):
    """Normalize generated timestamps to naive UTC."""
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)

    return datetime.fromisoformat(value).replace(tzinfo=None)


def add_error(errors, category, message):
    errors.append({
        "category": category,
        "message": message,
    })


def validate_route_constraints(conn, result):
    errors = []
    warnings = []

    routes = result["routes"]
    all_stops = [
        stop
        for route in routes
        for stop in route["stops"]
    ]

    planned_ids = [stop["delivery_id"] for stop in all_stops]

    route_unplanned_ids = [
        item["delivery_id"]
        for item in result["route_unplanned"]
    ]

    assignment_unplanned_ids = [
        item["delivery_id"]
        for item in result["assignment_unassigned"]
    ]

    # --------------------------------------------------
    # 1. Duplicate and reconciliation checks
    # --------------------------------------------------

    duplicate_ids = [
        delivery_id
        for delivery_id, count in Counter(planned_ids).items()
        if count > 1
    ]

    for delivery_id in duplicate_ids:
        add_error(
            errors,
            "DUPLICATE_DELIVERY",
            delivery_id,
        )

    all_accounted_ids = (
        planned_ids
        + route_unplanned_ids
        + assignment_unplanned_ids
    )

    duplicate_accounting = [
        delivery_id
        for delivery_id, count in Counter(all_accounted_ids).items()
        if count > 1
    ]

    for delivery_id in duplicate_accounting:
        add_error(
            errors,
            "DUPLICATE_ACCOUNTING",
            delivery_id,
        )

    if len(all_accounted_ids) != result["pending_count"]:
        add_error(
            errors,
            "RECONCILIATION",
            (
                f"Expected {result['pending_count']} deliveries, "
                f"accounted for {len(all_accounted_ids)}."
            ),
        )

    # --------------------------------------------------
    # 2. Load reference data
    # --------------------------------------------------

    matrix = load_base_travel_matrix(conn)

    traffic = load_traffic_multipliers("NORMAL")

    delivery_cache = {}

    def get_delivery(delivery_id):
        if delivery_id not in delivery_cache:
            delivery_cache[delivery_id] = conn.execute("""
                SELECT
                    d.delivery_id,
                    d.site_pk,
                    d.demand_units,
                    d.demand_weight_kg,
                    d.service_minutes,
                    tw.window_start,
                    tw.window_end,
                    tw.window_type
                FROM deliveries d
                LEFT JOIN time_windows tw
                    ON tw.delivery_pk = d.delivery_pk
                WHERE d.delivery_id = ?
            """, (delivery_id,)).fetchone()

        return delivery_cache[delivery_id]

    # --------------------------------------------------
    # 3. Validate every route
    # --------------------------------------------------

    soft_late_count = 0
    maximum_soft_lateness = 0

    for route in routes:
        shift_id = route["shift_id"]
        planning_date = route["planning_date"]

        shift = conn.execute("""
            SELECT
                sh.shift_start,
                sh.shift_end,
                sh.break_minutes,
                sh.vehicle_pk,
                v.vehicle_id,
                v.max_route_minutes
            FROM shifts sh
            JOIN vehicles v
                ON v.vehicle_pk = sh.vehicle_pk
            WHERE sh.shift_id = ?
        """, (shift_id,)).fetchone()

        if shift is None:
            add_error(
                errors,
                "SHIFT_NOT_FOUND",
                shift_id,
            )
            continue

        if shift["vehicle_id"] != route["vehicle_id"]:
            add_error(
                errors,
                "VEHICLE_MISMATCH",
                shift_id,
            )

        shift_start = as_datetime(shift["shift_start"])
        shift_end = as_datetime(shift["shift_end"])

        latest_finish = (
            shift_end
            - timedelta(minutes=shift["break_minutes"])
        )

        # --------------------------------------------------
        # 3A. Check effective vehicle capacity
        # --------------------------------------------------

        capacity = conn.execute("""
            SELECT
                capacity_units,
                capacity_weight_kg
            FROM vehicle_capacities
            WHERE vehicle_pk = ?
              AND effective_from <= ?
              AND (
                    effective_to IS NULL
                    OR effective_to > ?
              )
            ORDER BY effective_from DESC
            LIMIT 1
        """, (
            shift["vehicle_pk"],
            planning_date,
            planning_date,
        )).fetchone()

        if capacity is None:
            add_error(
                errors,
                "MISSING_VEHICLE_CAPACITY",
                shift_id,
            )
        else:
            total_units = 0.0
            total_weight = 0.0

            for stop in route["stops"]:
                delivery = get_delivery(stop["delivery_id"])

                if delivery is None:
                    add_error(
                        errors,
                        "DELIVERY_NOT_FOUND",
                        stop["delivery_id"],
                    )
                    continue

                total_units += float(delivery["demand_units"])
                total_weight += float(delivery["demand_weight_kg"])

            if total_units > float(capacity["capacity_units"]) + 1e-9:
                add_error(
                    errors,
                    "CAPACITY_UNITS_EXCEEDED",
                    (
                        f"{shift_id}: {total_units} used, "
                        f"{capacity['capacity_units']} available."
                    ),
                )

            if total_weight > float(capacity["capacity_weight_kg"]) + 1e-9:
                add_error(
                    errors,
                    "CAPACITY_WEIGHT_EXCEEDED",
                    (
                        f"{shift_id}: {total_weight} kg used, "
                        f"{capacity['capacity_weight_kg']} kg available."
                    ),
                )

        # --------------------------------------------------
        # 3B. Check route duration and shift limits
        # --------------------------------------------------

        route_start = as_datetime(route["route_start"])
        route_end = as_datetime(route["route_end"])

        actual_duration = (
            route_end - shift_start
        ).total_seconds() / 60

        if route_start != shift_start:
            add_error(
                errors,
                "ROUTE_START_MISMATCH",
                shift_id,
            )

        if actual_duration > shift["max_route_minutes"]:
            add_error(
                errors,
                "MAX_ROUTE_DURATION_EXCEEDED",
                shift_id,
            )

        if route_end > latest_finish:
            add_error(
                errors,
                "SHIFT_OR_BREAK_LIMIT_EXCEEDED",
                shift_id,
            )

        if abs(
            actual_duration - route["duration_minutes"]
        ) > 0.01:
            add_error(
                errors,
                "ROUTE_DURATION_MISMATCH",
                shift_id,
            )

        if route["stops"]:
            if route_end != as_datetime(
                route["stops"][-1]["departure"]
            ):
                add_error(
                    errors,
                    "ROUTE_END_MISMATCH",
                    shift_id,
                )

        # --------------------------------------------------
        # 3C. Check stop sequence and timing
        # --------------------------------------------------

        expected_sequence = list(
            range(1, len(route["stops"]) + 1)
        )

        actual_sequence = [
            stop["sequence"]
            for stop in route["stops"]
        ]

        if actual_sequence != expected_sequence:
            add_error(
                errors,
                "INVALID_STOP_SEQUENCE",
                shift_id,
            )

        previous_site_pk = None
        previous_departure = shift_start

        multiplier = traffic.get(planning_date)

        if multiplier is None:
            add_error(
                errors,
                "MISSING_TRAFFIC_MULTIPLIER",
                planning_date,
            )
            continue

        for stop in route["stops"]:
            delivery = get_delivery(stop["delivery_id"])

            if delivery is None:
                continue

            current_site_pk = delivery["site_pk"]

            # First stop uses the documented open-route
            # assumption: no depot-to-first-stop travel.
            if previous_site_pk is None:
                base_travel = 0

            elif previous_site_pk == current_site_pk:
                base_travel = 0

            else:
                key = (previous_site_pk, current_site_pk)

                if key not in matrix:
                    add_error(
                        errors,
                        "MISSING_TRAVEL_TIME",
                        (
                            f"{shift_id}: "
                            f"{previous_site_pk} -> {current_site_pk}"
                        ),
                    )
                    previous_site_pk = current_site_pk
                    previous_departure = as_datetime(
                        stop["departure"]
                    )
                    continue

                base_travel = matrix[key]

            expected_travel = ceil(
                base_travel * multiplier
            )

            if stop["travel_minutes"] != expected_travel:
                add_error(
                    errors,
                    "TRAVEL_TIME_MISMATCH",
                    stop["delivery_id"],
                )

            arrival = as_datetime(stop["arrival"])
            departure = as_datetime(stop["departure"])

            estimated_arrival = (
                previous_departure
                + timedelta(minutes=expected_travel)
            )

            window_start = as_datetime(
                delivery["window_start"]
            )

            window_end = as_datetime(
                delivery["window_end"]
            )

            expected_arrival = max(
                estimated_arrival,
                window_start,
            )

            if arrival != expected_arrival:
                add_error(
                    errors,
                    "ARRIVAL_TIME_MISMATCH",
                    stop["delivery_id"],
                )

            service_minutes = int(
                delivery["service_minutes"]
            )

            expected_departure = (
                arrival
                + timedelta(minutes=service_minutes)
            )

            if departure != expected_departure:
                add_error(
                    errors,
                    "SERVICE_TIME_MISMATCH",
                    stop["delivery_id"],
                )

            if departure < arrival:
                add_error(
                    errors,
                    "INVALID_DEPARTURE_TIME",
                    stop["delivery_id"],
                )

            lateness = max(
                0,
                ceil(
                    (arrival - window_end).total_seconds()
                    / 60
                ),
            )

            window_type = (
                delivery["window_type"] or "HARD"
            ).upper()

            if window_type == "HARD" and lateness > 0:
                add_error(
                    errors,
                    "HARD_WINDOW_VIOLATION",
                    stop["delivery_id"],
                )

            if stop["lateness_minutes"] != lateness:
                add_error(
                    errors,
                    "LATENESS_CALCULATION_MISMATCH",
                    stop["delivery_id"],
                )

            if window_type == "SOFT" and lateness > 0:
                soft_late_count += 1
                maximum_soft_lateness = max(
                    maximum_soft_lateness,
                    lateness,
                )

            previous_site_pk = current_site_pk
            previous_departure = departure

    # --------------------------------------------------
    # 4. Summarize SOFT-window lateness
    # --------------------------------------------------

    if soft_late_count:
        warnings.append(
            f"{soft_late_count} SOFT-window deliveries are late."
        )

        warnings.append(
            f"Maximum SOFT-window lateness: "
            f"{maximum_soft_lateness} minutes."
        )

    return {
        "errors": errors,
        "warnings": warnings,
        "planned_count": len(all_stops),
        "route_count": len(routes),
        "soft_late_count": soft_late_count,
        "maximum_soft_lateness": maximum_soft_lateness,
    }


def main():
    conn = get_connection()

    try:
        print("\nBuilding route preview...")

        result = build_route_preview(
            conn,
            scenario_name="NORMAL",
        )

        print("Running independent constraint validation...")

        validation = validate_route_constraints(
            conn,
            result,
        )

        print("\n===== PHASE 5.4 VALIDATION =====")

        print("Pending deliveries:", result["pending_count"])
        print("Routes checked:", validation["route_count"])
        print("Planned deliveries:", validation["planned_count"])
        print(
            "Route-stage unplanned:",
            result["route_unplanned_count"],
        )
        print(
            "Assignment-stage unassigned:",
            len(result["assignment_unassigned"]),
        )

        print("\nVALIDATION ERRORS:")

        if validation["errors"]:
            counts = Counter(
                error["category"]
                for error in validation["errors"]
            )

            for category, count in sorted(counts.items()):
                print(f"{category}: {count}")

            print("\nFirst 10 error examples:")

            for error in validation["errors"][:10]:
                print(
                    f"- {error['category']}: "
                    f"{error['message']}"
                )
        else:
            print("None")

        print("\nWARNINGS:")

        if validation["warnings"]:
            for warning in validation["warnings"]:
                print("-", warning)
        else:
            print("None")

        print("\nFINAL RESULT:")

        if validation["errors"]:
            print("FAIL - Fix validation errors before proceeding.")
        else:
            print("PASS - All independent constraint checks passed.")

        print(
            "\nDatabase delivery statuses remain unchanged "
            "because this is a preview-only validation."
        )

    finally:
        conn.close()


if __name__ == "__main__":
    main()
