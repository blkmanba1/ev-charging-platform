#!/usr/bin/env python
"""Render the SP1 figures used by the Phase-1 report.

Reads the per-dataset artefacts the pipeline writes under ``data/interim/`` and
writes PNGs to ``docs/figures/``. Nothing here recomputes anything: if a figure
looks wrong, the pipeline run is wrong, not the plot.

Usage
-----
    python subprojects/sp1-data-forecasting/scripts/make_figures.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from sp1.config import repo_root, sp1_settings

DATASETS = {
    "boulder": {"label": "Boulder, Colorado (primary)", "local_tz": "America/Denver"},
    "palo-alto": {"label": "Palo Alto, California (validation)", "local_tz": "America/Los_Angeles"},
}

COLORS = {"primary": "#1f4e79", "secondary": "#c55a11", "actual": "#404040", "predicted": "#1f4e79"}


def load_json(path: Path) -> dict:
    """Read a JSON artefact, tolerating a UTF-8 BOM (PowerShell redirection adds one)."""
    return json.loads(path.read_text(encoding="utf-8-sig"))


def figure_hourly_profile(interim: Path, out: Path) -> Path | None:
    """Mean demand by local hour of day, one panel per dataset."""
    available = [key for key in DATASETS if (interim / f"patterns-us-{key}.json").is_file()]
    if not available:
        return None
    fig, axes = plt.subplots(1, len(available), figsize=(6.2 * len(available), 3.4), squeeze=False)
    for axis, key in zip(axes[0], available):
        payload = load_json(interim / f"patterns-us-{key}.json")
        frame = pd.DataFrame(payload["by_local_hour"]).sort_values("local_hour")
        axis.bar(frame["local_hour"], frame["mean_kwh"], color=COLORS["primary"], width=0.8)
        axis.set_title(DATASETS[key]["label"], fontsize=10)
        axis.set_xlabel("local hour of day")
        axis.set_ylabel("mean demand (kWh per hour)")
        axis.set_xticks(range(0, 24, 4))
        axis.grid(axis="y", alpha=0.3, linewidth=0.5)
        axis.set_axisbelow(True)
    fig.suptitle("Derived 1-hour charging demand by local hour", fontsize=11)
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out


def figure_demand_weeks(interim: Path, out: Path, weeks: int = 2) -> Path | None:
    """Two weeks of the hourly series, to show the daily cycle and the weekend."""
    available = [key for key in DATASETS if (interim / f"hourly-us-{key}.csv").is_file()]
    if not available:
        return None
    fig, axes = plt.subplots(len(available), 1, figsize=(9.5, 2.6 * len(available)), squeeze=False)
    for axis, key in zip(axes[:, 0], available):
        frame = pd.read_csv(interim / f"hourly-us-{key}.csv", parse_dates=["timestamp"])
        frame = frame.set_index("timestamp").sort_index()
        window = frame.tail(24 * 7 * weeks)
        local = window.index.tz_convert(DATASETS[key]["local_tz"])
        axis.plot(local, window["demand_kwh"], color=COLORS["primary"], linewidth=0.9)
        axis.set_title(f"{DATASETS[key]['label']} — last {weeks} weeks", fontsize=10)
        axis.set_ylabel("kWh per hour")
        axis.grid(alpha=0.3, linewidth=0.5)
        axis.set_axisbelow(True)
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out


def figure_model_ranking(interim: Path, out: Path) -> Path | None:
    """WAPE by model, both datasets side by side."""
    available = [key for key in DATASETS if (interim / f"metrics-us-{key}.json").is_file()]
    if not available:
        return None
    frames = {}
    for key in available:
        ranking = pd.DataFrame(load_json(interim / f"metrics-us-{key}.json")["ranking"])
        frames[key] = ranking.set_index("model")["wape"].sort_values()
    models = sorted({model for frame in frames.values() for model in frame.index})
    fig, axes = plt.subplots(1, len(available), figsize=(5.6 * len(available), 3.4), squeeze=False)
    for axis, key in zip(axes[0], available):
        series = frames[key].reindex(models).dropna()
        colors = [COLORS["secondary"] if m.startswith("naive") else COLORS["primary"] for m in series.index]
        axis.barh(series.index, series.values, color=colors)
        axis.set_title(f"{DATASETS[key]['label']}", fontsize=10)
        axis.set_xlabel("WAPE (lower is better)")
        axis.grid(axis="x", alpha=0.3, linewidth=0.5)
        axis.set_axisbelow(True)
        axis.invert_yaxis()
    fig.suptitle("Out-of-sample accuracy — orange bars are naive baselines", fontsize=11)
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out


def figure_forecast_vs_actual(interim: Path, out: Path, key: str = "boulder", days: int = 7) -> Path | None:
    """Predicted vs actual demand for one week of the evaluation window."""
    path = interim / f"backtest-us-{key}.csv"
    if not path.is_file():
        return None
    frame = pd.read_csv(path, parse_dates=["timestamp"]).sort_values("timestamp")
    frame = frame.set_index("timestamp").tail(24 * days)
    local = frame.index.tz_convert(DATASETS[key]["local_tz"])
    fig, axis = plt.subplots(figsize=(9.5, 3.2))
    axis.plot(local, frame["actual_kwh"], color=COLORS["actual"], linewidth=1.1, label="actual")
    axis.plot(local, frame["predicted_demand_kwh"], color=COLORS["predicted"], linewidth=1.1, label="day-ahead forecast")
    if "lower_bound_kwh" in frame.columns:
        axis.fill_between(
            local, frame["lower_bound_kwh"], frame["upper_bound_kwh"],
            color=COLORS["predicted"], alpha=0.15, label="90% interval",
        )
    axis.set_title(f"{DATASETS[key]['label']} — final week of the evaluation window", fontsize=10)
    axis.set_ylabel("kWh per hour")
    axis.legend(fontsize=8, ncol=3)
    axis.grid(alpha=0.3, linewidth=0.5)
    axis.set_axisbelow(True)
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out


def main() -> int:
    """Write every figure that its inputs allow."""
    settings = sp1_settings(root=repo_root())
    interim = settings.interim_dir
    # Figures sit next to the report so \graphicspath{{figures/}} resolves.
    out_dir = repo_root() / "docs" / "phase1-report" / "figures"

    jobs = [
        ("sp1-hourly-profile.png", figure_hourly_profile, (interim,)),
        ("sp1-demand-weeks.png", figure_demand_weeks, (interim,)),
        ("sp1-model-ranking.png", figure_model_ranking, (interim,)),
        ("sp1-forecast-vs-actual.png", figure_forecast_vs_actual, (interim,)),
    ]
    written = 0
    for name, function, args in jobs:
        result = function(*args, out_dir / name)
        if result is None:
            print(f"  skipped {name} (inputs missing)")
        else:
            print(f"  wrote {result}")
            written += 1
    print(f"{written} figure(s) written to {out_dir}")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:  # pragma: no cover
        pass
    raise SystemExit(main())
