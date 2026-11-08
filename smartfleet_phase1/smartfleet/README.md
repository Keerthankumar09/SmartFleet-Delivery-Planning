# SmartFleet — Delivery Planning & Logistics Analytics

A locally runnable logistics planning project for synthetic delivery data, constraint-aware route planning, delivery simulation, validation, and analytics.

## Current status
Phase 1 scaffold: project structure, SQLite schema, data dictionary, database helpers, and integrity checks.
Planning, simulation, anomaly injection, exports, and dashboard modules are added incrementally.

## Requirements
- Python 3.11+
- pip
- Git

## Setup (Windows PowerShell)
```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If PowerShell blocks activation, run:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

## Initialize the database
```powershell
python scripts\init_db.py
```

This creates `data\smartfleet.db` from `database\schema.sql`.

## Run initial checks
```powershell
python scripts\validate_db.py
```

## Run the dashboard
```powershell
streamlit run app.py
```

## Design notes
- IDs are deterministic, immutable business identifiers (for example `ORD-2026-000001`).
- Internal integer primary keys are used for relational joins; public business IDs have UNIQUE constraints.
- Operational state changes are represented by append-only event tables.
- Deliberate anomalies belong in a separate ground-truth dataset/table and must not be mixed into planner input.
- Generated data is synthetic. No external customer or personal data is used.

## Project commands planned
```powershell
python scripts\generate_data.py --mode starter --seed 20261022
python scripts\generate_data.py --mode full --seed 20261022
python scripts\validate_data.py
python scripts\export_data.py --format csv
```

The generation and export commands are implemented in later project phases.
