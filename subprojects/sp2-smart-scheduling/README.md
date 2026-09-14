# SP2 — Smart Charging Scheduling

**Owner:** Xie Letian (谢乐天)
**Consumes:** SP1 demand forecast (`sp1-demand-forecast-v1.csv`), SP3 solar forecast
**Produces:** `data/processed/sp2-charging-schedule-v1.csv` → SP5, SP4

## Tasks (from the official brief)
- Investigate existing charging strategies and electricity tariff structures.
- Develop charging scheduling algorithms that minimise charging costs and peak demand.
- Compare uncontrolled and intelligent charging approaches.
- Evaluate scheduling performance under different operating scenarios.

## Candidate approaches
Linear Programming · Genetic Algorithms · Rule-Based Heuristics (Python / MATLAB)

## Headline scenario
50 EVs plugging in at 18:00 — show the platform shifting load to midnight.

## Note on SP3
SP3 (solar) is not yet allocated. **Do not block on it** — treat missing solar as zero and
keep the interface clean so it can be wired in later without refactoring.

## Output contract
See `docs/integration-contract.md` → *SP2 → SP5 and SP2 → SP4 · Charging schedule*.

## Layout
```
src/
notebooks/
```
