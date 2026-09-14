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
Benchmark current commercial EV charging costs **in China** and establish baseline carbon
intensity metrics (**gCO₂/kWh**) for the **Chinese grid** — prefer a published official regional
grid emission factor (Ministry of Ecology and Environment / provincial factors) over a
self-computed one, since it needs a citable reference in the dissertation. Costs are in **CNY**.

This baseline is what every later saving is measured against, and SP4's dashboard depends on it
— get it pinned early.

## Output contract
See `docs/integration-contract.md` → *SP5 → SP4 · Economic & environmental assessment*.

## Layout
```
src/
notebooks/
```
