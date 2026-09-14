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

| Sub-project | Owner | Directory |
|---|---|---|
| SP1 — Data Analysis & Demand Forecasting | Xu Yuxuan | `subprojects/sp1-data-forecasting/` |
| SP2 — Smart Charging Scheduling | Xie Letian | `subprojects/sp2-smart-scheduling/` |
| SP3 — Renewable-Aware Charging Management | **unallocated** | `subprojects/sp3-renewable-aware/` |
| SP4 — Monitoring & Visualisation Platform | Li Chunren | `subprojects/sp4-monitoring-dashboard/` |
| SP5 — Economic, Environmental & System Assessment | He Zimo | `subprojects/sp5-system-assessment/` |

## 4. Open items

1. **SP3 owner** — the official brief says five students; only four are assigned. Asked of the
   supervisor; awaiting an answer.
2. **Aggregate vs per-EV forecast** — the only interface question still blocking SP2's optimiser
   design. Asked of the supervisor in the reply draft.
3. **Chinese grid carbon intensity source** for SP5's baseline — needs a citable reference.
4. **Who owns the shared tariff table** (recommendation: SP2).
5. **Trello board** — created? Card list is ready in `docs/trello-board.md`.
6. **Reply email** — drafted but not sent. See the workspace's `回复导师邮件草稿.md`.

## 5. Where to start implementing

Read in this order:

1. `README.md` — scope, team, data flow
2. `docs/integration-contract.md` — **the interfaces; read before writing any output file**
3. `CONTRIBUTING.md` — branching, commits, definition of done
4. Your own `subprojects/spN-*/README.md`

Then Phase 1 (Months 1–2), per the supervisor's roadmap:

| SP | Phase 1 task |
|---|---|
| SP1 | Identify and clean Chinese public EV charging datasets |
| SP2 | Research Chinese peak-valley time-of-use tariff structures |
| SP3 | Solar resource data + PV modelling (pending owner) |
| SP4 | Set up the development environment (Dash/Streamlit or React/Node + SQLite/PostgreSQL) |
| SP5 | Benchmark Chinese commercial charging costs; establish gCO₂/kWh baseline |

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
