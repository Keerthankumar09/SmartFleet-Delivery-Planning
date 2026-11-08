PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS customer_sites (
    site_pk INTEGER PRIMARY KEY,
    site_id TEXT NOT NULL UNIQUE,
    site_name TEXT NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    region TEXT NOT NULL,
    service_minutes INTEGER NOT NULL CHECK(service_minutes >= 0),
    site_type TEXT NOT NULL DEFAULT 'STANDARD'
        CHECK(site_type IN ('STANDARD','RESTRICTED','DOCK','PICKUP')),
    is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0,1)),
    created_at TEXT NOT NULL,
    CHECK(latitude BETWEEN -90 AND 90),
    CHECK(longitude BETWEEN -180 AND 180)
);

CREATE TABLE IF NOT EXISTS orders (
    order_pk INTEGER PRIMARY KEY,
    order_id TEXT NOT NULL UNIQUE,
    site_pk INTEGER NOT NULL REFERENCES customer_sites(site_pk),
    order_date TEXT NOT NULL,
    priority TEXT NOT NULL CHECK(priority IN ('LOW','NORMAL','HIGH','URGENT')),
    order_status TEXT NOT NULL CHECK(order_status IN ('CREATED','ALLOCATED','CANCELLED','CLOSED')),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS deliveries (
    delivery_pk INTEGER PRIMARY KEY,
    delivery_id TEXT NOT NULL UNIQUE,
    order_pk INTEGER NOT NULL REFERENCES orders(order_pk),
    site_pk INTEGER NOT NULL REFERENCES customer_sites(site_pk),
    demand_units REAL NOT NULL CHECK(demand_units > 0),
    demand_weight_kg REAL NOT NULL CHECK(demand_weight_kg >= 0),
    service_minutes INTEGER NOT NULL CHECK(service_minutes >= 0),
    required_vehicle_type TEXT,
    delivery_status TEXT NOT NULL CHECK(delivery_status IN
        ('PENDING','ASSIGNED','IN_TRANSIT','DELIVERED','FAILED','UNSERVED')),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS vehicles (
    vehicle_pk INTEGER PRIMARY KEY,
    vehicle_id TEXT NOT NULL UNIQUE,
    vehicle_type TEXT NOT NULL,
    registration_alias TEXT NOT NULL UNIQUE,
    max_route_minutes INTEGER NOT NULL CHECK(max_route_minutes > 0),
    is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0,1)),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS vehicle_capacities (
    capacity_pk INTEGER PRIMARY KEY,
    vehicle_pk INTEGER NOT NULL REFERENCES vehicles(vehicle_pk),
    effective_from TEXT NOT NULL,
    effective_to TEXT,
    capacity_units REAL NOT NULL CHECK(capacity_units > 0),
    capacity_weight_kg REAL NOT NULL CHECK(capacity_weight_kg > 0),
    UNIQUE(vehicle_pk, effective_from),
    CHECK(effective_to IS NULL OR effective_to > effective_from)
);

CREATE TABLE IF NOT EXISTS drivers (
    driver_pk INTEGER PRIMARY KEY,
    driver_id TEXT NOT NULL UNIQUE,
    driver_alias TEXT NOT NULL UNIQUE,
    license_class TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0,1)),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS shifts (
    shift_pk INTEGER PRIMARY KEY,
    shift_id TEXT NOT NULL UNIQUE,
    driver_pk INTEGER NOT NULL REFERENCES drivers(driver_pk),
    vehicle_pk INTEGER REFERENCES vehicles(vehicle_pk),
    shift_start TEXT NOT NULL,
    shift_end TEXT NOT NULL,
    break_minutes INTEGER NOT NULL DEFAULT 0 CHECK(break_minutes >= 0),
    shift_status TEXT NOT NULL CHECK(shift_status IN ('SCHEDULED','ACTIVE','COMPLETED','CANCELLED')),
    CHECK(shift_end > shift_start)
);

CREATE TABLE IF NOT EXISTS travel_time_matrix (
    travel_pk INTEGER PRIMARY KEY,
    scenario_date TEXT NOT NULL,
    scenario_name TEXT NOT NULL,
    from_site_pk INTEGER NOT NULL REFERENCES customer_sites(site_pk),
    to_site_pk INTEGER NOT NULL REFERENCES customer_sites(site_pk),
    distance_km REAL NOT NULL CHECK(distance_km >= 0),
    travel_minutes INTEGER NOT NULL CHECK(travel_minutes >= 0),
    UNIQUE(scenario_date, scenario_name, from_site_pk, to_site_pk),
    CHECK(from_site_pk <> to_site_pk)
);

CREATE TABLE IF NOT EXISTS time_windows (
    window_pk INTEGER PRIMARY KEY,
    window_id TEXT NOT NULL UNIQUE,
    delivery_pk INTEGER NOT NULL REFERENCES deliveries(delivery_pk),
    window_start TEXT NOT NULL,
    window_end TEXT NOT NULL,
    window_type TEXT NOT NULL DEFAULT 'HARD' CHECK(window_type IN ('HARD','SOFT')),
    effective_from TEXT NOT NULL,
    effective_to TEXT,
    CHECK(window_end > window_start),
    CHECK(effective_to IS NULL OR effective_to > effective_from)
);

CREATE TABLE IF NOT EXISTS routes (
    route_pk INTEGER PRIMARY KEY,
    route_id TEXT NOT NULL UNIQUE,
    vehicle_pk INTEGER NOT NULL REFERENCES vehicles(vehicle_pk),
    shift_pk INTEGER NOT NULL REFERENCES shifts(shift_pk),
    planning_date TEXT NOT NULL,
    route_status TEXT NOT NULL CHECK(route_status IN ('DRAFT','PLANNED','DISPATCHED','IN_PROGRESS','COMPLETED','CANCELLED')),
    planned_distance_km REAL NOT NULL DEFAULT 0 CHECK(planned_distance_km >= 0),
    planned_duration_minutes INTEGER NOT NULL DEFAULT 0 CHECK(planned_duration_minutes >= 0),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS route_stops (
    stop_pk INTEGER PRIMARY KEY,
    stop_id TEXT NOT NULL UNIQUE,
    route_pk INTEGER NOT NULL REFERENCES routes(route_pk),
    delivery_pk INTEGER NOT NULL REFERENCES deliveries(delivery_pk),
    stop_sequence INTEGER NOT NULL CHECK(stop_sequence > 0),
    planned_arrival TEXT,
    planned_departure TEXT,
    actual_arrival TEXT,
    actual_departure TEXT,
    stop_status TEXT NOT NULL CHECK(stop_status IN ('PLANNED','ARRIVED','COMPLETED','SKIPPED','FAILED')),
    UNIQUE(route_pk, stop_sequence),
    UNIQUE(route_pk, delivery_pk)
);

CREATE TABLE IF NOT EXISTS delivery_outcomes (
    outcome_pk INTEGER PRIMARY KEY,
    outcome_id TEXT NOT NULL UNIQUE,
    delivery_pk INTEGER NOT NULL REFERENCES deliveries(delivery_pk),
    route_pk INTEGER REFERENCES routes(route_pk),
    outcome_status TEXT NOT NULL CHECK(outcome_status IN ('DELIVERED','FAILED','UNSERVED')),
    outcome_reason TEXT,
    attempted_at TEXT,
    completed_at TEXT,
    ground_truth_label TEXT,
    created_at TEXT NOT NULL,
    CHECK(completed_at IS NULL OR attempted_at IS NULL OR completed_at >= attempted_at)
);

-- Append-only event history: application code inserts events; it does not rewrite old events.
CREATE TABLE IF NOT EXISTS delivery_events (
    event_pk INTEGER PRIMARY KEY,
    event_id TEXT NOT NULL UNIQUE,
    delivery_pk INTEGER NOT NULL REFERENCES deliveries(delivery_pk),
    from_status TEXT,
    to_status TEXT NOT NULL,
    event_time TEXT NOT NULL,
    reason_code TEXT,
    event_payload_json TEXT
);

CREATE TABLE IF NOT EXISTS route_events (
    event_pk INTEGER PRIMARY KEY,
    event_id TEXT NOT NULL UNIQUE,
    route_pk INTEGER NOT NULL REFERENCES routes(route_pk),
    event_type TEXT NOT NULL,
    event_time TEXT NOT NULL,
    event_payload_json TEXT
);

CREATE TABLE IF NOT EXISTS vehicle_restrictions (
    restriction_pk INTEGER PRIMARY KEY,
    vehicle_pk INTEGER NOT NULL REFERENCES vehicles(vehicle_pk),
    site_pk INTEGER NOT NULL REFERENCES customer_sites(site_pk),
    restriction_type TEXT NOT NULL,
    effective_from TEXT NOT NULL,
    effective_to TEXT,
    UNIQUE(vehicle_pk, site_pk, restriction_type, effective_from),
    CHECK(effective_to IS NULL OR effective_to > effective_from)
);

CREATE TABLE IF NOT EXISTS ground_truth (
    truth_pk INTEGER PRIMARY KEY,
    truth_id TEXT NOT NULL UNIQUE,
    issue_type TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_business_id TEXT NOT NULL,
    expected_detection TEXT NOT NULL,
    severity TEXT NOT NULL CHECK(severity IN ('LOW','MEDIUM','HIGH','CRITICAL')),
    details_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_orders_site ON orders(site_pk);
CREATE INDEX IF NOT EXISTS idx_deliveries_order ON deliveries(order_pk);
CREATE INDEX IF NOT EXISTS idx_deliveries_site ON deliveries(site_pk);
CREATE INDEX IF NOT EXISTS idx_shifts_driver ON shifts(driver_pk);
CREATE INDEX IF NOT EXISTS idx_travel_pair_date ON travel_time_matrix(scenario_date, from_site_pk, to_site_pk);
CREATE INDEX IF NOT EXISTS idx_windows_delivery ON time_windows(delivery_pk);
CREATE INDEX IF NOT EXISTS idx_stops_route_sequence ON route_stops(route_pk, stop_sequence);
CREATE INDEX IF NOT EXISTS idx_events_delivery_time ON delivery_events(delivery_pk, event_time);
