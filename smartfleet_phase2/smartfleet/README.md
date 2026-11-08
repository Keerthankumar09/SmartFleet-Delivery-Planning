# SmartFleet – Delivery Planning & Logistics Analytics

## 1. Problem Statement and Project Objectives

### Problem Statement

Managing large-scale delivery operations involves assigning deliveries to suitable vehicles and drivers while satisfying multiple operational constraints, including vehicle capacity, delivery time windows, driver shifts, service durations, and travel times.

I developed **SmartFleet**, a delivery planning and logistics analytics system that generates delivery data, assigns deliveries to available resources, creates feasible delivery routes, simulates delivery outcomes, and produces operational performance reports.

### Project Objectives

- Generate reproducible synthetic logistics and delivery datasets.
- Assign deliveries to eligible vehicles and driver shifts.
- Plan routes while respecting operational constraints.
- Simulate delivery execution and operational failures.
- Measure delivery performance through analytics.
- Provide an interactive dashboard for exploring operational results.
- Validate data integrity, planning outputs, and system behavior.

## 2. Architecture and Technology Stack

### Technology Stack

| Technology | Purpose |
|---|---|
| Python | Core application and planning logic |
| SQLite | Relational data storage |
| Pandas | Data processing and analytics |
| NumPy | Numerical operations |
| Streamlit | Interactive dashboard |
| Plotly | Interactive charts and visualizations |
| PowerShell | Development and execution environment |

### System Architecture

The application follows a modular, phase-based architecture.

```text
SmartFleet
│
├── Configuration
│   └── Application settings
│
├── Database
│   ├── Database schema
│   └── SQLite connection management
│
├── Data Generation
│   ├── Master data generation
│   ├── Transaction generation
│   └── Travel matrix generation
│
├── Planning
│   ├── Constraint validation
│   ├── Delivery assignment
│   ├── Route planning
│   ├── Route persistence
│   ├── Delivery simulation
│   └── Analytics
│
├── Scripts
│   ├── Generation scripts
│   ├── Validation scripts
│   ├── Planning scripts
│   └── Reporting scripts
│
├── Data
│   ├── SQLite database
│   ├── Generated datasets
│   └── Analytics exports
│
├── Docs
│   └── Data dictionary
│
└── app.py
    └── Streamlit dashboard
```

The system uses SQLite as the central data store. Planning and simulation modules operate on the generated data, while analytics exports provide the dashboard with its reporting data.

## 3. Delivery Assignment and Route-Planning Approach

### Delivery Assignment

The assignment module matches pending deliveries with eligible driver shifts and vehicles.

The assignment process considers:

- Required vehicle type.
- Vehicle capacity in delivery units.
- Vehicle weight capacity.
- Driver and vehicle availability.
- Shift timing.
- Delivery time-window overlap.
- Vehicle restrictions.
- Remaining shift capacity and service time.

A deterministic best-fit selection strategy is used to assign deliveries to suitable shifts.

The assignment process is a planning preview and does not directly modify delivery statuses.

### Route Planning

The route planner uses a deterministic beam-search heuristic to construct delivery routes.

The implementation:

1. Groups assigned deliveries by planning date and shift.
2. Evaluates candidate delivery stops.
3. Calculates travel time using the base travel-time matrix.
4. Adjusts travel time using the selected traffic scenario.
5. Estimates arrival and departure times.
6. Applies time-window and shift feasibility checks.
7. Retains promising route states using a bounded beam search.
8. Records deliveries that cannot be included in feasible routes as unplanned.

The beam width is configured to 40.

The algorithm aims to construct feasible routes; it does not guarantee globally optimal routes.

## 4. Constraints and Assumptions

### Operational Constraints

The planning system checks the following conditions:

| Constraint | Implementation |
|---|---|
| Vehicle unit capacity | Prevents exceeding available delivery capacity |
| Vehicle weight capacity | Checks total delivery weight |
| Vehicle type | Matches delivery requirements |
| Driver shift | Ensures route activity fits within shift limits |
| Vehicle availability | Checks vehicle activity and effective dates |
| Driver availability | Checks driver activity and effective dates |
| Vehicle restrictions | Prevents restricted vehicle-site assignments |
| Hard time windows | Rejects late arrivals |
| Soft time windows | Allows lateness with a penalty |
| Service duration | Includes delivery service time |
| Route duration | Enforces maximum route duration |
| Break allowance | Reserves break time before shift end |

### Planning Assumptions

- The project uses synthetic data rather than live logistics data.
- The first planned stop has zero initial travel time because no depot starting location is modeled.
- Travel times are based on a generated base matrix and daily traffic multipliers.
- The traffic scenarios are LOW, NORMAL, and HEAVY.
- Driver break time is reserved at the end of the shift rather than scheduled as an explicit route stop.
- SOFT time-window violations are permitted and recorded.
- Route planning is heuristic and may leave some otherwise assignable deliveries unplanned.

## 5. Delivery Simulation Methodology

After routes are persisted, the simulation module generates delivery execution outcomes.

### Simulation Design

- Uses a fixed random seed of `20261022` for reproducibility.
- Simulates execution for persisted planned route stops.
- Introduces a 5% random delivery failure rate.
- Adds cumulative arrival delays of 0–8 minutes.
- Records delivery outcomes and status transitions.
- Creates delivery and route event records.
- Classifies deliveries as DELIVERED, FAILED, or UNSERVED.

### Simulation Results

| Outcome | Deliveries |
|---|---:|
| Delivered | 791 |
| Failed | 43 |
| Unserved | 1,166 |
| **Total** | **2,000** |

The simulation is a synthetic execution model, not a live tracking system.

## 6. Analytics and Dashboard

The analytics module generates performance reports from the persisted delivery outcomes and route information.

### Generated Reports

| Report | Description |
|---|---|
| `analytics_summary.json` | Overall performance summary |
| `delivery_performance.csv` | Individual delivery results |
| `daily_performance.csv` | Daily delivery performance |
| `priority_performance.csv` | Performance by delivery priority |
| `route_performance.csv` | Route-level performance |
| `soft_window_lateness.csv` | Soft-window lateness analysis |

### Key Performance Indicators

| Metric | Result |
|---|---:|
| Total deliveries | 2,000 |
| Delivered deliveries | 791 |
| Failed deliveries | 43 |
| Unserved deliveries | 1,166 |
| Delivery success rate | 39.55% |
| On-time rate among delivered deliveries | 91.28% |
| Total routes | 155 |
| Planned stops | 834 |
| Total planned distance | 12,794.15 km |
| Average stops per route | 5.38 |

### Interactive Dashboard

The Streamlit dashboard provides:

- Delivery outcome KPIs.
- Delivery status distribution.
- Daily performance trends.
- Priority-wise performance.
- Route performance analysis.
- Delivery-level details.
- Interactive filters.
- Downloadable reports.

Run the dashboard using:

```bash
streamlit run app.py
```

Then open the local URL displayed in the terminal.

## 7. Validation and Testing Results

The project includes database integrity checks, data validation scripts, planning validation, and unit tests for operational constraints.

### Validation Results

| Validation | Result |
|---|---|
| Database schema | 16 tables verified |
| Foreign-key integrity | PASS |
| Master data counts | PASS |
| Transaction validation | PASS |
| Travel matrix validation | PASS |
| Base travel matrix | 249,500 directed pairs |
| Traffic scenario manifest | 90 records |
| Constraint unit tests | 11 passed, 0 failed |
| Python compilation | PASS |
| Route preview validation | PASS |
| Route constraint validation | PASS |

### Route Preview Validation

Before simulation, route preview validation confirmed:

- No duplicate planned deliveries.
- No hard time-window violations.
- No invalid route sequences.
- No invalid departure times.
- Planned and unplanned deliveries accounted for all 2,000 pending deliveries.

The route constraint validation also reported no validation errors. Soft-window lateness warnings were recorded separately.

### Reproducibility

The synthetic data generators and simulation use fixed seeds to support repeatable results.

The saved database and generated reports represent the completed demonstration run.

## 8. Limitations and Future Improvements

### Current Limitations

1. **Synthetic data:** Results are based on generated data and may not represent real-world delivery operations.
2. **Heuristic optimization:** Beam search does not guarantee globally optimal routing.
3. **Unplanned deliveries:** Only 834 of the 2,000 deliveries were included in planned routes. The remaining deliveries were recorded as unserved in the simulation.
4. **No live GPS integration:** Actual vehicle locations and live route tracking are not implemented.
5. **No real-time traffic API:** Traffic conditions are represented using generated scenario multipliers.
6. **No depot modeling:** Initial travel from a depot to the first delivery is not included.
7. **Break scheduling:** Break time is reserved at the end of a shift rather than optimized within the route.
8. **Simulation simplification:** Delivery failures and delays are generated synthetically rather than derived from actual operational events.

### Future Improvements

- Integrate real-world mapping and traffic APIs.
- Introduce depot-aware route planning.
- Improve routing using advanced optimization algorithms.
- Add dynamic vehicle reassignment and route replanning.
- Implement real-time GPS tracking.
- Improve the handling of unplanned deliveries.
- Add more realistic driver breaks and operational constraints.
- Expand simulation scenarios and anomaly detection.
- Improve dashboard filtering and operational monitoring.

## Project Summary

SmartFleet demonstrates an end-to-end logistics planning and analytics workflow, covering synthetic data generation, resource assignment, constraint-aware route planning, route persistence, delivery simulation, analytics, and interactive visualization.

The project emphasizes reproducibility, modular design, operational feasibility, validation, and transparent reporting of results and limitations.