# Architecture

Phase 1 uses a modular Python application with SQLite persistence. Data generation, planning, simulation, validation, analytics, and UI are separate layers. SQLite foreign-key enforcement is enabled for every application connection. See `database/schema.sql` for relational constraints.
