# AI-Enabled Smart EV Charging and Energy Management Platform

> **Final Year Project** — University of Glasgow (Glasgow College UESTC)
> **Supervisor:** Dr Amer Ghias
> **Duration:** 6–7 months · **Meeting:** biweekly team integration (Sat 14:00 China time) on Teams
> **Region:** China · **Time resolution:** 1 hour · **Currency:** CNY (¥)

An integrated software prototype that uses data analytics, machine learning, and optimisation
to make EV charging **smarter, cheaper, and greener** — forecasting charging stress, aligning it
with solar generation curves, and shifting charging blocks into grid valleys.

---

## The problem we are solving

If 50 EVs plug into a standard distribution network uncoordinated at 18:00 — exactly when
household demand peaks — utilities face outages or must fall back on expensive, high-carbon
fossil-fuel generation. Meanwhile renewables such as solar are volatile: they peak when cars
are **not** home.

**Our goal:** forecast charging demand accurately, align it with renewable generation, and
shift charging into low-load / low-tariff windows.

---

## Team & subsystems

Each member owns an independent subsystem, but **every output is a teammate's input** — this
is a collaborative systems-engineering project, not four separate essays.

| Sub-project | Owner | Responsibility | Code home |
|---|---|---|---|
| **SP1** | Xu Yuxuan (徐宇轩) | EV Charging Data Analysis & Demand Forecasting | `subprojects/sp1-data-forecasting/` |
| **SP2** | Xie Letian (谢乐天) | Smart Charging Scheduling | `subprojects/sp2-smart-scheduling/` |
| **SP3** | *not yet allocated* | Renewable-Aware Charging Management | `subprojects/sp3-renewable-aware/` |
| **SP4** | Li Chunren (李春仁) | Charging Monitoring & Visualisation Platform | `subprojects/sp4-monitoring-dashboard/` |
| **SP5** | He Zimo (何子墨) | Economic, Environmental & System Assessment | `subprojects/sp5-system-assessment/` |

### Data flow

```
   SP1  demand forecast  ──►  SP2  charging schedule  ──►  SP5  savings & CO2 assessment
     ▲                                                             │
     │                                                             ▼
   SP3  solar generation forecast                        SP4  dashboard / UI  ◄── all three
```

- **SP1 → SP2**: predicted demand profile (when + how much power EVs need)
- **SP2 → SP5**: optimised charging schedule (what actually gets charged, and when)
- **SP3 → SP2**: solar generation forecast, so scheduling can maximise renewable use
- **SP1 + SP2 + SP3 + SP5 → SP4**: everything funnels into the user-facing dashboard

The exact file formats are pinned in **[`docs/integration-contract.md`](docs/integration-contract.md)** —
read it before you write a single output file. Agreeing the interface early is what prevents the
last-minute integration bottleneck the supervisor warned about.

---

## Roadmap & milestones

| Phase | Window | Focus | Milestone |
|---|---|---|---|
| **1** | Months 1–2 | Research, data sourcing, environment setup | **M1** Literature review done, tools aligned, clean datasets secured |
| **2** | Months 3–4 | Core algorithms & subsystem development | **M2** Mid-project report; each subsystem runs on mock/static data |
| **3** | Month 5 | Integration, testing & refinement | **M3** Fully working integrated prototype |
| **4** | Months 6–7 | Final evaluation & dissertation writing | **M4** Thesis submitted, viva/presentation passed |

Phase 3 is the critical one: we run **"Uncontrolled vs Intelligent"** scenarios (e.g. 50 EVs
plug in at 18:00) and show the platform shifting load to midnight — cutting cost and grid peaks.

---

## Repository conventions

- **Branching:** `main` is always working. Work on `sp<N>/<short-description>`
  (e.g. `sp1/demand-forecast-lstm`), open a PR, get one teammate review.
- **Commits:** weekly at minimum. Small, frequent, and meaningful.
- **Modularity is key.** Every function that crosses a subsystem boundary needs a docstring
  stating its inputs and outputs, so teammates can read your code without asking you.
- **Never commit data or secrets.** Raw data goes in `data/raw/` (git-ignored); keep a
  `data/README.md` describing where to download it.

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the full workflow.

---

## Quick start

```bash
git clone https://github.com/blkmanba1/ev-charging-platform.git
cd ev-charging-platform
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

Recommended stacks (from the supervisor):
- **SP1 / SP2 / SP3 / SP5:** Python — pandas, scikit-learn, XGBoost, statsmodels, PuLP / DEAP
  (or MATLAB for optimisation)
- **SP4:** Python (Dash / Streamlit) **or** React / Node.js, with SQLite / PostgreSQL

---

## Documentation

| Document | Contents |
|---|---|
| [`docs/project-description.md`](docs/project-description.md) | The official project brief (background, tasks, outcomes, prerequisites) |
| [`docs/integration-contract.md`](docs/integration-contract.md) | **Pinned data formats between subsystems — read this first** |
| [`docs/meeting-notes/`](docs/meeting-notes/) | One file per meeting: `YYYY-MM-DD.md` |
| [`docs/team-setup.md`](docs/team-setup.md) | QQ group, Teams meetings, repository access, and how we communicate |

---

## Prerequisite skills

Python programming · machine learning fundamentals · signal processing and data analysis ·
basic database handling · engineering mathematics and statistics · MATLAB or Python simulation ·
basic optimisation techniques
