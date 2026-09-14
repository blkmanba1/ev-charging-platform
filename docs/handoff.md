# Handoff — current project state

**Purpose:** a fresh session (or a teammate) should be able to pick this project up from this
file alone. Written at the end of the planning/analysis stage.

**Last updated:** 2026-09-14

---

## 1. What is decided (do not re-litigate)

| Decision | Value | Decided by |
|---|---|---|
| Repository | **public** — https://github.com/blkmanba1/ev-charging-platform | team |
| Task board | Trello, card list in `docs/trello-board.md` | team |
| Team comms | **QQ group, students only** | team |
| Comms with supervisor | Teams meetings + email | team |
| Datasets | **Chinese data — approved by Dr Ghias** | supervisor |
| Time resolution | **1 hour** | team |
| Currency | **CNY (¥)** | team |
| Storage timezone | **UTC** (display handled by SP4) | team |
| Scenario hand-off | **CSV** | team |

Full detail: `docs/integration-contract.md`.

## 2. Meeting logistics

- Next meeting: **Saturday 2026-09-26, 14:00 China time (UTC+8) = 07:00 UK**
- Recurring: **every two weeks on Saturday** through 2027-06-13
- Platform: Microsoft Teams (link and passcode are in the calendar invitation — deliberately
  **not** stored in this public repo)
- The supervisor's kickoff email said "this Friday" but signed off "See you Saturday"; the
  `.ics` attachment says Saturday 26 September. **Confirm with him.**
- All four members' RSVP was still `NEEDS-ACTION` — accept the invitation.

## 3. Team & ownership

| Sub-project | Owner | Directory | Phase-1 status (2026-09-14) |
|---|---|---|---|
| SP1 — Data Analysis & Demand Forecasting | Xu Yuxuan | `subprojects/sp1-data-forecasting/` | **Phase 1 complete** — official datasets secured (City of Boulder primary, City of Palo Alto validation), 76 tests, contract outputs produced |
| SP2 — Smart Charging Scheduling | Xie Letian | `subprojects/sp2-smart-scheduling/` | not started |
| SP3 — Renewable-Aware Charging Management | **unallocated** | `subprojects/sp3-renewable-aware/` | not started |
| SP4 — Monitoring & Visualisation Platform | Li Chunren | `subprojects/sp4-monitoring-dashboard/` | not started |
| SP5 — Economic, Environmental & System Assessment | He Zimo | `subprojects/sp5-system-assessment/` | not started |

## 4. Open items

1. **SP3 owner** — the official brief says five students; only four are assigned. Asked of the
   supervisor; awaiting an answer.
2. **Aggregate vs per-EV forecast** — SP1 currently forecasts **aggregate** demand. The dataset
   actually answers this differently now: Boulder has no vehicle identifier, but **Palo Alto does**
   (`User ID`, 97% populated), so a per-EV variant is possible without new data — it is a scope
   decision, not a data limitation. Still worth confirming with the supervisor.
3. **Carbon intensity source** for SP5's baseline — the Chinese route is closed with the data
   decision. Options are recorded in `data/README.md` (e.g. keyless NESO Carbon Intensity API);
   needs a decision and a citable reference.
4. **Who owns the shared tariff table** (recommendation: SP2) — and it is now a **blocker**: the
   Boulder/Palo Alto data contain no tariff column, so SP2 must source a US tariff schedule before
   it can fill `tariff_cny_per_kwh`. See integration contract amendment **A1**.
5. **Trello board** — created? Card list is ready in `docs/trello-board.md`.
6. **Reply email** — drafted but not sent. See the workspace's `回复导师邮件草稿.md`.
7. **SP1 dataset (closed 2026-09-14).** Chosen: **City of Boulder** (official municipal open data,
   **CC0 1.0**, 148,136 sessions, 5.9 years, metered kWh) as primary, **City of Palo Alto**
   (official, PDDL, 259,415 sessions, 9.4 years, per-user IDs) as validation — both
   supervisor-recommended, both fetchable with no registration, both scripted in
   `scripts/fetch_datasets.py`. **Not used:** the Chinese third-party figshare dataset and China
   Charging Alliance member material (monthly aggregates only, verified with a member account).
   Full source evaluation: `data/README.md`.

## 5. Where to start implementing

Read in this order:

1. `README.md` — scope, team, data flow
2. `docs/integration-contract.md` — **the interfaces; read before writing any output file**
3. `CONTRIBUTING.md` — branching, commits, definition of done
4. Your own `subprojects/spN-*/README.md`

Then Phase 1 (Months 1–2), per the supervisor's roadmap:

| SP | Phase 1 task | Status |
|---|---|---|
| SP1 | Identify and clean Chinese public EV charging datasets | **done** — see `subprojects/sp1-data-forecasting/README.md` |
| SP2 | Research Chinese peak-valley time-of-use tariff structures | to do |
| SP3 | Solar resource data + PV modelling (pending owner) | to do |
| SP4 | Set up the development environment (Dash/Streamlit or React/Node + SQLite/PostgreSQL) | to do |
| SP5 | Benchmark Chinese commercial charging costs; establish gCO₂/kWh baseline | to do |

SP1's outputs are already contract-compliant, so **SP2 and SP4 can develop against real files
today** rather than mock data:

```bash
python subprojects/sp1-data-forecasting/scripts/fetch_datasets.py --dataset cn-charging-orders
python subprojects/sp1-data-forecasting/scripts/run_sp1.py --dataset cn-charging-orders
# -> data/processed/sp1-demand-forecast-v1.csv      (+ .meta.json)
# -> data/processed/sp1-baseline-demand-v1.csv      (+ .meta.json)  "everyone plugs in at 18:00"
```

The uncontrolled baseline shows an **11.6× peak increase** over the forecast peak on the same
window — that is the number SP2's scheduler exists to reduce.

## 6. Things easily forgotten

- **Datasets are git-ignored** (`data/raw`, `data/interim`, `data/processed`). Record every
  dataset in `data/README.md` in the same PR.
- **The repo is public.** No datasets, credentials, or meeting links in commits.
- **A decision made in QQ does not exist until it is in the repository.**
- `data/README.md` contains the researched candidate list of **Chinese** data sources
  (charging sessions, peak-valley tariffs, solar, grid carbon intensity). Start there rather
  than searching from scratch.
- **Known honest difficulty:** China publishes much less open session-level EV charging data
  than the US or EU. The best public options are research datasets on Science Data Bank
  (scidb.cn). A calibrated synthetic profile built from published Chinese aggregates is the
  documented fallback — it must be labelled as synthetic.
- **China's peak-valley ToU tariff (峰谷分时电价)** is a genuine Chinese policy instrument and
  the natural mechanism for SP2's scheduler. This is a strength of the project, not a workaround.

## 7. Source material (workspace, not in the repo)

| File | Contents |
|---|---|
| `RE_ Missed you at today's meeting - let's reschedule.eml` | Supervisor's kickoff email + the earlier "nobody joined" email |
| `EV_Charging_Project_Description.pdf` | Official brief: 5 sub-projects, outcomes, prerequisites |
| `ATT00003.ics` | Calendar invitation with the recurring Teams meeting |
| `毕设资料整理.md` | Chinese-language summary of all three, with contradictions flagged |
| `回复导师邮件草稿.md` | English reply draft, two open questions |

## 8. Delivery targets (from the official brief)

EV charging dataset repository and analysis framework · ML demand forecasting model · smart
charging scheduling algorithms · renewable-aware charging module · monitoring & visualisation
dashboard · economic/environmental/sustainability assessment reports · integrated software
prototype · final technical report, dissertation, and presentation.

Milestones: **M1** literature review + clean datasets (Months 1–2) · **M2** mid-project report,
subsystems work on mock data (Months 3–4) · **M3** fully working integrated prototype (Month 5) ·
**M4** thesis submitted and viva passed (Months 6–7).
