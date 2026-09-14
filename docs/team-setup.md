# Team Setup — how we communicate and track work

Chosen at kickoff. Keep this file updated if anything changes.

---

## 1. GitHub repository

**https://github.com/blkmanba1/ev-charging-platform** — **public.**

There is nothing to be invited to. Just send teammates the link; they can clone it directly.

> **This repository is public.** So never commit datasets, credentials, API keys, or the Teams
> meeting link and passcode. Those live in the calendar invitation and the team's own records.

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

## 3. Communication channels

We use **two** channels, because no single one reaches everybody:

| Channel | Who | Purpose |
|---|---|---|
| **QQ group** | the four students **only** | Daily coordination, quick questions, deciding the weekly commitments |
| **Teams meeting** | students + supervisor | The scheduled individual check-ins and biweekly integration meetings |
| **Email** | students + supervisor | Anything that needs a record: deliverables, scope changes, deadline questions |

**Why the split:** Dr Ghias is based in the UK and cannot use QQ. So QQ is our internal
workspace, and it is our responsibility to relay anything he needs to know — either in the
Teams meeting or by email. **Never let a decision live only in the QQ group if it affects
the supervisor or the deliverable.**

### QQ group conventions

- **One group, named clearly:** `FYP — AI-Enabled Smart EV Charging & Energy Management Platform`
- Keep it to the four of you. Do not add the supervisor.
- **Decisions get written to the repo, not left in chat.** If a decision is made in QQ and it
  affects an interface, it goes into `docs/integration-contract.md` in the same week, or it
  didn't happen.
- Pin the essentials: the repository link, the Teams join link, and the meeting time.
- Use `@全体成员` sparingly — only for deadlines and meeting changes.

### Teams — the channel used with the supervisor

Dr Amer Ghias uses Teams natively, and the meeting invitation is already a Teams meeting, so
the scheduled meetings stay there. Join link, Meeting ID, and passcode are in the calendar
invitation. **Accept the invitation** so attendance is tracked.

Meeting links and minutes are mirrored into QQ after each meeting.

### Reaching the supervisor between meetings

- Email for anything needing a decision or a paper trail.
- Do not expect a fast reply in QQ hours — he is in a different timezone (UK, UTC+0/+1).
  China time is **7–8 hours ahead**, so his working day starts around 16:00–17:00 China time.

### Weekly report template (post in the QQ group, then relay a summary to the supervisor)

```
**Week of YYYY-MM-DD — <name> (SP<N>)**
- Done: …
- Next: …
- Blocked by: … (or "nothing")
- PRs: #12, #15
```

### Meeting rhythm (proposed by the supervisor)

| Meeting | Frequency | Who | Platform |
|---|---|---|---|
| Individual check-in | Weekly | Supervisor + individual student | Teams — *schedule still to be confirmed* |
| Team integration meeting | Biweekly, Sat 14:00 China time | Supervisor + whole team | Teams (recurring series) |

The team integration meeting is a **recurring biweekly Teams series** — join link, Meeting ID,
and passcode are in the calendar invitation. Accept the invitation so attendance is tracked.

**Confirmed at kickoff:** the recurring Saturday 14:00 China time slot is the *team integration
meeting*; the weekly individual check-ins are arranged separately.

After every meeting, post a short summary in the QQ group so anyone who missed it stays current,
and save the full minutes to `docs/meeting-notes/YYYY-MM-DD.md`.

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
