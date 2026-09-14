# SP4 — Charging Monitoring and Visualisation Platform

**Owner:** Li Chunren (李春仁)
**Consumes:** SP1 forecast, SP2 schedule, SP3 solar, SP5 assessment
**Produces:** the user-facing dashboard — the thing people actually see

## Tasks (from the official brief)
- Design a charging monitoring architecture.
- Develop a software dashboard to display charging status, energy consumption, and charging costs.
- Implement data visualisation and reporting functions.

## Recommended stack (from the supervisor)
Python (Dash / Streamlit) **or** React / Node.js, paired with a lightweight database
(SQLite / PostgreSQL).

## Suggested views
Real-time charging status · predicted demand vs actual · cost savings · environmental impact

## Output contract
Consumes every other subsystem's output file. Read `docs/integration-contract.md` in full —
you are the integration point, so you will find interface bugs before anyone else does.

## Layout
```
app/          # dashboard application
assets/       # static files, styles
```
