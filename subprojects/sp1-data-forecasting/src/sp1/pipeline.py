"""End-to-end SP1 pipeline: raw dataset -> contract-compliant outputs.

What one run does:

1. load the raw dataset (session records or an hourly load series);
2. aggregate it into a gap-free 1-hour UTC demand series and store it under
   ``data/interim/``;
3. summarise charging patterns by local hour and weekday;
4. run a rolling-origin, out-of-sample backtest of every model in the zoo and
   record the metrics;
5. pick the model with the best WAPE (unless one is pinned in ``config.yaml``);
6. write ``data/processed/sp1-demand-forecast-v1.csv`` with its ``.meta.json``,
   and the matching ``sp1-baseline-demand-v1.csv`` "uncontrolled" profile;
7. re-read both files and validate them against the integration contract.

The pipeline is deterministic given the same input and seed, and never writes
outside ``data/``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from .config import Sp1Settings
from .contract import (
    FORECAST_COLUMNS,
    ContractError,
    assert_valid_series,
    read_meta,
    read_series_csv,
    write_meta,
    write_series_csv,
)
from .features import (
    DEFAULT_LAGS,
    DEFAULT_ROLLING_WINDOWS,
    add_calendar_features,
    add_lag_features,
)
from .hourly import (
    build_hourly_demand,
    build_uncontrolled_profile,
    complete_grid,
    profile,
)
from .ingest import write_interim_table
from .models import (
    BacktestResult,
    add_residual_intervals,
    build_models,
    evaluate_models,
    ranking_table,
)

FORECAST_FILENAME = "sp1-demand-forecast-v1.csv"
BASELINE_FILENAME = "sp1-baseline-demand-v1.csv"
HOURLY_DEMAND_FILENAME = "sp1-hourly-demand-v1.csv"
SESSIONS_FILENAME = "sp1-sessions-canonical-v1.csv"
BACKTEST_FILENAME = "sp1-backtest-v1.csv"
METRICS_FILENAME = "sp1-model-metrics-v1.json"
PATTERNS_FILENAME = "sp1-pattern-summary-v1.json"

FORECAST_UNITS = {
    "predicted_demand_kwh": "kWh",
    "lower_bound_kwh": "kWh",
    "upper_bound_kwh": "kWh",
}
BASELINE_UNITS = {
    "predicted_demand_kwh": "kWh",
    "lower_bound_kwh": "kWh",
    "upper_bound_kwh": "kWh",
}


@dataclass
class PipelineResult:
    """Where a pipeline run put its files, and what it found.

    Attributes
    ----------
    outputs : dict of str to pathlib.Path
        Absolute paths of every file written, keyed by role.
    summary : dict
        JSON-serialisable summary: window, chosen model, headline metrics and
        the best-per-model ranking.
    """

    outputs: dict[str, Path] = field(default_factory=dict)
    summary: dict = field(default_factory=dict)


def build_feature_frame(
    demand: pd.DataFrame,
    local_tz: str,
    target_column: str = "demand_kwh",
    lags: tuple[int, ...] = DEFAULT_LAGS,
    rolling_windows: tuple[int, ...] = DEFAULT_ROLLING_WINDOWS,
) -> pd.DataFrame:
    """Add calendar, lag and rolling features to an hourly demand series.

    Parameters
    ----------
    demand : pandas.DataFrame
        Gap-free hourly frame with ``timestamp`` (UTC) and ``demand_kwh``.
    local_tz : str
        Timezone used for the calendar features.
    target_column : str
        Column predicted by the models.
    lags, rolling_windows : tuple of int
        Window sizes, in hours.

    Returns
    -------
    pandas.DataFrame
        Feature frame; the leading warm-up rows still contain NaN.
    """
    frame = add_calendar_features(demand, local_tz=local_tz)
    return add_lag_features(
        frame, target_column=target_column, lags=lags, rolling_windows=rolling_windows
    )


def run_pipeline(
    settings: Sp1Settings,
    sessions: pd.DataFrame | None = None,
    hourly_load: pd.DataFrame | None = None,
    source_label: str = "",
    synthetic: bool = False,
    provenance: dict | None = None,
    model_names: list[str] | None = None,
    horizon: int | None = None,
    forecast_days: int | None = None,
    write_interim: bool = True,
) -> PipelineResult:
    """Run the whole SP1 pipeline and write the contract outputs.

    Parameters
    ----------
    settings : Sp1Settings
        Resolved configuration (paths, horizon, window length, seed).
    sessions : pandas.DataFrame | None
        Canonical session table. Mutually exclusive with ``hourly_load``.
    hourly_load : pandas.DataFrame | None
        Frame with ``timestamp`` (UTC) and ``demand_kwh``; used when the dataset
        is published as an aggregated load series.
    source_label : str
        Provenance string written into every meta file.
    synthetic : bool
        Recorded in the meta files. **Must** be True for generated data.
    provenance : dict | None
        Extra provenance keys (licence, url, calibration) for the meta files.
    model_names : list of str | None
        Restrict the model zoo; defaults to every available model.
    horizon : int | None
        Forecast horizon in hours; defaults to the configured value.
    forecast_days : int | None
        Length of the output window in days; defaults to the configured value.
    write_interim : bool
        Write the intermediate tables under ``data/interim/``.

    Returns
    -------
    PipelineResult
        Written paths and a JSON-serialisable summary.

    Raises
    ------
    ContractError
        If neither input is given, the series is too short, or a written file
        fails contract validation.
    """
    if (sessions is None) == (hourly_load is None):
        raise ContractError("pass exactly one of sessions= or hourly_load=")

    horizon = horizon or settings.forecast_horizon_hours
    forecast_days = forecast_days or settings.forecast_days
    if forecast_days * 24 <= horizon:
        raise ContractError("forecast_days must cover more than a single horizon")
    if not source_label:
        raise ContractError("source_label is required: every output must state its provenance")

    if sessions is not None:
        demand = complete_grid(build_hourly_demand(sessions))
        baseline_raw = build_uncontrolled_profile(
            sessions,
            plug_in_hour_local=settings.plug_in_hour_local,
            max_power_kw=settings.max_charging_power_kw,
            local_tz=settings.local_tz,
        )
        baseline_definition = (
            f"uncontrolled: every session's energy is moved to a block starting "
            f"{settings.plug_in_hour_local:02d}:00 local, charged at the session's own "
            f"recorded power (fallback {settings.max_charging_power_kw:g} kW); "
            "no queueing or network limits"
        )
    else:
        assert hourly_load is not None
        demand = complete_grid(
            hourly_load[["timestamp", "demand_kwh"]].assign(session_count=0)
        )
        # With an aggregated load series there is nothing to move around: the
        # observed profile *is* the uncoordinated profile.
        baseline_raw = demand[["timestamp", "demand_kwh", "session_count"]].copy()
        baseline_definition = (
            "uncontrolled: the observed load series itself (no session-level data "
            "available to build a plug-in-at-18:00 scenario)"
        )

    if len(demand) < horizon + 24 * settings.backtest_min_train_days:
        raise ContractError(
            f"series has {len(demand)} hourly intervals; need at least "
            f"{horizon + 24 * settings.backtest_min_train_days} for training plus one horizon"
        )

    feature_frame = build_feature_frame(demand, local_tz=settings.local_tz)
    n_origins = max(1, forecast_days)

    models = build_models(random_state=settings.random_seed)
    if model_names:
        unknown = [name for name in model_names if name not in models]
        if unknown:
            raise ContractError(f"unknown model(s) {unknown}; available: {sorted(models)}")
        models = {name: models[name] for name in model_names}

    results = evaluate_models(
        feature_frame,
        models=models,
        horizon=horizon,
        step=24,
        min_train_intervals=24 * settings.backtest_min_train_days,
        n_origins=n_origins,
        origin_hour_local=0,
        local_tz=settings.local_tz,
        train_window_intervals=24 * settings.train_window_days if settings.train_window_days else None,
    )
    ranking = ranking_table(results)
    chosen_name = settings.model or str(ranking.index[0])
    if chosen_name not in results:
        raise ContractError(
            f"configured sp1.model '{chosen_name}' is not among {sorted(results)}"
        )
    chosen: BacktestResult = results[chosen_name]

    window_start = pd.Timestamp(chosen.predictions["timestamp"].min())
    window_end = pd.Timestamp(chosen.predictions["timestamp"].max())

    forecast = add_residual_intervals(
        chosen.predictions, chosen.metrics["residual_std_by_horizon"]
    ).rename(columns={"predicted_kwh": "predicted_demand_kwh"})
    forecast = forecast[
        ["timestamp", "predicted_demand_kwh", "lower_bound_kwh", "upper_bound_kwh"]
    ].sort_values("timestamp", ignore_index=True)
    if forecast["timestamp"].duplicated().any():
        raise ContractError("forecast window contains duplicate intervals")

    baseline_window = baseline_raw[
        (baseline_raw["timestamp"] >= window_start) & (baseline_raw["timestamp"] <= window_end)
    ].copy()
    baseline_grid = complete_grid(
        baseline_window,
        value_columns=("demand_kwh", "session_count"),
        start=window_start,
        end=window_end,
    )

    meta_extra: dict[str, object] = {
        "synthetic": bool(synthetic),
        "model": chosen_name,
        "forecast_horizon_hours": horizon,
        "window": {
            "start": window_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "end": window_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "days": forecast_days,
        },
        "history_days": round(len(demand) / 24.0, 2),
        "interval_method": (
            "empirical prediction interval: prediction +/- 1.645 x residual std "
            "at the same horizon, from the rolling-origin backtest"
        ),
        "evaluation": {
            "wape": round(float(chosen.metrics["wape"]), 4),
            "mae_kwh": round(float(chosen.metrics["mae_kwh"]), 4),
            "rmse_kwh": round(float(chosen.metrics["rmse_kwh"]), 4),
            "r2": round(float(chosen.metrics["r2"]), 4),
            "n_origins": int(chosen.metrics["n_origins"]),
            "scheme": "rolling origin, retrained per origin, targets strictly out of sample",
        },
        "model_ranking_wape": {
            name: round(float(result.metrics["wape"]), 4) for name, result in results.items()
        },
    }
    if provenance:
        meta_extra.update(provenance)

    forecast_path = settings.processed_dir / FORECAST_FILENAME
    baseline_path = settings.processed_dir / BASELINE_FILENAME
    write_series_csv(forecast, forecast_path, columns=FORECAST_COLUMNS)
    write_meta(forecast_path, source=source_label, units=FORECAST_UNITS, extra=meta_extra)

    baseline_out = pd.DataFrame(
        {
            "timestamp": baseline_grid["timestamp"],
            "predicted_demand_kwh": baseline_grid["demand_kwh"].astype("float64"),
            "lower_bound_kwh": pd.Series(float("nan"), index=baseline_grid.index, dtype="float64"),
            "upper_bound_kwh": pd.Series(float("nan"), index=baseline_grid.index, dtype="float64"),
        }
    )
    write_series_csv(baseline_out, baseline_path, columns=FORECAST_COLUMNS)
    write_meta(
        baseline_path,
        source=source_label,
        units=BASELINE_UNITS,
        extra={
            "synthetic": bool(synthetic),
            "definition": baseline_definition,
            "plug_in_hour_local": settings.plug_in_hour_local,
            "max_power_kw": settings.max_charging_power_kw,
            "window": meta_extra["window"],
        },
    )

    outputs: dict[str, Path] = {"forecast": forecast_path, "baseline": baseline_path}
    interim_paths: dict[str, Path] = {}
    if write_interim:
        if sessions is not None:
            interim_paths["sessions"] = write_interim_table(
                sessions, settings.interim_dir / SESSIONS_FILENAME
            )
        interim_paths["hourly_demand"] = write_interim_table(
            demand, settings.interim_dir / HOURLY_DEMAND_FILENAME
        )
        interim_paths["backtest"] = write_interim_table(
            forecast.merge(
                chosen.predictions[["timestamp", "actual_kwh", "horizon", "origin"]],
                on="timestamp",
                how="left",
            ),
            settings.interim_dir / BACKTEST_FILENAME,
        )
        metrics_path = settings.interim_dir / METRICS_FILENAME
        metrics_path.parent.mkdir(parents=True, exist_ok=True)
        metrics_path.write_text(
            json.dumps(
                {
                    "source": source_label,
                    "synthetic": bool(synthetic),
                    "chosen_model": chosen_name,
                    "ranking": json.loads(ranking.reset_index().to_json(orient="records")),
                    "per_model": {
                        name: result.metrics for name, result in results.items()
                    },
                },
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        interim_paths["metrics"] = metrics_path

        patterns = profile(demand, local_tz=settings.local_tz)
        patterns_path = settings.interim_dir / PATTERNS_FILENAME
        payload = {
            "source": source_label,
            "synthetic": bool(synthetic),
            "by_local_hour": json.loads(patterns.reset_index().to_json(orient="records")),
            "total_energy_kwh": round(float(demand["demand_kwh"].sum()), 2),
            "mean_daily_energy_kwh": round(float(demand["demand_kwh"].sum()) / (len(demand) / 24), 2),
        }
        patterns_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        interim_paths["patterns"] = patterns_path
        outputs.update(interim_paths)

    # Read everything back and validate: never trust a file you have not parsed.
    _verify_outputs(forecast_path, baseline_path)

    summary = {
        "source": source_label,
        "synthetic": bool(synthetic),
        "chosen_model": chosen_name,
        "window": meta_extra["window"],
        "history_days": meta_extra["history_days"],
        "ranking_wape": meta_extra["model_ranking_wape"],
        "evaluation": meta_extra["evaluation"],
        "outputs": {key: str(value) for key, value in outputs.items()},
    }
    return PipelineResult(outputs=outputs, summary=summary)


def _verify_outputs(forecast_path: Path, baseline_path: Path) -> None:
    """Re-read and contract-check both processed files."""
    forecast = read_series_csv(forecast_path)
    assert_valid_series(forecast)
    baseline = read_series_csv(baseline_path, required_value_columns=("predicted_demand_kwh",))
    assert_valid_series(baseline)
    for path in (forecast_path, baseline_path):
        meta = read_meta(path)
        if meta["generated_by"] != "SP1":
            raise ContractError(f"{path}: meta generated_by must be 'SP1'")
    if list(forecast.columns) != list(FORECAST_COLUMNS):
        raise ContractError(f"{forecast_path}: unexpected column set {list(forecast.columns)}")
