
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.database.db import get_connection
from src.planning.analytics import generate_analytics


def main():
    conn = get_connection()

    try:
        generate_analytics(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
