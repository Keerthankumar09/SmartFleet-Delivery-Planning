
"""Deterministic, capacity-aware delivery-to-shift assignment."""

from collections import defaultdict
from datetime import date, datetime


PRIORITY_ORDER = {
    "URGENT": 0,
    "HIGH": 1,
    "NORMAL": 2,
    "LOW": 3,
}


def _as_utc_naive(value):
    """Normalize timestamps to naive UTC for comparison.

    Naive shift timestamps are interpreted as UTC, matching
    the generated synthetic planning timestamps.
    """
    parsed = datetime.fromisoformat(value)
    return parsed.replace(tzinfo=None)

def _date_is_active(effective_from, effective_to, planning_date):
    """Check an effective date range; effective_to is exclusive."""
    if effective_from > planning_date:
        return False

    if effective_to and planning_date >= effective_to:
        return False

    return True


def load_planning_data(conn):
    """Load pending deliveries and eligible vehicle shifts."""

    deliveries = conn.execute("""
        SELECT
            d.delivery_pk,
            d.delivery_id,
            d.site_pk,
            d.demand_units,
            d.demand_weight_kg,
            d.service_minutes,
            d.required_vehicle_type,
            o.order_date,
            o.priority,
            tw.window_start,
            tw.window_end,
            tw.window_type
        FROM deliveries d
        JOIN orders o ON o.order_pk = d.order_pk
        LEFT JOIN time_windows tw
            ON tw.delivery_pk = d.delivery_pk
        WHERE d.delivery_status = 'PENDING'
        ORDER BY d.delivery_pk
    """).fetchall()

    shifts = conn.execute("""
        SELECT
            sh.shift_pk,
            sh.shift_id,
            sh.driver_pk,
            sh.vehicle_pk,
            sh.shift_start,
            sh.shift_end,
            sh.break_minutes,
            sh.shift_status,
            dr.is_active AS driver_active,
            v.vehicle_id,
            v.vehicle_type,
            v.max_route_minutes,
            v.is_active AS vehicle_active,
            vc.capacity_units,
            vc.capacity_weight_kg,
            vc.effective_from,
            vc.effective_to
        FROM shifts sh
        JOIN drivers dr ON dr.driver_pk = sh.driver_pk
        JOIN vehicles v ON v.vehicle_pk = sh.vehicle_pk
        JOIN vehicle_capacities vc
            ON vc.vehicle_pk = v.vehicle_pk
        WHERE dr.is_active = 1
          AND v.is_active = 1
          AND sh.shift_status != 'CANCELLED'
        ORDER BY sh.shift_start, sh.shift_id
    """).fetchall()

    restrictions = conn.execute("""
        SELECT
            vehicle_pk,
            site_pk,
            effective_from,
            effective_to
        FROM vehicle_restrictions
    """).fetchall()

    return deliveries, shifts, restrictions


def assign_deliveries(conn):
    """
    Assign pending deliveries to vehicle shifts.

    This is a planning preview only. It does not write assignments
    or change delivery statuses in the database.
    """

    deliveries, shifts, restrictions = load_planning_data(conn)

    restrictions_by_vehicle_site = defaultdict(list)

    for restriction in restrictions:
        key = (
            restriction["vehicle_pk"],
            restriction["site_pk"],
        )
        restrictions_by_vehicle_site[key].append(restriction)

    shifts_by_date = defaultdict(list)

    for shift in shifts:
        shift_date = shift["shift_start"][:10]

        if not shift["vehicle_pk"]:
            continue

        if not _date_is_active(
            shift["effective_from"],
            shift["effective_to"],
            shift_date,
        ):
            continue

        shift_start = _as_utc_naive(shift["shift_start"])
        shift_end = _as_utc_naive(shift["shift_end"])

        available_minutes = (
            shift_end - shift_start
        ).total_seconds() / 60 - shift["break_minutes"]

        if available_minutes <= 0:
            continue

        shifts_by_date[shift_date].append({
            "shift": shift,
            "shift_start": shift_start,
            "shift_end": shift_end,
            "capacity_units": float(shift["capacity_units"]),
            "capacity_weight_kg": float(
                shift["capacity_weight_kg"]
            ),
            "used_units": 0.0,
            "used_weight_kg": 0.0,
            "used_service_minutes": 0,
            "available_minutes": available_minutes,
            "assigned_deliveries": [],
        })

    deliveries_by_date = defaultdict(list)

    for delivery in deliveries:
        deliveries_by_date[delivery["order_date"]].append(delivery)

    assignments = []
    unassigned = []

    for planning_date in sorted(deliveries_by_date):
        daily_shifts = shifts_by_date.get(planning_date, [])

        daily_deliveries = sorted(
            deliveries_by_date[planning_date],
            key=lambda d: (
                PRIORITY_ORDER.get(d["priority"], 99),
                d["window_start"] or "9999",
                d["delivery_id"],
            ),
        )

        for delivery in daily_deliveries:

            if not delivery["window_start"] or not delivery["window_end"]:
                unassigned.append({
                    "delivery_id": delivery["delivery_id"],
                    "reason": "MISSING_TIME_WINDOW",
                })
                continue

            window_start = _as_utc_naive(
                delivery["window_start"]
            )
            window_end = _as_utc_naive(
                delivery["window_end"]
            )

            candidates = []

            for state in daily_shifts:
                shift = state["shift"]

                if (
                    delivery["required_vehicle_type"]
                    and delivery["required_vehicle_type"]
                    != shift["vehicle_type"]
                ):
                    continue

                # A shift must overlap the delivery window.
                if (
                    window_end < state["shift_start"]
                    or window_start > state["shift_end"]
                ):
                    continue

                # Reject a vehicle if an active restriction
                # applies to this delivery's customer site.
                restriction_key = (
                    shift["vehicle_pk"],
                    delivery["site_pk"],
                )

                blocked = any(
                    _date_is_active(
                        item["effective_from"],
                        item["effective_to"],
                        planning_date,
                    )
                    for item in restrictions_by_vehicle_site.get(
                        restriction_key, []
                    )
                )

                if blocked:
                    continue

                new_units = (
                    state["used_units"] + delivery["demand_units"]
                )
                new_weight = (
                    state["used_weight_kg"]
                    + delivery["demand_weight_kg"]
                )
                new_service = (
                    state["used_service_minutes"]
                    + delivery["service_minutes"]
                )

                if new_units > state["capacity_units"]:
                    continue

                if new_weight > state["capacity_weight_kg"]:
                    continue

                if new_service > state["available_minutes"]:
                    continue

                # Best-fit score: prefer a shift with less
                # remaining normalized capacity.
                remaining_units = (
                    state["capacity_units"] - new_units
                ) / state["capacity_units"]

                remaining_weight = (
                    state["capacity_weight_kg"] - new_weight
                ) / state["capacity_weight_kg"]

                score = (
                    remaining_units + remaining_weight,
                    shift["shift_id"],
                )

                candidates.append((score, state))

            if not candidates:
                unassigned.append({
                    "delivery_id": delivery["delivery_id"],
                    "reason": "NO_ELIGIBLE_SHIFT",
                })
                continue

            candidates.sort(key=lambda item: item[0])
            selected = candidates[0][1]
            shift = selected["shift"]

            selected["used_units"] += delivery["demand_units"]
            selected["used_weight_kg"] += (
                delivery["demand_weight_kg"]
            )
            selected["used_service_minutes"] += (
                delivery["service_minutes"]
            )

            selected["assigned_deliveries"].append(
                delivery["delivery_id"]
            )

            assignments.append({
                "delivery_pk": delivery["delivery_pk"],
                "delivery_id": delivery["delivery_id"],
                "planning_date": planning_date,
                "priority": delivery["priority"],
                "site_pk": delivery["site_pk"],
                "shift_pk": shift["shift_pk"],
                "shift_id": shift["shift_id"],
                "vehicle_pk": shift["vehicle_pk"],
                "vehicle_id": shift["vehicle_id"],
                "driver_pk": shift["driver_pk"],
                "demand_units": delivery["demand_units"],
                "demand_weight_kg": delivery["demand_weight_kg"],
                "service_minutes": delivery["service_minutes"],
                "window_start": delivery["window_start"],
                "window_end": delivery["window_end"],
                "window_type": delivery["window_type"],
            })

    shift_summaries = []

    for planning_date in sorted(shifts_by_date):
        for state in shifts_by_date[planning_date]:
            if not state["assigned_deliveries"]:
                continue

            shift = state["shift"]

            shift_summaries.append({
                "planning_date": planning_date,
                "shift_id": shift["shift_id"],
                "vehicle_id": shift["vehicle_id"],
                "delivery_count": len(
                    state["assigned_deliveries"]
                ),
                "used_units": round(state["used_units"], 2),
                "capacity_units": state["capacity_units"],
                "used_weight_kg": round(
                    state["used_weight_kg"], 2
                ),
                "capacity_weight_kg": state[
                    "capacity_weight_kg"
                ],
                "service_minutes": state[
                    "used_service_minutes"
                ],
                "available_minutes": state[
                    "available_minutes"
                ],
            })

    return {
        "assignments": assignments,
        "unassigned": unassigned,
        "shift_summaries": shift_summaries,
        "pending_count": len(deliveries),
    }
