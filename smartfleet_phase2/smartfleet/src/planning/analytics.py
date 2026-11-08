
import csv
import json
import math
from collections import defaultdict
from datetime import datetime, timezone

from config.settings import EXPORT_DIR


def _minutes_late(actual_arrival, window_end):
    """Return positive lateness in whole minutes, or zero."""
    if not actual_arrival or not window_end:
        return 0

    actual = datetime.fromisoformat(actual_arrival)
    deadline = datetime.fromisoformat(window_end)

    # Convert timezone-aware timestamps to UTC, then remove timezone info.
    if actual.tzinfo is not None:
        actual = actual.astimezone(timezone.utc).replace(tzinfo=None)

    if deadline.tzinfo is not None:
        deadline = deadline.astimezone(timezone.utc).replace(tzinfo=None)

    seconds = (actual - deadline).total_seconds()
    return max(0, math.ceil(seconds / 60))


def _write_csv(path, rows, fieldnames):
    """Write a CSV report, including its header when empty."""
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def generate_analytics(conn):
    """
    Generate delivery, daily, priority, route and summary reports.

    This function only reads the database and writes report files.
    It does not modify database records.
    """

    EXPORT_DIR.mkdir(parents=True, exist_ok=True)

    print("Collecting delivery performance data...")

    deliveries = [
        dict(row)
        for row in conn.execute(
            """
            SELECT
                d.delivery_pk,
                d.delivery_id,
                o.order_id,
                substr(o.order_date, 1, 10) AS order_date,
                o.priority,
                d.delivery_status,
                outcome.outcome_status,
                outcome.outcome_reason,
                tw.window_type,
                tw.window_end,
                rs.planned_arrival,
                rs.actual_arrival,
                rs.actual_departure,
                r.route_id
            FROM deliveries d
            JOIN orders o
                ON o.order_pk = d.order_pk
            JOIN delivery_outcomes outcome
                ON outcome.delivery_pk = d.delivery_pk
            LEFT JOIN time_windows tw
                ON tw.delivery_pk = d.delivery_pk
            LEFT JOIN route_stops rs
                ON rs.delivery_pk = d.delivery_pk
            LEFT JOIN routes r
                ON r.route_pk = rs.route_pk
            ORDER BY o.order_date, d.delivery_id
            """
        )
    ]

    total_deliveries = conn.execute(
        "SELECT COUNT(*) FROM deliveries"
    ).fetchone()[0]

    unique_outcomes = conn.execute(
        "SELECT COUNT(DISTINCT delivery_pk) FROM delivery_outcomes"
    ).fetchone()[0]

    if len(deliveries) != total_deliveries or unique_outcomes != total_deliveries:
        raise ValueError(
            "Analytics stopped: every delivery must have exactly one outcome. "
            f"Deliveries={total_deliveries}, report rows={len(deliveries)}, "
            f"unique outcomes={unique_outcomes}"
        )

    # Overall delivery outcomes.
    status_counts = defaultdict(int)

    for item in deliveries:
        status_counts[item["outcome_status"]] += 1

    delivered = status_counts["DELIVERED"]
    failed = status_counts["FAILED"]
    unserved = status_counts["UNSERVED"]

    # Enrich individual delivery records with lateness.
    on_time_delivered = 0
    late_delivered = 0

    for item in deliveries:
        late_minutes = _minutes_late(
            item["actual_arrival"],
            item["window_end"],
        )

        item["late_minutes"] = late_minutes
        item["on_time"] = (
            "YES" if item["actual_arrival"] and late_minutes == 0
            else "NO" if item["actual_arrival"]
            else "NOT_ATTEMPTED"
        )

        if item["outcome_status"] == "DELIVERED":
            if late_minutes == 0 and item["actual_arrival"]:
                on_time_delivered += 1
            elif item["actual_arrival"]:
                late_delivered += 1

    # Daily performance.
    daily = defaultdict(
        lambda: {
            "total_deliveries": 0,
            "delivered": 0,
            "failed": 0,
            "unserved": 0,
        }
    )

    for item in deliveries:
        day = item["order_date"]
        daily[day]["total_deliveries"] += 1
        daily[day][item["outcome_status"].lower()] += 1

    daily_rows = []

    for day in sorted(daily):
        values = daily[day]
        total = values["total_deliveries"]

        daily_rows.append({
            "date": day,
            **values,
            "delivery_success_rate_percent": round(
                values["delivered"] / total * 100, 2
            ) if total else 0,
        })

    # Priority performance.
    priority = defaultdict(
        lambda: {
            "total_deliveries": 0,
            "delivered": 0,
            "failed": 0,
            "unserved": 0,
        }
    )

    for item in deliveries:
        level = item["priority"]
        priority[level]["total_deliveries"] += 1
        priority[level][item["outcome_status"].lower()] += 1

    priority_rows = []

    for level in sorted(priority):
        values = priority[level]
        total = values["total_deliveries"]

        priority_rows.append({
            "priority": level,
            **values,
            "delivery_success_rate_percent": round(
                values["delivered"] / total * 100, 2
            ) if total else 0,
        })

    # Route performance.
    route_rows = [
        dict(row)
        for row in conn.execute(
            """
            SELECT
                r.route_id,
                r.planning_date,
                r.route_status,
                r.planned_distance_km,
                r.planned_duration_minutes,
                COUNT(rs.stop_pk) AS total_stops,
                SUM(
                    CASE WHEN rs.stop_status = 'COMPLETED'
                    THEN 1 ELSE 0 END
                ) AS delivered_stops,
                SUM(
                    CASE WHEN rs.stop_status = 'FAILED'
                    THEN 1 ELSE 0 END
                ) AS failed_stops,
                MIN(rs.actual_arrival) AS first_actual_arrival,
                MAX(rs.actual_departure) AS last_actual_departure
            FROM routes r
            LEFT JOIN route_stops rs
                ON rs.route_pk = r.route_pk
            GROUP BY r.route_pk
            ORDER BY r.planning_date, r.route_id
            """
        )
    ]

    for route in route_rows:
        start = route.pop("first_actual_arrival")
        end = route.pop("last_actual_departure")

        if start and end:
            start_dt = datetime.fromisoformat(start)
            end_dt = datetime.fromisoformat(end)
            route["actual_duration_minutes"] = round(
                (end_dt - start_dt).total_seconds() / 60, 2
            )
        else:
            route["actual_duration_minutes"] = 0

        route["average_distance_per_stop_km"] = round(
            route["planned_distance_km"] / route["total_stops"], 3
        ) if route["total_stops"] else 0

    # Overall summary.
    on_time_rate = (
        on_time_delivered / delivered * 100 if delivered else 0
    )

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(
            timespec="seconds"
        ),
        "total_deliveries": total_deliveries,
        "outcomes": {
            "delivered": delivered,
            "failed": failed,
            "unserved": unserved,
        },
        "delivery_success_rate_percent": round(
            delivered / total_deliveries * 100, 2
        ) if total_deliveries else 0,
        "delivery_failure_rate_percent": round(
            failed / total_deliveries * 100, 2
        ) if total_deliveries else 0,
        "unserved_rate_percent": round(
            unserved / total_deliveries * 100, 2
        ) if total_deliveries else 0,
        "on_time_delivered": on_time_delivered,
        "late_delivered": late_delivered,
        "on_time_rate_among_delivered_percent": round(
            on_time_rate, 2
        ),
        "routes": {
            "total_routes": len(route_rows),
            "total_stops": sum(
                row["total_stops"] for row in route_rows
            ),
            "total_planned_distance_km": round(
                sum(row["planned_distance_km"] for row in route_rows), 3
            ),
            "average_stops_per_route": round(
                sum(row["total_stops"] for row in route_rows)
                / len(route_rows), 2
            ) if route_rows else 0,
        },
        "priority_performance": priority_rows,
    }

    # Export individual delivery report.
    delivery_fields = [
        "delivery_id",
        "order_id",
        "order_date",
        "priority",
        "delivery_status",
        "outcome_status",
        "outcome_reason",
        "window_type",
        "window_end",
        "planned_arrival",
        "actual_arrival",
        "actual_departure",
        "late_minutes",
        "on_time",
        "route_id",
    ]

    delivery_export = [
        {field: item.get(field) for field in delivery_fields}
        for item in deliveries
    ]

    _write_csv(
        EXPORT_DIR / "delivery_performance.csv",
        delivery_export,
        delivery_fields,
    )

    _write_csv(
        EXPORT_DIR / "daily_performance.csv",
        daily_rows,
        [
            "date",
            "total_deliveries",
            "delivered",
            "failed",
            "unserved",
            "delivery_success_rate_percent",
        ],
    )

    _write_csv(
        EXPORT_DIR / "priority_performance.csv",
        priority_rows,
        [
            "priority",
            "total_deliveries",
            "delivered",
            "failed",
            "unserved",
            "delivery_success_rate_percent",
        ],
    )

    _write_csv(
        EXPORT_DIR / "route_performance.csv",
        route_rows,
        [
            "route_id",
            "planning_date",
            "route_status",
            "planned_distance_km",
            "planned_duration_minutes",
            "total_stops",
            "delivered_stops",
            "failed_stops",
            "actual_duration_minutes",
            "average_distance_per_stop_km",
        ],
    )

    summary_path = EXPORT_DIR / "analytics_summary.json"

    summary_path.write_text(
        json.dumps(summary, indent=4),
        encoding="utf-8",
    )

    print("\n===== PHASE 8 ANALYTICS COMPLETE =====")
    print(f"Total deliveries: {total_deliveries}")
    print(f"Delivered: {delivered}")
    print(f"Failed: {failed}")
    print(f"Unserved: {unserved}")
    print(f"Delivery success rate: {summary['delivery_success_rate_percent']}%")
    print(f"On-time rate among delivered: {on_time_rate:.2f}%")
    print(f"Routes analyzed: {len(route_rows)}")
    print(f"Total planned distance: {summary['routes']['total_planned_distance_km']} km")
    print(f"Reports saved in: {EXPORT_DIR}")

    return summary
