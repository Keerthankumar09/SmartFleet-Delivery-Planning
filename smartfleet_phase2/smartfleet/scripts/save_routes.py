
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.database.db import get_connection
from src.planning.persistence import save_route_preview


def main():
    conn = get_connection()

    try:
        save_route_preview(conn, scenario_name="NORMAL")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
