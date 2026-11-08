# Phase 2 — Master data generation

## Generated records
- 500 customer sites inside the configured synthetic region.
- 100 vehicles and one capacity record per vehicle.
- 100 drivers.
- 3,000 scheduled shifts (one shift per driver per day for 30 days).

## Reproducibility
The generator uses Python's local `random.Random(seed)` instance. The default
seed is `20261022`; the same seed and configuration produce the same records.

## Run (Windows PowerShell)
From the `smartfleet` project root:

```powershell
python scripts\generate_data.py --phase master --seed 20261022 --reset
python scripts\validate_data.py
```

`--reset` deletes existing rows from all project data tables before creating
the master dataset. Use it only when you are ready to replace generated data.
It does not delete the database schema.

## Current scope
This phase does not yet create orders, deliveries, time windows, travel-time
scenarios, routes, route stops, outcomes, or labelled anomalies. Those are
added in subsequent phases.
