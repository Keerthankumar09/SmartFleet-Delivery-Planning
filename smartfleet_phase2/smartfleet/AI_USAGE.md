# AI Usage Disclosure

## 1. Overview

AI tools, including ChatGPT, were used as development assistants during the implementation of the SmartFleet – Delivery Planning and Logistics Analytics project.

AI assistance was primarily used to accelerate development, understand implementation approaches, troubleshoot errors, improve code organization, and prepare technical documentation.

The final implementation was reviewed and executed locally, with validation results checked during development.

## 2. Areas Where AI Assisted

### Project Architecture and Planning
- Helped organize the project into development phases.
- Suggested a modular Python project structure.
- Assisted with identifying database entities and relationships.
- Helped break the overall logistics workflow into smaller implementation tasks.

### Data Generation and Database
- Assisted with synthetic master data and transaction generation.
- Helped identify database integrity requirements.
- Assisted with travel-time matrix generation and traffic scenario design.
- Helped troubleshoot data validation and database errors.

### Delivery Assignment and Route Planning
- Assisted with implementing vehicle and driver eligibility checks.
- Helped develop capacity, shift, service-time, and delivery-window constraints.
- Assisted with the deterministic assignment and beam-search route-planning approach.
- Helped diagnose route feasibility and unplanned delivery issues.

### Simulation and Analytics
- Assisted with delivery outcome simulation logic.
- Helped troubleshoot timestamp and timezone handling.
- Assisted with generating delivery, daily, priority, and route performance reports.
- Helped interpret analytics results.

### Dashboard and Documentation
- Assisted with Streamlit dashboard development.
- Helped organize KPI reporting and interactive visualizations.
- Assisted in preparing README documentation and the data dictionary.

## 3. Where AI Accelerated Development

AI reduced the time spent on:
- Structuring a multi-module Python application.
- Understanding and implementing operational constraints.
- Troubleshooting Python exceptions and SQL issues.
- Developing validation scripts.
- Preparing documentation and submission materials.

AI was particularly useful as an iterative debugging and implementation assistant.

## 4. Personal Contributions and Review

My responsibilities included:

- Defining the project objective and following the required development workflow.
- Creating and maintaining the project files in the local development environment.
- Executing the Python scripts and reviewing their terminal output.
- Identifying errors and sharing relevant code and tracebacks for troubleshooting.
- Applying suggested changes and rerunning affected scripts.
- Reviewing generated data counts and database integrity results.
- Running validation scripts and checking their results.
- Running the Streamlit dashboard locally.
- Reviewing the final analytics results and project outputs.

The project was not treated as complete merely because code was generated. Implementation steps were followed by local execution and validation.

## 5. Validation Evidence

The following checks were executed locally:

- Database validation: 16 tables verified and foreign-key integrity passed.
- Master data validation: passed.
- Transaction validation: passed for 2,000 orders, deliveries, and time windows.
- Travel matrix validation: passed for 249,500 directed pairs.
- Traffic scenario validation: 90 records verified.
- Constraint tests: 11 passed, 0 failed.
- Route preview validation: passed before delivery simulation.
- Route constraint validation: passed before delivery simulation.
- Python compilation: completed without syntax errors.
- Streamlit dashboard: launched successfully.

## 6. Limitations and Responsibility

AI-generated suggestions can contain errors or require adaptation to the existing codebase. Suggested implementations were therefore applied and checked in the local environment.

The project uses synthetic data and a simplified delivery simulation. The results should not be interpreted as evidence of production deployment or real-world logistics performance.

I take responsibility for understanding, reviewing, and explaining the submitted implementation, including its assumptions, limitations, and validation results.

## 7. AI Tool

- Tool used: ChatGPT
- Primary role: Development assistance, debugging, code explanation, validation guidance, and documentation support.