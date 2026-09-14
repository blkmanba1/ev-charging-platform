# Data directory

**Datasets are never committed to this repository.** The sub-folders below are git-ignored;
only this README (and `.gitkeep` placeholders) are tracked.

```
data/
├── raw/        # exactly as downloaded — never edit these files
├── interim/    # partially cleaned, intermediate artefacts
└── processed/  # contract-compliant outputs that other subsystems consume
```

## Rules

1. **`raw/` is read-only.** Never overwrite. If a file is wrong, re-download it.
2. **`processed/` obeys `docs/integration-contract.md`.** That is the whole point of the folder.
3. Every dataset you bring in gets a row in the table below **in the same PR**.

## Dataset register

| Dataset | Owner (SP) | Source URL | Licence | Downloaded | Size | Notes |
|---|---|---|---|---|---|---|
| *(none yet — SP1 to start)* | | | | | | |

## Candidate datasets (from the supervisor)

| Dataset | Likely use | Notes |
|---|---|---|
| **ACN-Data** (Caltech/JPL) | SP1 demand forecasting | Real workplace charging sessions, ~30+ months; widely used in the literature |
| **Boulder, Colorado EV data** | SP1 demand forecasting | City-level charging behaviour |
| **UK National Grid data** | SP1 / SP2 / SP5 | Demand, generation mix, and carbon intensity — good for `gCO2/kWh` baselines |
| **Elexon / NESO (UK) tariff & half-hourly data** | SP2 scheduling | Time-of-use and dynamic tariff structures |
| **PVGIS / NREL NSRDB / Solcast** | SP3 solar generation | Irradiance and PV output modelling |
| **Open Charge Map** | SP4 monitoring | Charging station locations and metadata |

## Quick check before you commit

```bash
git status --short          # nothing under data/raw, data/interim, data/processed should appear
```
