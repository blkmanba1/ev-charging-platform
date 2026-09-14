# Contributing & Workflow

The supervisor's working agreements, made concrete. Keep this short and follow it.

---

## Branching

| Branch | Purpose |
|---|---|
| `main` | Always working. Protected — no direct pushes. |
| `sp<N>/<short-description>` | Your feature work. e.g. `sp1/demand-forecast-lstm` |
| `integration/<short-description>` | Cross-subsystem work in Phase 3 |
| `docs/<short-description>` | Documentation-only changes |

```bash
git checkout main
git pull
git checkout -b sp1/demand-forecast-lstm
# ... work ...
git add .
git commit -m "sp1: add LSTM demand forecasting baseline"
git push -u origin sp1/demand-forecast-lstm
gh pr create --fill
```

**Rule:** one teammate review before merge. If your PR touches a file under someone else's
`subprojects/` folder or `docs/integration-contract.md`, that owner must be the reviewer.

---

## Commit messages

`<sp-id>: <what changed, imperative mood>`

```
sp1: add LSTM demand forecasting baseline
sp2: fix tariff lookup off-by-one at interval boundaries
sp4: wire dashboard to sp5 assessment JSON
docs: pin 15-minute resolution in integration contract
```

Weekly commits are the minimum. Small and frequent beats one giant commit.

---

## Code modularity — non-negotiable

This is a systems-engineering project where **your output is a teammate's input**. So:

- Every function that crosses a subsystem boundary gets a **docstring stating inputs and outputs**,
  including units.
- Prefer explicit column names over positional access when reading shared CSV files.
- No hard-coded absolute paths. Read paths from a `config.yaml` / env var, or accept them as arguments.
- If you change an output format, change `docs/integration-contract.md` **in the same PR**.

---

## Data handling

- **Never commit datasets.** `data/raw/`, `data/processed/`, and `data/interim/` are git-ignored.
- Record where you got each dataset in `data/README.md`: name, source URL, licence, date
  downloaded, size, and what you cleaned.
- Never commit credentials, `.env` files, API keys, or personal data.

---

## Environment

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate        # macOS / Linux
pip install -r requirements.txt
```

If you need a new dependency, add it to `requirements.txt` in your PR and mention it in the
description so teammates know to re-run `pip install`.

---

## What "done" means

A task is done when:

1. It runs from a clean checkout following the README.
2. Its output matches `docs/integration-contract.md`.
3. There is at least a minimal test or a reproducible command that demonstrates it.
4. It is merged to `main` and the Trello card is moved to **Done**.
