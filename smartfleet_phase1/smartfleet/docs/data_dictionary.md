# SmartFleet Data Dictionary (Phase 1)

This is the initial relational contract. Business IDs are immutable and unique; integer `*_pk` columns are database primary keys. Timestamps use ISO-8601 text. Distances are kilometres, durations are minutes, weights are kilograms, and coordinates are decimal degrees.

| Entity / field | Type | Req. | Allowed values / units | Uniqueness | Validation |
|---|---|---:|---|---|---|
| CustomerSite.site_id | TEXT | Yes | `SITE-000001` | Unique | Non-empty |
| CustomerSite.site_name | TEXT | Yes | Name | No | Non-empty |
| CustomerSite.latitude | REAL | Yes | Decimal degrees | No | -90 to 90 |
| CustomerSite.longitude | REAL | Yes | Decimal degrees | No | -180 to 180 |
| CustomerSite.region | TEXT | Yes | Region label | No | Non-empty |
| CustomerSite.service_minutes | INTEGER | Yes | Minutes | No | >= 0 |
| CustomerSite.site_type | TEXT | Yes | STANDARD, RESTRICTED, DOCK, PICKUP | No | Enum |
| CustomerSite.is_active | INTEGER | Yes | 0/1 | No | Boolean |
| Order.order_id | TEXT | Yes | `ORD-2026-000001` | Unique | Immutable |
| Order.site_pk | INTEGER | Yes | CustomerSite FK | No | Must exist |
| Order.order_date | TEXT | Yes | ISO date | No | Valid date |
| Order.priority | TEXT | Yes | LOW, NORMAL, HIGH, URGENT | No | Enum |
| Order.order_status | TEXT | Yes | CREATED, ALLOCATED, CANCELLED, CLOSED | No | Enum |
| Delivery.delivery_id | TEXT | Yes | `DEL-2026-000001` | Unique | Immutable |
| Delivery.order_pk | INTEGER | Yes | Order FK | No | Must exist |
| Delivery.site_pk | INTEGER | Yes | CustomerSite FK | No | Must agree with parent order site |
| Delivery.demand_units | REAL | Yes | Capacity units | No | > 0 |
| Delivery.demand_weight_kg | REAL | Yes | kg | No | >= 0 |
| Delivery.service_minutes | INTEGER | Yes | Minutes | No | >= 0 |
| Delivery.required_vehicle_type | TEXT | No | Vehicle type | No | Compatible vehicle required when set |
| Delivery.delivery_status | TEXT | Yes | PENDING, ASSIGNED, IN_TRANSIT, DELIVERED, FAILED, UNSERVED | No | Lifecycle transition validation |
| Vehicle.vehicle_id | TEXT | Yes | `VEH-000001` | Unique | Immutable |
| Vehicle.vehicle_type | TEXT | Yes | Type label | No | Non-empty |
| Vehicle.registration_alias | TEXT | Yes | Synthetic alias | Unique | Must not contain real registration data |
| Vehicle.max_route_minutes | INTEGER | Yes | Minutes | No | > 0 |
| VehicleCapacity.vehicle_pk | INTEGER | Yes | Vehicle FK | No | Must exist |
| VehicleCapacity.effective_from | TEXT | Yes | ISO timestamp/date | Composite | Valid effective interval |
| VehicleCapacity.effective_to | TEXT | No | ISO timestamp/date | No | Greater than effective_from |
| VehicleCapacity.capacity_units | REAL | Yes | Units | No | > 0 |
| VehicleCapacity.capacity_weight_kg | REAL | Yes | kg | No | > 0 |
| Driver.driver_id | TEXT | Yes | `DRV-000001` | Unique | Immutable |
| Driver.driver_alias | TEXT | Yes | Synthetic alias | Unique | No personal data |
| Driver.license_class | TEXT | Yes | Class label | No | Non-empty |
| Shift.shift_id | TEXT | Yes | `SHF-2026-000001` | Unique | Immutable |
| Shift.driver_pk | INTEGER | Yes | Driver FK | No | Must exist |
| Shift.vehicle_pk | INTEGER | No | Vehicle FK | No | Must exist when supplied |
| Shift.shift_start / shift_end | TEXT | Yes | ISO timestamps | No | End > start |
| Shift.break_minutes | INTEGER | Yes | Minutes | No | >= 0 |
| Shift.shift_status | TEXT | Yes | SCHEDULED, ACTIVE, COMPLETED, CANCELLED | No | Enum |
| TravelTimeMatrix.scenario_date | TEXT | Yes | ISO date | Composite | Valid date |
| TravelTimeMatrix.scenario_name | TEXT | Yes | BASELINE / traffic label | Composite | Non-empty |
| TravelTimeMatrix.from_site_pk / to_site_pk | INTEGER | Yes | Site FKs | Composite | Both exist and differ |
| TravelTimeMatrix.distance_km | REAL | Yes | km | No | >= 0 |
| TravelTimeMatrix.travel_minutes | INTEGER | Yes | Minutes | No | >= 0 |
| TimeWindow.window_id | TEXT | Yes | `WIN-000001` | Unique | Immutable |
| TimeWindow.delivery_pk | INTEGER | Yes | Delivery FK | No | Must exist |
| TimeWindow.window_start / window_end | TEXT | Yes | ISO timestamps | No | End > start |
| TimeWindow.window_type | TEXT | Yes | HARD, SOFT | No | Enum |
| Route.route_id | TEXT | Yes | `RTE-2026-000001` | Unique | Immutable |
| Route.vehicle_pk / shift_pk | INTEGER | Yes | Vehicle / Shift FKs | No | Must exist; shift vehicle consistent |
| Route.planning_date | TEXT | Yes | ISO date | No | Valid date |
| Route.route_status | TEXT | Yes | DRAFT, PLANNED, DISPATCHED, IN_PROGRESS, COMPLETED, CANCELLED | No | Lifecycle validation |
| Route.planned_distance_km | REAL | Yes | km | No | >= 0; derived from legs |
| Route.planned_duration_minutes | INTEGER | Yes | Minutes | No | >= 0; derived from schedule |
| RouteStop.stop_id | TEXT | Yes | `STOP-<route-id>-001` | Unique | Immutable |
| RouteStop.route_pk / delivery_pk | INTEGER | Yes | Route / Delivery FKs | Composite | Must exist |
| RouteStop.stop_sequence | INTEGER | Yes | 1..N | Unique per route | Contiguous sequence validation |
| RouteStop planned/actual times | TEXT | No | ISO timestamps | No | Arrival <= departure; temporal order |
| RouteStop.stop_status | TEXT | Yes | PLANNED, ARRIVED, COMPLETED, SKIPPED, FAILED | No | Enum |
| DeliveryOutcome.outcome_id | TEXT | Yes | `OUT-2026-000001` | Unique | Immutable |
| DeliveryOutcome.delivery_pk | INTEGER | Yes | Delivery FK | No | Must exist |
| DeliveryOutcome.route_pk | INTEGER | No | Route FK | No | Must exist when supplied |
| DeliveryOutcome.outcome_status | TEXT | Yes | DELIVERED, FAILED, UNSERVED | No | Enum |
| DeliveryOutcome.outcome_reason | TEXT | No | Reason code | No | Required for FAILED |
| DeliveryOutcome.attempted_at / completed_at | TEXT | No | ISO timestamps | No | Completion >= attempt |
| DeliveryOutcome.ground_truth_label | TEXT | No | Label | No | Evaluation metadata only; not planner input |

Supporting tables: `delivery_events`, `route_events`, `vehicle_restrictions`, and `ground_truth` preserve event history, restrictions, and separately labelled anomalies.

## Relationships and cardinality

- CustomerSite 1:N Order.
- CustomerSite 1:N Delivery.
- Order 1:N Delivery (supports split shipments); each Delivery belongs to exactly one Order.
- Vehicle 1:N VehicleCapacity over non-overlapping effective periods.
- Driver 1:N Shift; Vehicle 0..1:N Shift.
- CustomerSite N:M CustomerSite through TravelTimeMatrix, differentiated by date and traffic scenario.
- Delivery 1:N TimeWindow (multiple permitted windows); each window belongs to one delivery.
- Vehicle 1:N Route; Shift 1:N Route historically, subject to operational overlap checks.
- Route 1:N RouteStop; Delivery 0..1:N RouteStop historically, but at most one active planned assignment per delivery must be enforced by business logic.
- Delivery 0..1:N DeliveryOutcome for attempt history; one final outcome per delivery per planning cycle.
- Delivery 1:N DeliveryEvent and Route 1:N RouteEvent.
- Vehicle N:M CustomerSite through VehicleRestriction.
- GroundTruth records point to business IDs polymorphically; these are labels, not operational foreign keys.

Effective dates apply to capacities, time windows, and restrictions. State changes are append-only events.
