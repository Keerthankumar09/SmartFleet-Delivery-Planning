
"""Generate the base travel-time matrix and daily traffic scenarios."""

import csv
import math
import random
import sys
from datetime import date, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import GENERATED_DIR
from src.database.db import get_connection

SEED = 20261022
BATCH_SIZE = 5000

TRAFFIC_RANGES = {
    "LOW": (0.80, 0.95),
    "NORMAL": (0.95, 1.10),
    "HEAVY": (1.20, 1.60),
}


def haversine_km(lat1, lon1, lat2, lon2):
    """Calculate straight-line distance between two coordinates."""
    radius = 6371.0

    lat1 = math.radians(lat1)
    lat2 = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1)
        * math.cos(lat2)
        * math.sin(delta_lon / 2) ** 2
    )

    return 2 * radius * math.asin(math.sqrt(a))


def generate_traffic_manifest(seed=SEED):
    """Create 30 days x 3 traffic scenario combinations."""
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)

    rng = random.Random(seed)
    start_date = date(2026, 10, 22)
    manifest_path = GENERATED_DIR / "traffic_scenarios.csv"

    with manifest_path.open(
        "w", newline="", encoding="utf-8"
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "scenario_date",
                "scenario_name",
                "daily_multiplier",
                "seed",
            ],
        )
        writer.writeheader()

        for day_offset in range(30):
            current_date = start_date + timedelta(days=day_offset)

            for scenario_name, bounds in TRAFFIC_RANGES.items():
                writer.writerow({
                    "scenario_date": current_date.isoformat(),
                    "scenario_name": scenario_name,
                    "daily_multiplier": round(
                        rng.uniform(*bounds), 4
                    ),
                    "seed": seed,
                })

    return manifest_path


def generate_travel_matrix(seed=SEED):
    """Generate one base travel-time record per directed site pair."""
    rng = random.Random(seed)

    with get_connection() as conn:
        existing = conn.execute(
            "SELECT COUNT(*) FROM travel_time_matrix"
        ).fetchone()[0]

        if existing:
            raise RuntimeError(
                f"Travel matrix already contains {existing} records. "
                "Generator stopped to prevent duplicate data."
            )

        sites = conn.execute(
            """
            SELECT site_pk, latitude, longitude
            FROM customer_sites
            WHERE is_active = 1
            ORDER BY site_pk
            """
        ).fetchall()

        if len(sites) != 500:
            raise RuntimeError(
                f"Expected 500 active sites, found {len(sites)}."
            )

        records = []

        for origin in sites:
            for destination in sites:
                if origin["site_pk"] == destination["site_pk"]:
                    continue

                straight_distance = haversine_km(
                    origin["latitude"],
                    origin["longitude"],
                    destination["latitude"],
                    destination["longitude"],
                )

                road_distance = straight_distance * 1.25
                speed_kmh = rng.uniform(29.75, 40.25)

                travel_minutes = max(
                    1,
                    math.ceil(road_distance / speed_kmh * 60),
                )

                records.append((
                    "2026-10-22",
                    "BASE",
                    origin["site_pk"],
                    destination["site_pk"],
                    round(road_distance, 2),
                    travel_minutes,
                ))

                if len(records) >= BATCH_SIZE:
                    conn.executemany(
                        """
                        INSERT INTO travel_time_matrix (
                            scenario_date,
                            scenario_name,
                            from_site_pk,
                            to_site_pk,
                            distance_km,
                            travel_minutes
                        )
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        records,
                    )
                    records.clear()

        if records:
            conn.executemany(
                """
                INSERT INTO travel_time_matrix (
                    scenario_date,
                    scenario_name,
                    from_site_pk,
                    to_site_pk,
                    distance_km,
                    travel_minutes
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                records,
            )

        conn.commit()

    manifest_path = generate_traffic_manifest(seed)

    return len(sites) * (len(sites) - 1), manifest_path


def main():
    count, manifest_path = generate_travel_matrix()

    print("Travel matrix generation completed.")
    print(f"Base travel records: {count}")
    print(f"Traffic scenario records: 90")
    print(f"Scenario manifest: {manifest_path}")
    print(f"Seed: {SEED}")


if __name__ == "__main__":
    main()
