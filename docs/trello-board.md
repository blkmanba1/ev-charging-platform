# Trello board — card list

Create the board **FYP — AI-Enabled Smart EV Charging & Energy Management Platform**, then
create these lists and cards. Work top to bottom. The list order is the board's left-to-right
column order.

> **Faster:** paste each list's cards into Trello one per line, then use Trello's
> "card templates" or Trello's CSV import (Butler / Power-Up) if you prefer. For a board this
> size, hand-creating ~20 cards takes about ten minutes.

---

## List 1 — 📥 Backlog

```
[shared] Confirm Sub-Project 3 owner with supervisor
[shared] Agree integration contract v0.1 at kickoff (resolution, currency, aggregate vs per-EV)
[shared] Accept the recurring Teams calendar invitation (all 4 members)
[shared] Write up kickoff meeting notes into docs/meeting-notes/
[SP1] Literature review: EV charging demand forecasting methods
[SP1] Decide dataset: which Chinese EV charging dataset(s) to use
[SP2] Literature review: charging strategies and electricity tariff structures
[SP2] Decide optimisation approach: LP / GA / rule-based heuristics
[SP3] Literature review: solar PV generation modelling and renewable-aware charging
[SP3] Choose solar dataset: Chinese solar resource data (see data/README.md)
[SP4] Literature review: charging monitoring dashboards
[SP4] Decide stack: Dash/Streamlit vs React/Node.js
[SP5] Literature review: EV charging cost and CO2 assessment methods
[SP5] Establish baseline carbon intensity metric (gCO2/kWh) for the Chinese grid
[shared] Draft the technical report skeleton
[shared] Set up weekly individual check-in with supervisor
```

## List 2 — 🎯 This Week

```
[shared] Kickoff meeting attendance + notes
[shared] Create the QQ group and pin repo / Teams links
[shared] Everyone: read docs/integration-contract.md and raise objections
[SP1] Identify candidate **Chinese** EV charging datasets and record them in data/README.md
[SP2] Research Chinese ToU and peak-valley electricity tariff structures
[SP4] Set up local development environment and confirm requirements.txt installs
[SP5] Benchmark current commercial EV charging costs in China
```

## List 3 — 🔨 In Progress

```
[shared] Repo scaffold: README, .gitignore, integration contract, contributing guide
```

## List 4 — 👀 Review

*(empty — nothing in review yet)*

## List 5 — ✅ Done

```
[shared] GitHub repository created (private) and collaborators invited
[shared] Project documentation organised (brief + email + calendar invite)
```

---

## Labels to create

| Label | Colour suggestion |
|---|---|
| `SP1` | blue |
| `SP2` | green |
| `SP3` | yellow |
| `SP4` | orange |
| `SP5` | purple |
| `shared` | sky |
| `docs` | grey |
| `blocked` | red |
| `milestone` | black |

## Card description template

```
Definition of done:
- output matches docs/integration-contract.md
- runs from a clean checkout
- PR merged to main

Owner:
Depends on:
Notes:
```

## Automation (Butler, optional but recommended)

- When a card is moved to **✅ Done** → mark the linked PR as merged (manual link is fine).
- Every **Monday 09:00** → move nothing automatically, but post a reminder comment on all
  cards in **🎯 This Week**: "Is this still this week's commitment?"
- When a card is moved to **👀 Review** → require one reviewer from the relevant SP.
