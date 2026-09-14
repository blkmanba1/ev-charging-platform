# SP1 — EV Charging Data Analysis and Demand Forecasting

**Owner:** Xu Yuxuan (徐宇轩)
**Consumes:** Chinese public EV charging datasets (session records or hourly load series)
**Produces:** `data/processed/sp1-demand-forecast-v1.csv` → SP2, SP4, SP5
**Status:** Phase 1/2 implementation running on real data (see *Results* below)

## Tasks (from the official brief)

- Collect and preprocess public EV charging datasets. → `src/sp1/ingest.py`, `src/sp1/hourly.py`
- Analyse charging patterns and user behaviour. → `src/sp1/hourly.py::profile`, `data/interim/sp1-pattern-summary-v1.json`
- Develop machine learning models to predict future charging demand. → `src/sp1/features.py`, `src/sp1/models.py`
- Evaluate forecasting accuracy and model performance. → rolling-origin backtest in `src/sp1/models.py`

## Quick start

```bash
# 0. environment (from the repository root)
python -m venv .venv
.venv\Scripts\activate                 # Windows;  source .venv/bin/activate elsewhere
pip install -r requirements.txt

# 1. download + verify + unpack the raw dataset (never committed)
python subprojects/sp1-data-forecasting/scripts/fetch_datasets.py --list
python subprojects/sp1-data-forecasting/scripts/fetch_datasets.py --dataset cn-charging-orders

# 2. run the whole pipeline (raw -> interim -> processed)
python subprojects/sp1-data-forecasting/scripts/run_sp1.py --dataset cn-charging-orders

# 3. tests
python -m pytest subprojects/sp1-data-forecasting/tests -q
```

Useful flags: `--models naive_daily,ridge` (fast subset), `--forecast-days 5`,
`--horizon 24`, `--no-interim`, `--synthetic --days 120 --evs 200` (labelled fallback).

## Layout

```
sp1-data-forecasting/
├── README.md                     this file
├── config/datasets.yaml          raw-dataset adapters (column maps, timezones, licences)
├── scripts/
│   ├── fetch_datasets.py         download + SHA-256 verify + unpack
│   └── run_sp1.py                end-to-end CLI
├── src/sp1/
│   ├── contract.py               contract-compliant CSV + .meta.json read/write/validate
│   ├── config.py                 repository paths and SP1 settings
│   ├── ingest.py                 raw dataset -> canonical session table
│   ├── hourly.py                 sessions -> gap-free 1-hour demand; patterns; baseline
│   ├── features.py               calendar / lag / naive features, supervised samples
│   ├── models.py                 model zoo, metrics, rolling-origin backtest, intervals
│   ├── pipeline.py               end-to-end orchestration
│   └── synthetic.py              labelled synthetic fallback (never presented as measured)
├── tests/                        72 tests, no network or dataset needed
└── notebooks/                    exploration (empty for now)
```

## Design decisions (and why)

1. **Direct multi-horizon forecasting with the horizon as a feature.** One model predicts the
   whole next 24 hours from a single origin, instead of recursing a one-step model 24 times.
   No error accumulation, and a single fit per origin keeps the backtest affordable.
2. **Calendar features describe the *target* interval; lag features describe the *origin*.**
   Calendar values are known in advance, so using them is legitimate; lag and rolling features
   are shifted so they can never see the interval being predicted. `features.assert_no_leakage`
   recomputes every lag from the raw series and fails loudly if that ever stops being true.
3. **Honest evaluation: rolling origin, retrained per origin, targets strictly out of sample.**
   Origins are anchored to local midnight, so each one is a genuine "day-ahead forecast".
   `test_rolling_backtest_never_trains_on_future_targets` pins the training boundary with a ramp
   series, because a leaky backtest reports fantasy accuracy.
4. **Naive baselines are first-class models.** `naive_daily` (same hour yesterday) and
   `naive_weekly` are scored in the same table as ridge / random forest / gradient boosting /
   XGBoost. SP1 has to show the ML model *earns its complexity*; on aggregate demand it often
   does not, and that is a finding worth reporting rather than hiding.
5. **WAPE leads the metrics.** Demand is zero or near-zero for much of the day, which makes MAPE
   explode; WAPE (total absolute error ÷ total demand) is stable and reads naturally.
6. **Confidence bounds are empirical, not model-based.** `prediction ± 1.645 × σ(residual)` at the
   same horizon, taken from the backtest. The method is stated in the `.meta.json` so SP5 does not
   mistake it for a model-derived interval.
7. **The 1-hour demand series is *connected charging power*.** For session data, energy is spread
   across the hourly intervals a session overlaps, in proportion to overlap. That is the load the
   grid sees; see `data/README.md` for the caveat that the source `power` column is a rating.
8. **The "uncontrolled" baseline keeps each session's own power.** Moving every session's energy
   to 18:00 local at a fixed 7 kW would stretch a 150 kW fast-charge session over 40 hours,
   which is not a scenario, it is a bug. Energy is conserved; only the timing changes.
9. **Synthetic data is a labelled fallback, never a substitute.** `sp1.synthetic` exists so the
   tests are deterministic and so SP2 is not blocked if a dataset disappears; every output it
   produces carries `"synthetic": true` in its meta file and the word SYNTHETIC in its source.

## Outputs

| File | Written by | Purpose |
|---|---|---|
| `data/processed/sp1-demand-forecast-v1.csv` + `.meta.json` | pipeline | **the contract deliverable** — day-ahead predicted demand with 90% bounds |
| `data/processed/sp1-baseline-demand-v1.csv` + `.meta.json` | pipeline | "uncontrolled" comparison profile for the same window |
| `data/interim/sp1-sessions-canonical-v1.csv` | pipeline | canonical session table (one schema for any raw dataset) |
| `data/interim/sp1-hourly-demand-v1.csv` | pipeline | the gap-free 1-hour demand series |
| `data/interim/sp1-backtest-v1.csv` | pipeline | out-of-sample predictions next to the actuals |
| `data/interim/sp1-model-metrics-v1.json` | pipeline | full metric set per model, per horizon |
| `data/interim/sp1-pattern-summary-v1.json` | pipeline | charging pattern by local hour (behaviour analysis) |

All `data/` outputs are git-ignored: they are regenerated by one command.

## Results

### Dataset: figshare 28263986 — Beijing + Shanghai + Guangzhou public charging orders

1,295,394 sessions from 1,847 stations across 33 days (2024-01-17 → 2024-02-18),
aggregated into 786 hourly intervals (89.2 GWh of connected charging power).

**Charging pattern (local time, mean across the window):** a pronounced midday peak
(12:00–13:00, 6.3–6.6% of daily energy each) and a broad evening plateau (19:00–23:00), with the
trough at 04:00–05:00 (2.1–2.2%). This is *public* charging behaviour, not residential: the
18:00 home-charging peak of the project brief does not appear in this dataset, and the brief's
"50 EVs plug in at 18:00" scenario therefore has to be built as a stated scenario rather than
read off the data.

**Forecast accuracy (rolling origin, one day-ahead forecast per local day, 18 origins × 24 h =
432 out-of-sample intervals, all models retrained per origin):**

| Model | WAPE | MAE (kWh/h) | RMSE (kWh/h) | R² |
|---|---|---|---|---|
| `naive_daily` (same hour yesterday) | **0.0871** | 8,314 | 12,747 | 0.864 |
| `gradient_boosting` (sklearn) | 0.1040 | 9,934 | 14,536 | 0.823 |
| `xgboost` | 0.1047 | 9,998 | 14,458 | 0.825 |
| `random_forest` | 0.1103 | 10,531 | 15,395 | 0.802 |
| `ridge` (with all lag/rolling/calendar features) | 0.1468 | 14,017 | 18,397 | 0.717 |
| `naive_weekly` (same hour last week) | 0.2928 | 27,968 | 33,797 | 0.045 |
| `hour_of_week_profile` | 0.3403 | 32,499 | 39,248 | −0.288 |

**The headline result is uncomfortable and must be reported as it stands: the zero-cost
`naive_daily` baseline beats every machine-learning model.** Gradient boosting gets closest
(WAPE 0.104 vs 0.087 — about 19% worse in relative terms) and it is the best *learned* model, but
it does not earn its complexity on this data. Two honest readings:

- with 18 forecast origins and one month of history, the tree models cannot learn a cleaner
  "copy yesterday, adjusted" mapping than the plain copy itself — and `naive_daily_kwh` is already
  one of their input features, so this is a genuine finding about the data, not a features bug;
- forecast error is flat across the horizon (per-horizon WAPE 0.072–0.103, no trend from h=1 to
  h=24), which is the signature of a series dominated by a stable daily cycle.

**What would change that** (the next iteration, not a claim): exogenous drivers the model cannot
see today — day type / holiday calendar, temperature, station-level capacity and occupancy,
tariff windows — plus a longer history covering more than one month. `sp1.model` in `config.yaml`
pins the model explicitly if the team prefers to publish the learned model rather than the
baseline; the meta file always records the full ranking either way.

### Deliverable comparison: uncontrolled vs forecast

Both contract files cover the same 432 hours (2024-01-30 17:00Z → 2024-02-17 16:00Z):

| Quantity | Forecast (day-ahead) | Uncontrolled baseline (all plug in at 18:00 local) |
|---|---|---|
| Total energy | 42,078 MWh | 41,270 MWh (conserved to 0.02% of the actual 41,260 MWh) |
| Mean load | 97,404 kW | 95,532 kW |
| **Peak hour** | **208 MWh** | **2,409 MWh — 11.6× the forecast peak** |
| 90% interval width (mean) | 40,318 kWh | not modelled (empty, per contract) |

The 11.6× peak amplification is the concrete version of the brief's "50 EVs at 18:00" story at
1,847-station scale, and it is the number SP2's scheduler exists to reduce. The forecast carries a
flat +1.98% energy bias over the same window, and its 90% interval is wide (≈41% of the mean) —
both stated here rather than buried, and both recorded in the meta file.

## Known limitations

- **`power` is a rating** (see `data/README.md`), so absolute kWh totals are an upper bound.
  Comparisons between strategies are still valid because both sides use the same series.
- **33 days is one month.** Seasonal effects (month, holiday) cannot be learned; `month` is in the
  feature set but is nearly constant. A longer dataset is the single biggest upgrade available.
- **No vehicle-level data**, so the "aggregate vs per-EV" question in
  `docs/integration-contract.md` cannot be answered from this dataset — SP1 currently forecasts
  **aggregate** demand, which is the default the contract assumes. The per-EV variant needs a
  dataset with vehicle identifiers.
- **No tariff column**, so SP1 does not produce cost; that stays with SP2/SP5.
- **Midday-peak ≠ brief's evening-peak scenario.** The scenario files remain SP2's job; SP1
  supplies the demand and the uncontrolled baseline.
