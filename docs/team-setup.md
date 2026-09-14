# Team Setup — how we communicate and track work

Chosen at kickoff. Keep this file updated if anything changes.

---

## 1. GitHub repository

**https://github.com/blkmanba1/ev-charging-platform** (private)

Everyone needs collaborator access — send your GitHub username to Xu Yuxuan (repo owner).

### First-time setup for each member

```bash
git clone https://github.com/blkmanba1/ev-charging-platform.git
cd ev-charging-platform
git config user.name  "Your Name"
git config user.email "your-email@std.uestc.edu.cn"
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

Then read, in this order:
1. `README.md` — what the project is and who does what
2. `docs/integration-contract.md` — **the interfaces between us; read before writing output**
3. `CONTRIBUTING.md` — branching, commits, what "done" means

---

## 2. Trello board

**Board name:** FYP — AI-Enabled Smart EV Charging & Energy Management Platform

See `docs/trello-board.md` for the full card list to create (or import).

### Lists (columns)

| List | Meaning |
|---|---|
| 📥 Backlog | Everything we know we need, not yet scheduled |
| 🎯 This Week | Committed for the current week — keep it small |
| 🔨 In Progress | Actively being worked on — **max 2 cards per person** |
| 👀 Review | PR open, awaiting a teammate's review |
| ✅ Done | Merged to `main`. Move the card the moment it lands. |

### Conventions

- **One card = one PR.** If a card needs a second PR, it was two cards.
- Prefix every card title with the owner: `[SP1] Clean ACN-Data session records`.
- Card description must state the **definition of done** — usually "output matches
  `docs/integration-contract.md`".
- Labels: `SP1` `SP2` `SP3` `SP4` `SP5` `shared` `docs` `blocked` `milestone`.
- Any `blocked` card gets a comment naming **who** unblocks it and **what** they must deliver.

---

## 3. Communication channel — Microsoft Teams

**Team name:** FYP — AI-Enabled Smart EV Charging & Energy Management Platform
**Channel:** `General` (project-wide) + a private channel per sub-project if needed.

Dr Amer Ghias uses Teams natively and the meeting invitation is already a Teams meeting, so
this is the lowest-friction option for reaching him.

### Channels to create

| Channel | Purpose |
|---|---|
| `General` | Announcements, meeting links, weekly summary |
| `Integration` | Interface questions, contract changes, Phase 3 coordination |
| `Data` | Dataset sourcing, cleaning issues, where files live |
| `Weekly Check-in` | Individual weekly updates, one post per person per week |

### Weekly post template (paste into `Weekly Check-in`)

```
**Week of YYYY-MM-DD**
- Done: …
- Next: …
- Blocked by: … (or "nothing")
- PRs: #12, #15
```

### Meeting rhythm (proposed by the supervisor)

| Meeting | Frequency | Who | Purpose |
|---|---|---|---|
| Individual check-in | Weekly | Supervisor + individual student | Progress, blockers, scope questions |
| Team integration meeting | Biweekly, Sat 14:00 China time | Supervisor + whole team | Cross-subsystem alignment, milestones |

The Teams meeting is a **recurring biweekly series** — join link, Meeting ID, and passcode are
in the calendar invitation. Accept the invitation so attendance is tracked.

---

## 4. Division of responsibility

| Sub-project | Owner | Subsystem |
|---|---|---|
| SP1 | Xu Yuxuan | EV Charging Data Analysis & Demand Forecasting |
| SP2 | Xie Letian | Smart Charging Scheduling |
| SP3 | *unallocated* | Renewable-Aware Charging Management |
| SP4 | Li Chunren | Charging Monitoring & Visualisation Platform |
| SP5 | He Zimo | Economic, Environmental & System Assessment |

**SP3 is not yet assigned.** Until it is, SP2 must not block on solar data — treat missing
solar as zero so the interface stays clean.
