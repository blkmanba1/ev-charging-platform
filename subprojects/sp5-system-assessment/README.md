# SP5 — Economic, Environmental and System Assessment

**Owner:** He Zimo (何子墨)
**Consumes:** SP1 forecast, SP2 schedule, SP3 solar
**Produces:** `data/processed/sp5-assessment-v1.json` → SP4

## Tasks (from the official brief)
- Assess charging cost savings achieved by the proposed platform.
- Evaluate carbon emission reduction and environmental benefits.
- Conduct overall system performance evaluation and benchmarking.
- Analyse commercial feasibility and user benefits.

## Immediate work (Phase 1)
Benchmark commercial EV charging costs **for the sites actually in use** (Boulder, CO primary;
Palo Alto, CA validation — contract amendment **A1**; the kickoff China lock is retired) and
establish a baseline carbon intensity (**gCO₂/kWh**) for the grid serving those sites. Prefer a
published official regional emission factor over a self-computed one, since it needs a citable
reference in the dissertation. **Source not yet chosen:** the candidate listed in `data/README.md`
is the NESO Carbon Intensity API, which publishes **GB** factors and therefore does not match these
sites — decide the replacement and record it. Costs keep the `_cny` column names until the team
locks USD.

This baseline is what every later saving is measured against, and SP4's dashboard depends on it
— get it pinned early.

## Output contract
See `docs/integration-contract.md` → *SP5 → SP4 · Economic & environmental assessment*.

## Layout
```
src/
notebooks/
```
