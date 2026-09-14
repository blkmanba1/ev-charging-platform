# Integration Contract — Subsystem Interfaces

**Status:** v0.1 draft — to be agreed at the kickoff meeting
**Owner:** whole team · **Change process:** open a PR, ping the affected owner(s) for review

---

## Why this document exists

The supervisor's warning was explicit: the biggest risk to this project is a
**last-minute integration bottleneck**. Each of us owns an independent subsystem, but our
individual outputs are each other's inputs. If SP2 invents one CSV format and SP4 expects
another, we lose a week in Month 5 — exactly when we can least afford it.

So we agree the interfaces **now**, while everything is still cheap to change.

---

## Four rules

1. **`timestamp` is always ISO-8601, always in UTC, always ending in `Z`.**
   Example: `2026-09-26T14:00:00Z`. Local time is a display concern — SP4 handles it.
   This single rule removes the most common class of integration bug.

2. **Units live in the column name.** `kwh`, `kw`, `gbp`, `gco2`, `ratio`. Never assume.

3. **Every output file ships with a sibling `.meta.json`** carrying `schema_version`,
   `generated_at`, `generated_by` (SP id), `source`, and the units used. SP4 reads the meta,
   not the filename, to decide how to render.

4. **A schema change is a PR against this document**, reviewed by every downstream owner.
   Bump `schema_version` (minor for additive, major for breaking). Never silently change a
   column's meaning.

---

## Interchange format

- **Time series** → CSV (`.csv`), one header row, UTF-8, comma-separated, no index column.
- **Scalar summaries / configuration** → JSON (`.json`), UTF-8.
- All timestamps at a **fixed resolution per file** — state it in the meta as
  `resolution: 15min | 30min | 1h`.
- Missing values are **empty cells**, never `NaN`, `null`, `-`, or `N/A`.
- File naming: `<sp>-<content>-<version>.csv`, e.g. `sp1-demand-forecast-v1.csv`.

---

## SP1 → SP2 · Demand forecast

**File:** `data/processed/sp1-demand-forecast-v1.csv`
**Produced by:** SP1 (Xu Yuxuan) · **Consumed by:** SP2 (Xie Letian), SP4, SP5

| Column | Type | Unit | Meaning |
|---|---|---|---|
| `timestamp` | string | — | ISO-8601 UTC, interval **start** |
| `predicted_demand_kwh` | float | kWh | Predicted energy demanded in this interval |
| `lower_bound_kwh` | float | kWh | Lower confidence bound (empty if not modelled) |
| `upper_bound_kwh` | float | kWh | Upper confidence bound (empty if not modelled) |

**Optional second file** for the "uncontrolled" baseline comparison:
`data/processed/sp1-baseline-demand-v1.csv`, identical columns, representing the
uncoordinated "everyone plugs in at 18:00" profile. Phase 3 testing depends on this.

**SP2 can rely on:** a gap-free series, no missing intervals, non-negative values, and at least
30 days of history to schedule against.

---

## SP2 → SP5 and SP2 → SP4 · Charging schedule

**File:** `data/processed/sp2-charging-schedule-v1.csv`
**Produced by:** SP2 (Xie Letian) · **Consumed by:** SP5, SP4

| Column | Type | Unit | Meaning |
|---|---|---|---|
| `timestamp` | string | — | ISO-8601 UTC, interval start |
| `ev_id` | string | — | Opaque EV identifier (stable across files) |
| `allocated_power_kw` | float | kW | Power assigned in this interval |
| `allocated_energy_kwh` | float | kWh | Energy delivered in this interval |
| `strategy` | string | — | `uncontrolled` \| `tou` \| `optimised` |
| `tariff_gbp_per_kwh` | float | GBP/kWh | Tariff applied to this interval |
| `interval_cost_gbp` | float | GBP | Cost of this interval |

**Scenario files** (Phase 3 "Uncontrolled vs Intelligent"):
`data/processed/sp2-scenario-<name>-v1.csv` with the same columns, where `<name>` is
`uncontrolled` or `intelligent`.

**SP5 can rely on:** every row's `allocated_energy_kwh` is consistent with
`allocated_power_kw` and the stated resolution, and `strategy` is one of the three literals.

---

## SP3 → SP2 · Renewable generation forecast

**File:** `data/processed/sp3-solar-forecast-v1.csv`
**Produced by:** SP3 (unallocated) · **Consumed by:** SP2, SP4, SP5

| Column | Type | Unit | Meaning |
|---|---|---|---|
| `timestamp` | string | — | ISO-8601 UTC, interval start |
| `solar_generation_kwh` | float | kWh | Forecast PV generation in this interval |

SP2 uses this to bias charging into high-generation windows. **Until SP3 delivers, SP2 must
not block** — treat missing solar as zero and keep the interface clean.

---

## SP5 → SP4 · Economic & environmental assessment

**File:** `data/processed/sp5-assessment-v1.json`
**Produced by:** SP5 (He Zimo) · **Consumed by:** SP4

```json
{
  "schema_version": "1.0",
  "scenario": "intelligent",
  "baseline_scenario": "uncontrolled",
  "period": { "start": "2026-09-26T00:00:00Z", "end": "2026-10-26T00:00:00Z" },
  "cost_gbp": 412.55,
  "baseline_cost_gbp": 587.10,
  "cost_saving_gbp": 174.55,
  "cost_saving_ratio": 0.297,
  "co2_kg": 1180.4,
  "baseline_co2_kg": 1720.9,
  "co2_saving_kg": 540.5,
  "co2_saving_ratio": 0.314,
  "carbon_intensity_gco2_per_kwh": 233.0,
  "peak_demand_reduction_kw": 46.2
}
```

Optional time series alongside it: `data/processed/sp5-savings-timeline-v1.csv` with
`timestamp`, `cost_gbp`, `baseline_cost_gbp`, `co2_kg`, `baseline_co2_kg`.

---

## Cross-cutting: the meta file

Every output file above is accompanied by `<same-name>.meta.json`:

```json
{
  "schema_version": "1.0",
  "generated_at": "2026-10-01T09:12:00Z",
  "generated_by": "SP1",
  "source": "ACN-Data (Caltech), 2019-2020 subset",
  "resolution": "15min",
  "timezone": "UTC",
  "units": { "predicted_demand_kwh": "kWh" }
}
```

---

## Open questions to settle at kickoff

- [ ] What **resolution** do we standardise on — 15 min or 1 h? (SP2's optimiser cost scales with it.)
- [ ] Which **currency** for cost — GBP or CNY? (Supervisor is UK-based; display can convert in SP4.)
- [ ] Does SP1 forecast **aggregate** demand, or **per-EV**? Affects whether SP2 schedules fleets or individuals.
- [ ] Who owns the **shared tariff table** — SP2 or SP5?
- [ ] Do we standardise on **JSON or CSV** for the Phase 3 scenario hand-off? (Currently: CSV.)
