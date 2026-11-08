"""Deterministic generation of SmartFleet master data."""
import random
from datetime import date, datetime, time, timedelta, timezone

from config.settings import DEFAULT_REGION

BASE_DATE = date(2026, 10, 22)
CREATED_AT = "2026-10-22T00:00:00+00:00"

VEHICLE_PROFILES = {
    "VAN": (80, 1200, 600),
    "TRUCK": (250, 5000, 720),
    "MINI_TRUCK": (140, 2500, 660),
}

LICENSE_BY_VEHICLE = {
    "VAN": "LMV",
    "MINI_TRUCK": "LMV",
    "TRUCK": "HMV",
}


def _iso(dt):
    return dt.isoformat(timespec="seconds")


def generate_master_data(conn, seed=20261022, site_count=500,
                         vehicle_count=100, driver_count=100,
                         days=30):
    """Insert sites, vehicles, capacities, drivers and daily shifts.

    The function expects the target tables to be empty. The caller controls
    reset/transaction behavior so generation can be composed with later phases.
    """
    rng = random.Random(seed)
    region = DEFAULT_REGION
    cursor = conn.cursor()

    # 500 deterministic synthetic customer sites.
    for i in range(1, site_count + 1):
        site_type = rng.choices(
            ["STANDARD", "RESTRICTED", "DOCK", "PICKUP"],
            weights=[78, 8, 9, 5], k=1
        )[0]
        lat = rng.uniform(region["min_lat"], region["max_lat"])
        lon = rng.uniform(region["min_lon"], region["max_lon"])
        cursor.execute("""
            INSERT INTO customer_sites
            (site_id, site_name, latitude, longitude, region,
             service_minutes, site_type, is_active, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)
        """, (
            f"SITE-{i:06d}", f"Customer Site {i:04d}",
            round(lat, 6), round(lon, 6), region["name"],
            rng.choice([10, 15, 20, 25, 30, 40]), site_type, CREATED_AT
        ))

    # Vehicle and driver records are generated before dependent capacities/shifts.
    vehicle_pks = []
    for i in range(1, vehicle_count + 1):
        vehicle_type = rng.choices(
            ["VAN", "TRUCK", "MINI_TRUCK"], weights=[55, 20, 25], k=1
        )[0]
        _, _, max_route_minutes = VEHICLE_PROFILES[vehicle_type]
        cursor.execute("""
            INSERT INTO vehicles
            (vehicle_id, vehicle_type, registration_alias,
             max_route_minutes, is_active, created_at)
            VALUES (?, ?, ?, ?, 1, ?)
        """, (
            f"VEH-{i:06d}", vehicle_type, f"FLEET-{i:04d}",
            max_route_minutes, CREATED_AT
        ))
        vehicle_pks.append(cursor.lastrowid)

    driver_pks = []
    for i in range(1, driver_count + 1):
        # Assign a license that can operate at least one fleet vehicle.
        license_class = rng.choice(["LMV", "HMV"])
        cursor.execute("""
            INSERT INTO drivers
            (driver_id, driver_alias, license_class, is_active, created_at)
            VALUES (?, ?, ?, 1, ?)
        """, (
            f"DRV-{i:06d}", f"DRIVER-{i:04d}", license_class, CREATED_AT
        ))
        driver_pks.append(cursor.lastrowid)

    for i, vehicle_pk in enumerate(vehicle_pks, start=1):
        vehicle_type = cursor.execute(
            "SELECT vehicle_type FROM vehicles WHERE vehicle_pk = ?",
            (vehicle_pk,)
        ).fetchone()[0]
        units, weight, _ = VEHICLE_PROFILES[vehicle_type]
        cursor.execute("""
            INSERT INTO vehicle_capacities
            (vehicle_pk, effective_from, effective_to,
             capacity_units, capacity_weight_kg)
            VALUES (?, ?, NULL, ?, ?)
        """, (vehicle_pk, BASE_DATE.isoformat(), units, weight))

    # One scheduled shift per driver per day; vehicles rotate deterministically.
    shift_number = 0
    for day_offset in range(days):
        shift_date = BASE_DATE + timedelta(days=day_offset)
        for driver_index, driver_pk in enumerate(driver_pks):
            shift_number += 1
            vehicle_pk = vehicle_pks[(driver_index + day_offset) % len(vehicle_pks)]
            start_hour = rng.choice([6, 7, 8, 9])
            start = datetime.combine(shift_date, time(start_hour, 0))
            end = start + timedelta(hours=8)
            cursor.execute("""
                INSERT INTO shifts
                (shift_id, driver_pk, vehicle_pk, shift_start, shift_end,
                 break_minutes, shift_status)
                VALUES (?, ?, ?, ?, ?, ?, 'SCHEDULED')
            """, (
                f"SHF-2026-{shift_number:06d}", driver_pk, vehicle_pk,
                _iso(start), _iso(end), 30
            ))

    return {
        "customer_sites": site_count,
        "vehicles": vehicle_count,
        "vehicle_capacities": vehicle_count,
        "drivers": driver_count,
        "shifts": driver_count * days,
    }
