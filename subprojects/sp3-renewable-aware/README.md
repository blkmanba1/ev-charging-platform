# SP3 — Renewable-Aware Charging Management

**Owner:** *not yet allocated — see the supervisor*
**Consumes:** public solar/PV datasets
**Produces:** `data/processed/sp3-solar-forecast-v1.csv` → SP2, SP4, SP5

## Tasks (from the official brief)
- Model solar photovoltaic generation using public datasets.
- Develop charging strategies that maximise renewable energy utilisation.
- Analyse the impact of renewable integration on charging performance and energy consumption.

## Candidate datasets
**China-specific** — see `data/README.md`. ERA5 reanalysis and NASA POWER are the pragmatic
choice (free, hourly, no registration, defensible in a dissertation); CMA / data.cma.cn provide
measured observations where available.

## Status
The official brief lists **five** students; the project email lists four. This sub-project is
still unallocated. Two questions for the supervisor:
1. Who owns SP3, and when do they join?
2. Until then, does SP2 assume zero solar, or should someone cover it provisionally?

## Output contract
See `docs/integration-contract.md` → *SP3 → SP2 · Renewable generation forecast*.

## Layout
```
src/
notebooks/
```
