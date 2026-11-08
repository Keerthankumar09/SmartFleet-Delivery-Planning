# SmartFleet Data Dictionary

This document describes the main database tables used by SmartFleet.

| Table | Purpose |
|---|---|
| `customer_sites` | Stores customer delivery locations and site information. |
| `orders` | Stores customer orders, order dates, and priority levels. |
| `deliveries` | Stores delivery demand, service requirements, and current delivery status. |
| `vehicles` | Stores vehicle details and vehicle types. |
| `vehicle_capacities` | Stores vehicle capacity limits, including units and weight. |
| `drivers` | Stores driver information and availability status. |
| `shifts` | Stores driver and vehicle shift assignments, start/end times, and shift details. |
| `travel_time_matrix` | Stores estimated travel distance and travel time between customer sites. |
| `time_windows` | Stores permitted delivery arrival windows and window types. |
| `routes` | Stores planned route information, dates, status, and distance/duration estimates. |
| `route_stops` | Stores individual deliveries and their sequence within each route. |
| `delivery_outcomes` | Stores final simulated delivery outcomes and reasons. |
| `delivery_events` | Stores delivery status transitions and event details. |
| `route_events` | Stores route lifecycle events. |
| `vehicle_restrictions` | Stores vehicle-to-site restrictions and their effective dates. |
| `ground_truth` | Stores expected issue detections for validation or future analytics. |

## Important Fields

### `customer_sites`
- `site_pk`: Internal site primary key.
- Site business identifier and location coordinates.
- Site type and related site attributes.

### `orders`
- `order_pk`: Internal order primary key.
- `order_id`: Business order identifier.
- `site_pk`: Customer site reference.
- `order_date`: Order planning date.
- `priority`: Order priority.

### `deliveries`
- `delivery_pk`: Internal delivery primary key.
- `delivery_id`: Business delivery identifier.
- `order_pk`: Related order.
- `site_pk`: Delivery destination.
- `demand_units`: Required quantity.
- `demand_weight_kg`: Required delivery weight.
- `service_minutes`: Estimated service duration.
- `required_vehicle_type`: Required vehicle type.
- `delivery_status`: Current delivery status.

### `vehicles`
- Vehicle primary key and business identifier.
- Vehicle type and active status.

### `vehicle_capacities`
- Vehicle reference.
- Maximum supported units.
- Maximum supported weight in kilograms.
- Capacity effective dates.

### `drivers`
- Driver primary key and business identifier.
- Driver active status and driver attributes.

### `shifts`
- Shift primary key and identifier.
- Driver and vehicle references.
- `shift_start` and `shift_end`.
- Break duration and shift status.

### `travel_time_matrix`
- Origin and destination site references.
- `distance_km`: Estimated travel distance.
- Travel-time estimate in minutes.
- Scenario date and scenario name.

### `time_windows`
- Delivery reference.
- `window_start` and `window_end`.
- `window_type`: HARD or SOFT.
- Effective dates.

### `routes`
- `route_pk`: Internal route primary key.
- `route_id`: Business route identifier.
- Planning date and route status.
- Planned distance and duration.

### `route_stops`
- Route and delivery references.
- Stop sequence.
- Planned arrival and departure.
- Actual arrival and departure.
- Stop status.

### `delivery_outcomes`
- Delivery and route references.
- `outcome_status`: DELIVERED, FAILED, or UNSERVED.
- Outcome reason.
- Attempt and completion timestamps.
- Ground-truth label.

### `delivery_events` and `route_events`
These tables preserve event history, including status transitions, event timestamps, reason codes, and event payloads.

### `vehicle_restrictions`
Stores vehicle and site references with effective dates, identifying combinations that must not be assigned.

### `ground_truth`
Stores expected issue information, including issue type, entity, expected detection, severity, and details.

## Status Values

| Field | Values |
|---|---|
| Delivery status | PENDING, ASSIGNED, IN_TRANSIT, DELIVERED, FAILED, UNSERVED |
| Delivery outcome | DELIVERED, FAILED, UNSERVED |
| Time window type | HARD, SOFT |
| Ground-truth severity | LOW, MEDIUM, HIGH, CRITICAL |

**Note:** The database schema in `database/schema.sql` is the authoritative source for all column definitions, data types, constraints, and permitted values.