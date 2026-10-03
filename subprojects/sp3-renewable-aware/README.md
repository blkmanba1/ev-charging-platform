# SP3 — Renewable-Aware Charging Management

**Owner:** *not yet allocated — see the supervisor*
**Consumes:** public solar/PV datasets
**Produces:** `data/processed/sp3-solar-forecast-v1.csv` → SP2, SP4, SP5

## Tasks (from the official brief)
- Model solar photovoltaic generation using public datasets.
- Develop charging strategies that maximise renewable energy utilisation.
- Analyse the impact of renewable integration on charging performance and energy consumption.

## Candidate datasets
**Region: matches SP1's sites — see contract amendment A1.** The kickoff China lock is retired, so
the "China-specific" wording that used to be here no longer applies. ERA5 reanalysis and NASA POWER
are the pragmatic choice (free, hourly, no registration, defensible in a dissertation) and cover the
sites in use; CMA / data.cma.cn would only apply if the region returned to China.

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
