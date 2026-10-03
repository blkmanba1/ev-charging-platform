"""Repository paths and configuration access for SP1.

Nothing here hard-codes an absolute path: the repository root is found by
walking up from this file until ``config.yaml`` and ``subprojects/`` are both
present (see ``CONTRIBUTING.md`` — no hard-coded paths).

Public API
----------
- :func:`repo_root` — absolute :class:`~pathlib.Path` of the repository.
- :func:`load_config` — parsed ``config.yaml`` (plus ``config.local.yaml`` if present).
- :func:`sp1_settings` — the SP1 section with defaults filled in.
- :func:`resolve` — repository-relative path -> absolute path.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

DEFAULT_LOCAL_TZ = "Asia/Shanghai"


def repo_root(start: str | Path | None = None) -> Path:
    """Return the repository root.

    Parameters
    ----------
    start : str | Path | None
        Where to start looking; defaults to this file.

    Raises
    ------
    FileNotFoundError
        If no ancestor directory contains both ``config.yaml`` and ``subprojects/``.
    """
    current = Path(start or __file__).resolve()
    for candidate in [current, *current.parents]:
        if (candidate / "config.yaml").is_file() and (candidate / "subprojects").is_dir():
            return candidate
    raise FileNotFoundError(
        f"could not locate the repository root above {current}: no ancestor has both "
        "config.yaml and subprojects/"
    )


def load_config(root: str | Path | None = None) -> dict:
    """Load ``config.yaml``, merging ``config.local.yaml`` on top when it exists.

    Returns
    -------
    dict
        Parsed YAML. ``config.local.yaml`` is git-ignored and meant for
        machine-specific paths, so locally it wins.
    """
    root = Path(root) if root is not None else repo_root()
    with (root / "config.yaml").open(encoding="utf-8") as handle:
        config = yaml.safe_load(handle) or {}
    local = root / "config.local.yaml"
    if local.is_file():
        with local.open(encoding="utf-8") as handle:
            overlay = yaml.safe_load(handle) or {}
        config = _deep_merge(config, overlay)
    return config


def _deep_merge(base: dict, overlay: dict) -> dict:
    merged = dict(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def resolve(path: str | Path, root: str | Path | None = None) -> Path:
    """Resolve a repository-relative path against the repository root."""
    path = Path(path)
    if path.is_absolute():
        return path
    return (Path(root) if root is not None else repo_root()) / path


@dataclass(frozen=True)
class Sp1Settings:
    """SP1 settings after defaults are applied.

    Attributes
    ----------
    raw_dir, interim_dir, processed_dir : pathlib.Path
        Absolute data directories.
    local_tz : str
        Timezone used for calendar features and for display; storage is UTC.
    forecast_horizon_hours : int
        Day-ahead horizon, in 1-hour intervals.
    forecast_days : int
        Length of the evaluation/output window written to the contract files.
    backtest_min_train_days : int
        Minimum training history before the first forecast origin.
    train_window_days : int
        Training history cap per origin; 0 means "use everything".
    model : str
        Model name to use for the contract output; empty means "pick the best".
    max_charging_power_kw : float
        Per-vehicle power used to build the uncontrolled baseline profile.
    plug_in_hour_local : int
        Local clock hour at which the uncontrolled baseline assumes every EV plugs in.
    random_seed : int
        Seed for the synthetic fallback generator.
    """

    raw_dir: Path
    interim_dir: Path
    processed_dir: Path
    local_tz: str = DEFAULT_LOCAL_TZ
    forecast_horizon_hours: int = 24
    forecast_days: int = 30
    backtest_min_train_days: int = 14
    train_window_days: int = 365
    model: str = ""
    max_charging_power_kw: float = 7.0
    plug_in_hour_local: int = 18
    random_seed: int = 42


def sp1_settings(config: dict | None = None, root: str | Path | None = None) -> Sp1Settings:
    """Build :class:`Sp1Settings` from ``config.yaml``, filling in defaults."""
    root = Path(root) if root is not None else repo_root()
    config = config if config is not None else load_config(root)
    data = config.get("data", {})
    sp1 = config.get("sp1", {})
    return Sp1Settings(
        raw_dir=resolve(data.get("raw_dir", "data/raw"), root),
        interim_dir=resolve(data.get("interim_dir", "data/interim"), root),
        processed_dir=resolve(data.get("processed_dir", "data/processed"), root),
        local_tz=config.get("project", {}).get("timezone_display", DEFAULT_LOCAL_TZ),
        forecast_horizon_hours=int(sp1.get("forecast_horizon_hours", 24)),
        forecast_days=int(sp1.get("forecast_days", 30)),
        backtest_min_train_days=int(sp1.get("backtest_min_train_days", 14)),
        train_window_days=int(sp1.get("train_window_days", 365)),
        model=str(sp1.get("model", "") or ""),
        max_charging_power_kw=float(sp1.get("max_charging_power_kw", 7.0)),
        plug_in_hour_local=int(sp1.get("plug_in_hour_local", 18)),
        random_seed=int(sp1.get("random_seed", 42)),
    )
