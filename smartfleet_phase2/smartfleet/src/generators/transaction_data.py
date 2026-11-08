"""Generate deterministic SmartFleet orders, deliveries and time windows."""

import random
from datetime import date, datetime, time, timedelta, timezone


BASE_DATE = date(2026, 10, 22)
GENERATED_DAYS = 30
RECORD_COUNT = 2000


def generate_transaction_data(conn, seed=20261022):
    rng = random.Random(seed)

    sites = conn.execute("""
        SELECT site_pk, service_minutes
        FROM customer_sites
        WHERE is_active = 1
        ORDER BY site_pk
    """).fetchall()

    if not sites:
        raise ValueError(
            "No active customer sites found. Generate master data first."
        )

    existing = {
        "orders": conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0],
        "deliveries": conn.execute("SELECT COUNT(*) FROM deliveries").fetchone()[0],
        "time_windows": conn.execute(
            "SELECT COUNT(*) FROM time_windows"
        ).fetchone()[0],
    }

    if any(existing.values()):
        raise ValueError(
            "Transaction data already exists. "
            "This generator will not overwrite existing records. "
            "Do not delete data manually; check the database first."
        )

    priorities = ["LOW", "NORMAL", "HIGH", "URGENT"]
    priority_weights = [15, 50, 25, 10]

    order_rows = []
    delivery_rows = []
    window_rows = []

    for number in range(1, RECORD_COUNT + 1):
        site = rng.choice(sites)
        site_pk = site["site_pk"]

        # Spread orders across a fixed 30-day period.
        order_day = BASE_DATE + timedelta(
            days=rng.randrange(GENERATED_DAYS)
        )

        created_hour = rng.randint(6, 16)
        created_minute = rng.randint(0, 59)

        created_at = datetime.combine(
            order_day,
            time(created_hour, created_minute),
            tzinfo=timezone.utc,
        ).isoformat()

        order_id = f"ORD-2026-{number:06d}"
        delivery_id = f"DEL-2026-{number:06d}"
        window_id = f"WIN-2026-{number:06d}"

        priority = rng.choices(
            priorities, weights=priority_weights, k=1
        )[0]

        order_rows.append((
            order_id,
            site_pk,
            order_day.isoformat(),
            priority,
            "CREATED",
            created_at,
        ))

        demand_units = round(rng.uniform(1, 10), 2)
        demand_weight_kg = round(
            demand_units * rng.uniform(2, 12), 2
        )

        service_minutes = max(
            1,
            int(site["service_minutes"]) + rng.randint(-5, 10),
        )

        delivery_rows.append((
            delivery_id,
            order_id,  # Resolved to order_pk below.
            site_pk,
            demand_units,
            demand_weight_kg,
            service_minutes,
            None,      # No vehicle-type restriction by default.
            "PENDING",
            created_at,
        ))

        # Delivery window: a 2–4 hour period between 08:00 and 18:00.
        start_hour = rng.randint(8, 14)
        duration_hours = rng.randint(2, 4)

        window_start = datetime.combine(
            order_day, time(start_hour, 0), tzinfo=timezone.utc
        )
        window_end = window_start + timedelta(hours=duration_hours)

        effective_from = datetime.combine(
            order_day, time(0, 0), tzinfo=timezone.utc
        ).isoformat()

        window_rows.append((
            window_id,
            delivery_id,  # Resolved to delivery_pk below.
            window_start.isoformat(),
            window_end.isoformat(),
            rng.choices(["HARD", "SOFT"], weights=[85, 15], k=1)[0],
            effective_from,
            None,
        ))

    # Insert parents before children.
    conn.executemany("""
        INSERT INTO orders (
            order_id, site_pk, order_date, priority,
            order_status, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
    """, order_rows)

    order_ids = {
        row["order_id"]: row["order_pk"]
        for row in conn.execute(
            "SELECT order_pk, order_id FROM orders"
        ).fetchall()
    }

    delivery_insert_rows = [
        (
            row[0],
            order_ids[row[1]],
            *row[2:],
        )
        for row in delivery_rows
    ]

    conn.executemany("""
        INSERT INTO deliveries (
            delivery_id, order_pk, site_pk, demand_units,
            demand_weight_kg, service_minutes, required_vehicle_type,
            delivery_status, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, delivery_insert_rows)

    delivery_ids = {
        row["delivery_id"]: row["delivery_pk"]
        for row in conn.execute(
            "SELECT delivery_pk, delivery_id FROM deliveries"
        ).fetchall()
    }

    window_insert_rows = [
        (
            row[0],
            delivery_ids[row[1]],
            *row[2:],
        )
        for row in window_rows
    ]

    conn.executemany("""
        INSERT INTO time_windows (
            window_id, delivery_pk, window_start, window_end,
            window_type, effective_from, effective_to
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, window_insert_rows)

    return {
        "orders": len(order_rows),
        "deliveries": len(delivery_insert_rows),
        "time_windows": len(window_insert_rows),
    }