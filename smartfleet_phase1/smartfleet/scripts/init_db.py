from src.database.db import initialize_database
from config.settings import DB_PATH

if __name__ == "__main__":
    initialize_database()
    print(f"Database initialized: {DB_PATH}")
