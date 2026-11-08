from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
GENERATED_DIR = DATA_DIR / "generated"
EXPORT_DIR = DATA_DIR / "exports"
DB_PATH = DATA_DIR / "smartfleet.db"
SCHEMA_PATH = PROJECT_ROOT / "database" / "schema.sql"

DEFAULT_SEED = 20261022
DEFAULT_REGION = {
    "name": "Synthetic Andhra Logistics Region",
    "min_lat": 15.5,
    "max_lat": 17.5,
    "min_lon": 80.5,
    "max_lon": 82.5,
}
