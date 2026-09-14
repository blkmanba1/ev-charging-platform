"""End-to-end pipeline: the files SP2, SP4 and SP5 will actually read."""

from __future__ import annotations

import json

import pytest
from sp1.config import Sp1Settings
from sp1.contract import (
    FORECAST_COLUMNS,
    ContractError,
    read_meta,
    read_series_csv,
    validate_series,
)
from sp1.hourly import to_local
from sp1.pipeline import (
    BACKTEST_FILENAME,
    BASELINE_FILENAME,
    FORECAST_FILENAME,
    HOURLY_DEMAND_FILENAME,
    METRICS_FILENAME,
    PATTERNS_FILENAME,
    SESSIONS_FILENAME,
    run_pipeline,
)

FAST_MODELS = ["hour_of_week_profile", "ridge"]


def _settings(tmp_path, **overrides) -> Sp1Settings:
    values = {
        "raw_dir": tmp_path / "raw",
        "interim_dir": tmp_path / "interim",
        "processed_dir": tmp_path / "processed",
        "local_tz": "Asia/Shanghai",
        "forecast_horizon_hours": 24,
        "forecast_days": 3,
        "backtest_min_train_days": 3,
        "model": "",
        "max_charging_power_kw": 7.0,
        "plug_in_hour_local": 18,
        "random_seed": 7,
    }
    values.update(overrides)
    return Sp1Settings(**values)


def _run(tmp_path, sessions, **overrides):
    settings = _settings(tmp_path, **overrides)
    return run_pipeline(
        settings,
        sessions=sessions,
        source_label="pytest synthetic fixture",
        synthetic=True,
        model_names=FAST_MODELS,
    )


def test_pipeline_writes_contract_compliant_outputs(tmp_path, sessions):
    _run(tmp_path, sessions)

    forecast_path = tmp_path / "processed" / FORECAST_FILENAME
    baseline_path = tmp_path / "processed" / BASELINE_FILENAME
    assert forecast_path.is_file() and baseline_path.is_file()

    forecast = read_series_csv(forecast_path)
    assert list(forecast.columns) == list(FORECAST_COLUMNS)
    assert not validate_series(forecast)
    assert len(forecast) == 3 * 24  # three day-ahead origins, 24 intervals each
    assert (forecast["predicted_demand_kwh"] >= 0).all()
    assert (forecast["lower_bound_kwh"] <= forecast["predicted_demand_kwh"]).all()
    assert (forecast["upper_bound_kwh"] >= forecast["predicted_demand_kwh"]).all()

    baseline = read_series_csv(baseline_path)
    assert not validate_series(baseline)
    assert baseline["timestamp"].tolist() == forecast["timestamp"].tolist()
    assert baseline["lower_bound_kwh"].isna().all()  # not modelled for the baseline
    assert (baseline["predicted_demand_kwh"] >= 0).all()

    meta = read_meta(forecast_path)
    assert meta["generated_by"] == "SP1"
    assert meta["resolution"] == "1h"
    assert meta["synthetic"] is True
    assert meta["model"] in FAST_MODELS
    assert meta["window"]["days"] == 3
    assert "licence-free" not in meta["source"]
    baseline_meta = read_meta(baseline_path)
    assert "uncontrolled" in baseline_meta["definition"]

    for name in (
        SESSIONS_FILENAME,
        HOURLY_DEMAND_FILENAME,
        BACKTEST_FILENAME,
        METRICS_FILENAME,
        PATTERNS_FILENAME,
    ):
        assert (tmp_path / "interim" / name).is_file(), name

    metrics = json.loads((tmp_path / "interim" / METRICS_FILENAME).read_text(encoding="utf-8"))
    assert metrics["chosen_model"] in FAST_MODELS
    assert set(metrics["per_model"]) == set(FAST_MODELS)
    assert all(
        entry["n_intervals"] > 0 for entry in metrics["per_model"].values()
    )


def test_pipeline_is_deterministic(tmp_path, sessions):
    _run(tmp_path / "a", sessions)
    _run(tmp_path / "b", sessions)
    first = read_series_csv(tmp_path / "a" / "processed" / FORECAST_FILENAME)
    second = read_series_csv(tmp_path / "b" / "processed" / FORECAST_FILENAME)
    assert first["predicted_demand_kwh"].tolist() == second["predicted_demand_kwh"].tolist()
    assert first["lower_bound_kwh"].tolist() == second["lower_bound_kwh"].tolist()


def test_baseline_shifts_energy_into_the_local_evening(tmp_path, sessions):
    _run(tmp_path, sessions)
    baseline = read_series_csv(tmp_path / "processed" / BASELINE_FILENAME)
    hours = to_local(baseline["timestamp"]).hour
    evening = baseline.loc[hours.isin([18, 19, 20, 21]), "predicted_demand_kwh"].sum()
    assert evening / baseline["predicted_demand_kwh"].sum() > 0.5


def test_forecast_differs_from_the_uncontrolled_baseline(tmp_path, sessions):
    _run(tmp_path, sessions)
    forecast = read_series_csv(tmp_path / "processed" / FORECAST_FILENAME)
    baseline = read_series_csv(tmp_path / "processed" / BASELINE_FILENAME)
    assert not forecast["predicted_demand_kwh"].equals(baseline["predicted_demand_kwh"])


def test_pipeline_rejects_ambiguous_or_missing_input(tmp_path, sessions):
    settings = _settings(tmp_path)
    with pytest.raises(ContractError, match="exactly one of"):
        run_pipeline(settings, source_label="x", synthetic=True)
    with pytest.raises(ContractError, match="exactly one of"):
        run_pipeline(
            settings,
            sessions=sessions,
            hourly_load=sessions,
            source_label="x",
            synthetic=True,
        )


def test_pipeline_rejects_a_series_that_is_too_short(tmp_path, sessions):
    settings = _settings(tmp_path, backtest_min_train_days=60, forecast_days=3)
    with pytest.raises(ContractError, match="need at least"):
        run_pipeline(
            settings,
            sessions=sessions,
            source_label="too short",
            synthetic=True,
            model_names=FAST_MODELS,
        )


def test_pipeline_requires_a_source_label(tmp_path, sessions):
    settings = _settings(tmp_path)
    with pytest.raises(ContractError, match="source_label is required"):
        run_pipeline(settings, sessions=sessions, synthetic=True, model_names=FAST_MODELS)


def test_pipeline_accepts_an_hourly_load_series(tmp_path, sessions):
    from sp1.hourly import build_hourly_demand, complete_grid

    demand = complete_grid(build_hourly_demand(sessions))
    settings = _settings(tmp_path)
    result = run_pipeline(
        settings,
        hourly_load=demand,
        source_label="pytest hourly load fixture",
        synthetic=True,
        model_names=FAST_MODELS,
    )
    assert result.outputs["forecast"].is_file()
    meta = read_meta(result.outputs["baseline"])
    assert "observed load series" in meta["definition"]
    # No session table exists for a load series, so no sessions file is written.
    assert not (tmp_path / "interim" / SESSIONS_FILENAME).is_file()
