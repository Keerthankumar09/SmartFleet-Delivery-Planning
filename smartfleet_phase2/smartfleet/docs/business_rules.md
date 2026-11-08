# Business Rules

1. Generate parent/master records before dependent records.
2. All generated identifiers are deterministic, zero-padded, immutable business IDs.
3. Every delivery must be assigned to a route or explicitly marked UNSERVED.
4. Capacity is checked in both units and kilograms.
5. HARD time windows and driver shifts are hard constraints; SOFT windows contribute lateness penalties.
6. Vehicle/site restrictions and required vehicle types must be respected.
7. Service time is included in route duration.
8. Failed deliveries require a reason code.
9. Derived metrics are calculated from source rows, never independently randomized.
10. Ground-truth labels are kept out of planner input features.
11. Operational changes are appended to event tables; event history is not overwritten.
