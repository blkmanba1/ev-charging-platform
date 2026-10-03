"""Models, metrics and the rolling-origin backtest."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from sp1.contract import ContractError
from sp1.features import make_supervised
from sp1.models import (
    ColumnSelector,
    HourOfWeekProfile,
    add_residual_intervals,
    build_models,
    evaluate_models,
    ranking_table,
    rolling_backtest,
    summarize_metrics,
)


def test_summarize_metrics_known_values():
    metrics = summarize_metrics(np.array([0.0, 10.0]), np.array([1.0, 9.0]))
    assert metrics["mae_kwh"] == pytest.approx(1.0)
    assert metrics["rmse_kwh"] == pytest.approx(1.0)
    assert metrics["wape"] == pytest.approx(0.2)
    assert metrics["r2"] == pytest.approx(0.96)
    assert metrics["n_intervals"] == 2


def test_summarize_metrics_rejects_shape_mismatch():
    with pytest.raises(ContractError, match="shape mismatch"):
        summarize_metrics(np.array([1.0, 2.0]), np.array([1.0]))


def test_column_selector_returns_the_named_column(feature_frame):
    from sp1.features import NAIVE_DAILY_COLUMN, make_supervised

    X, y, _ = make_supervised(feature_frame, horizons=4)
    model = ColumnSelector(NAIVE_DAILY_COLUMN).fit(X, y)
    assert np.allclose(model.predict(X), X[NAIVE_DAILY_COLUMN].to_numpy())


def test_column_selector_rejects_a_missing_column(feature_frame):
    from sp1.features import make_supervised

    X, y, _ = make_supervised(feature_frame, horizons=4)
    model = ColumnSelector("not_a_column").fit(X, y)
    with pytest.raises(ContractError, match="not in the feature matrix"):
        model.predict(X.drop(columns=["lag_kwh_1"]))


def test_hour_of_week_profile_learns_cell_means_and_falls_back(feature_frame):
    from sp1.features import make_supervised

    X, y, _ = make_supervised(feature_frame, horizons=24)
    model = HourOfWeekProfile().fit(X, y)
    seen = X.iloc[[0]]
    assert model.predict(seen)[0] == pytest.approx(
        model.profile_.loc[(seen["day_of_week"].iloc[0], seen["hour_of_day"].iloc[0])]
    )
    unseen = pd.DataFrame({"day_of_week": [3], "hour_of_day": [3]})
    model.profile_ = model.profile_.drop(index=[(3, 3)], errors="ignore")
    assert model.predict(unseen)[0] == pytest.approx(model.global_mean_)


def test_build_models_includes_baselines_and_ml(feature_frame):
    models = build_models(random_state=1)
    for name in ("naive_daily", "naive_weekly", "hour_of_week_profile", "ridge"):
        assert name in models


def test_rolling_backtest_produces_out_of_sample_predictions(feature_frame):
    from sp1.features import NAIVE_DAILY_COLUMN

    result = rolling_backtest(
        feature_frame,
        ColumnSelector(NAIVE_DAILY_COLUMN),
        horizon=24,
        step=24,
        min_train_intervals=72,
        n_origins=3,
    )
    predictions = result.predictions
    assert result.metrics["n_origins"] == 3
    assert len(predictions) == 72
    assert predictions["timestamp"].is_monotonic_increasing
    assert predictions["timestamp"].diff().dropna().eq(pd.Timedelta(hours=1)).all()
    assert (predictions["predicted_kwh"] >= 0).all()
    assert not predictions[["predicted_kwh", "actual_kwh"]].isna().any().any()
    # Every forecast must be made before the interval it predicts.
    assert (pd.DatetimeIndex(predictions["origin"]) < pd.DatetimeIndex(predictions["timestamp"])).all()
    assert set(result.metrics["residual_std_by_horizon"]) == {str(h) for h in range(1, 25)}


def test_rolling_backtest_never_trains_on_future_targets():
    """With a ramp as the target, the newest training value pins the boundary.

    y increases by 1 per hourly interval, so ``max(y_train)`` says exactly which
    interval the newest training sample targeted. If the backtest leaked, that
    value would jump to or past the origin.
    """
    from sp1.pipeline import build_feature_frame

    n_intervals = 24 * 12
    timestamps = pd.date_range("2026-01-01", periods=n_intervals, freq="1h", tz="UTC")
    ramp = pd.DataFrame(
        {"timestamp": timestamps, "demand_kwh": np.arange(n_intervals, dtype="float64")}
    )
    feature = build_feature_frame(ramp, local_tz="Asia/Shanghai")

    class SpyModel:
        def __init__(self) -> None:
            self.max_train_y = None

        def fit(self, X, y):
            self.max_train_y = float(np.max(y))
            return self

        def predict(self, X):
            return np.zeros(len(X), dtype="float64")

    spy = SpyModel()
    result = rolling_backtest(
        feature, spy, horizon=24, step=24, min_train_intervals=72, n_origins=2
    )
    assert result.metrics["n_origins"] == 2
    assert spy.max_train_y is not None
    # The newest training target must be the interval immediately before the
    # last origin used — never the origin itself, and never anything later.
    last_origin = pd.DatetimeIndex(result.predictions["origin"]).max()
    origin_position = int((last_origin - timestamps[0]) / pd.Timedelta(hours=1))
    assert spy.max_train_y == origin_position - 1


def test_hour_of_week_profile_learns_a_seasonal_series():
    """On a series that repeats every local day, the profile model must nail it."""
    from sp1.pipeline import build_feature_frame

    hours = np.array(
        [0, 0, 0, 0, 0, 1, 3, 6, 8, 5, 3, 2, 2, 3, 5, 7, 9, 12, 14, 11, 7, 4, 2, 1],
        dtype="float64",
    )
    n_intervals = 24 * 20
    timestamps = pd.date_range("2026-01-05", periods=n_intervals, freq="1h", tz="UTC")
    # The pattern is anchored to UTC hours, so it repeats identically every day.
    values = np.tile(hours, n_intervals // 24)
    frame = build_feature_frame(
        pd.DataFrame({"timestamp": timestamps, "demand_kwh": values}), local_tz="Asia/Shanghai"
    )
    X, y, _ = make_supervised(frame, horizons=24)
    model = HourOfWeekProfile().fit(X, y)
    metrics = summarize_metrics(y.to_numpy(), model.predict(X))
    assert metrics["wape"] < 0.01
    assert metrics["r2"] > 0.99


def test_backtest_metrics_are_finite_on_noisy_synthetic_demand(feature_frame):
    """Sanity check: the fixtures are noisy, so no model is expected to be perfect."""
    result = rolling_backtest(
        feature_frame,
        HourOfWeekProfile(),
        horizon=24,
        step=24,
        min_train_intervals=72,
        n_origins=3,
    )
    assert np.isfinite(result.metrics["wape"])
    assert result.metrics["wape"] < 2.0
    assert result.metrics["n_intervals"] == 72


def test_evaluate_models_and_ranking(feature_frame):
    from sp1.features import NAIVE_DAILY_COLUMN

    results = evaluate_models(
        feature_frame,
        models={
            "naive_daily": ColumnSelector(NAIVE_DAILY_COLUMN),
            "profile": HourOfWeekProfile(),
        },
        horizon=24,
        step=24,
        min_train_intervals=72,
        n_origins=2,
    )
    assert set(results) == {"naive_daily", "profile"}
    table = ranking_table(results)
    assert table["wape"].is_monotonic_increasing
    assert "wape" in table.columns and "mae_kwh" in table.columns


def test_train_window_caps_the_training_history():
    """A bounded training window must actually shrink the training set."""
    from sp1.pipeline import build_feature_frame

    n_intervals = 24 * 60
    timestamps = pd.date_range("2026-01-01", periods=n_intervals, freq="1h", tz="UTC")
    values = 10 + 5 * np.sin(2 * np.pi * np.arange(n_intervals) / 24)
    feature = build_feature_frame(
        pd.DataFrame({"timestamp": timestamps, "demand_kwh": values}), local_tz="Asia/Shanghai"
    )

    class Spy:
        def __init__(self) -> None:
            self.rows: list[int] = []

        def fit(self, X, y):
            self.rows.append(len(X))
            return self

        def predict(self, X):
            return np.zeros(len(X))

    unbounded, bounded = Spy(), Spy()
    rolling_backtest(feature, unbounded, horizon=24, step=24, min_train_intervals=72, n_origins=1)
    rolling_backtest(
        feature,
        bounded,
        horizon=24,
        step=24,
        min_train_intervals=72,
        n_origins=1,
        train_window_intervals=24 * 7,
    )
    assert bounded.rows[-1] < unbounded.rows[-1]
    # One week of intervals x 24 horizons is the ceiling for the bounded run.
    assert bounded.rows[-1] <= 24 * 7 * 24


def test_add_residual_intervals_brackets_the_prediction():
    predictions = pd.DataFrame(
        {
            "timestamp": pd.date_range("2026-09-26", periods=3, freq="1h", tz="UTC"),
            "predicted_kwh": [5.0, 5.0, 5.0],
            "horizon": [1, 2, 3],
        }
    )
    out = add_residual_intervals(predictions, {"1": 1.0, "2": 2.0, "3": 3.0})
    assert (out["lower_bound_kwh"] <= out["predicted_kwh"]).all()
    assert (out["upper_bound_kwh"] >= out["predicted_kwh"]).all()
    assert (out["lower_bound_kwh"] >= 0).all()
    widths = (out["upper_bound_kwh"] - out["lower_bound_kwh"]).to_numpy()
    assert widths[0] < widths[1] < widths[2]


def test_add_residual_intervals_clips_at_zero():
    predictions = pd.DataFrame(
        {
            "timestamp": pd.date_range("2026-09-26", periods=1, freq="1h", tz="UTC"),
            "predicted_kwh": [0.5],
            "horizon": [1],
        }
    )
    out = add_residual_intervals(predictions, {"1": 10.0})
    assert out["lower_bound_kwh"].iloc[0] == 0.0
