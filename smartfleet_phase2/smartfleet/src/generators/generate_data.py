"""Generate SmartFleet datasets in repeatable phases."""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import DEFAULT_SEED
from src.database.db import get_connection, initialize_database
from src.generators.master_data import generate_master_data
from src.generators.transaction_data import generate_transaction_data


RESET_TABLES = [
    "delivery_events",
    "route_events",
    "delivery_outcomes",
    "route_stops",
    "routes",
    "time_windows",
    "travel_time_matrix",
    "vehicle_restrictions",
    "ground_truth",
    "deliveries",
    "orders",
    "shifts",
    "vehicle_capacities",
    "drivers",
    "vehicles",
    "customer_sites",
]


def reset_data(conn):
    conn.execute("PRAGMA foreign_keys = ON")

    for table in RESET_TABLES:
        conn.execute(f"DELETE FROM {table}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate SmartFleet synthetic data"
    )

    parser.add_argument(
        "--phase",
        choices=["master", "transactions"],
        default="master",
    )

    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)

    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete existing generated rows before generation",
    )

    args = parser.parse_args()

    if args.reset and args.phase != "master":
        parser.error(
            "--reset is only supported with --phase master. "
            "It clears all generated project data."
        )

    initialize_database()

    with get_connection() as conn:
        if args.reset:
            reset_data(conn)

        if args.phase == "master":
            counts = generate_master_data(conn, seed=args.seed)
            print("Master data generation completed.")

        else:
            counts = generate_transaction_data(conn, seed=args.seed)
            print("Transaction data generation completed.")

        conn.commit()

    for table, count in counts.items():
        print(f"{table}: {count}")

    print(f"Seed: {args.seed}")
    print("Next: run the relevant validation script.")


if __name__ == "__main__":
    main()