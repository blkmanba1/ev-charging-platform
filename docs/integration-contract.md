# Integration Contract — Subsystem Interfaces

**Status:** v0.2 — core decisions locked at kickoff
**Owner:** whole team · **Change process:** open a PR, ping the affected owner(s) for review

## Locked decisions

| Decision | Value | Rationale |
|---|---|---|
| Time resolution | **1 hour** | Keeps the SP2 optimiser tractable; ample for day-ahead scheduling |
| Currency | ~~**CNY (¥)**~~ → **see amendment A1** | Original rationale assumed China-only datasets |
| Region | ~~**China**~~ → **see amendment A1** | Original rationale assumed China-only datasets — **approved by the supervisor** |
| Timezone for storage | **UTC** | Local display handled by SP4 |
| Scenario hand-off format | **CSV** | Matches the time-series convention below |

### Amendments after kickoff

**A1 — 2026-09-14 · Region and currency.** Status: the region change is **confirmed acceptable by
the supervisor** (he accepts either Chinese or US data), so this is no longer an open approval item;
the currency/tariff knock-on below still needs SP2 and SP5 to acknowledge it.
SP1 reviewed the three sources the supervisor recommended and searched for official Chinese
equivalents. Finding: **no official Chinese source publishes session-level charging data**, while
two supervisor-recommended sources (City of Boulder, City of Palo Alto) are official municipal open
data (CC0 / PDDL) with metered kWh per session. The team therefore runs SP1 on those official
datasets, which invalidates two locks above:

- **Region:** no longer China-only. SP1's demand series and the uncontrolled baseline are for
  **Boulder and Palo Alto (USA)**. The file formats in this document are unchanged.
- **Currency:** CNY has no basis in these datasets — they contain **no tariff or price column at
  all**. SP2 must source a tariff schedule for the chosen region (US utility rates) before it can
  populate `tariff_cny_per_kwh`/`interval_cost_cny`. **Owner SP2**; the source survey is complete and
  written up in `docs/tariff-sources.md` (verified artefacts in `data/raw/tariff/`, ToU period
  mapping from OpenEI URDB, all-in prices from Xcel's own rate summaries). One sub-decision is still
  open: Palo Alto 2011–2020 has no ToU tariff available, so it is either priced on its tiered
  residential schedule, declared out of ToU scope, or resolved by enumerating the City's records
  portal.
- **Column names are deliberately not renamed yet.** `tariff_cny_per_kwh` and `interval_cost_cny`
  keep their names so nothing downstream breaks; if the team locks USD, that is a *minor* schema
  bump and a rename in the same PR.
- **What survives:** 1-hour resolution, UTC storage, ISO-8601 `Z` timestamps, CSV hand-off, the
  sibling `.meta.json`, and every file/column definition below.

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

2. **Units live in the column name.** `kwh`, `kw`, `cny`, `gco2`, `ratio`. Never assume.

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
- All timestamps at a **fixed 1-hour resolution**. `resolution` is `"1h"` in every meta file.
  Interval boundaries are on the hour, UTC.
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
| `tariff_cny_per_kwh` | float | CNY/kWh | Tariff applied to this interval |
| `interval_cost_cny` | float | CNY | Cost of this interval |

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
  "cost_cny": 412.55,
  "baseline_cost_cny": 587.10,
  "cost_saving_cny": 174.55,
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
`timestamp`, `cost_cny`, `baseline_cost_cny`, `co2_kg`, `baseline_co2_kg`.

---

## Cross-cutting: the meta file

Every output file above is accompanied by `<same-name>.meta.json` — i.e. the `.csv` suffix is
replaced, so `data/processed/sp1-demand-forecast-v1.csv` pairs with
`data/processed/sp1-demand-forecast-v1.meta.json`. (SP1 implements exactly this; if SP4 expected
`sp1-demand-forecast-v1.csv.meta.json`, say so and this line becomes the decision.) Fields:

```json
{
  "schema_version": "1.0",
  "generated_at": "2026-10-01T09:12:00Z",
  "generated_by": "SP1",
  "source": "ACN-Data (Caltech), 2019-2020 subset",
  "resolution": "1h",
  "timezone": "UTC",
  "units": { "predicted_demand_kwh": "kWh" }
}
```

---

## Decisions made at kickoff

- [x] **Resolution: 1 hour.** SP2's optimiser cost was the deciding factor.
- [x] **Currency: CNY.** All datasets are China-specific, so GBP would mean an extra, pointless
      conversion. SP4 may display another unit if the supervisor asks, but storage is CNY.
- [x] **Scenario hand-off: CSV.**
- [x] **Region: China.** This applies to the data as well — EV charging datasets, tariff
      structures, solar resource, and grid carbon intensity must all be Chinese sources.
      See `data/README.md` for candidates.

- [x] **Chinese datasets: approved by the supervisor.** The kickoff email suggested ACN-Data
      (Caltech), Boulder Colorado, and UK National Grid data, but the team asked whether a
      China-focused dataset would be acceptable for a project targeting the Chinese market, and
      **Dr Ghias confirmed that Chinese data may be used.** The international datasets are
      therefore superseded — no dual-dataset work is required.

      *Housekeeping:* `data/README.md` still lists the original international suggestions under a
      historical note. That is deliberate, so the reason for the choice stays documented if he
      asks about it later.

## Still open

- [ ] Does SP1 forecast **aggregate** demand, or **per-EV**? Affects whether SP2 schedules
      fleets or individuals. **Blocks SP2's optimiser design — settle first.**
      *Status 2026-09-14:* SP1 delivers **aggregate** demand. The dataset SP1 secured
      (`data/README.md`) has no vehicle identifier, so per-EV output is not derivable from it;
      the file format above is unchanged either way, and SP2 can build against the aggregate
      profile now. Still worth confirming with the supervisor that aggregate is acceptable.
- [ ] Who owns the **shared tariff table** — SP2 or SP5? (Recommendation: SP2, since SP2 is the
      only consumer that needs it at run time; SP5 reads it read-only.)
- [ ] Which **Chinese grid carbon intensity** source do we cite for SP5's baseline? A published
      national/provincial factor is preferable to a self-computed one — it will need a citable
      reference in the dissertation.
- [ ] Does the **UK supervisor expect GBP** anywhere in the final report? If so, SP5 produces CNY
      as the primary figure and adds a GBP conversion column at report time only.
