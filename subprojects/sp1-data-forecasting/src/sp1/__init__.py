"""SP1 — EV charging data analysis and demand forecasting.

Reusable code for the SP1 subsystem. The public entry points are:

- :mod:`sp1.contract` — read/write/validate the files pinned in
  ``docs/integration-contract.md``.
- :mod:`sp1.hourly` — turn charging sessions into a gap-free 1-hour demand series.
- :mod:`sp1.features` — calendar and lag features for supervised forecasting.
- :mod:`sp1.models` — baselines, scikit-learn models and rolling-origin evaluation.
- :mod:`sp1.pipeline` — end-to-end orchestration used by ``scripts/run_sp1.py``.

Everything in this package speaks **UTC** and **kWh per 1-hour interval** unless a
function's docstring says otherwise. Local time is a presentation concern (SP4).
"""

__all__ = ["__version__"]

__version__ = "0.1.0"
