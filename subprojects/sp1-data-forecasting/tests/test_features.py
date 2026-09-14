"""Feature construction: correct alignment, and above all no leakage."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from sp1.contract import ContractError
from sp1.features import (
    NAIVE_DAILY_COLUMN,
    NAIVE_WEEKLY_COLUMN,
    add_calendar_features,
    add_lag_features,
    assert_no_leakage,
    make_supervised,
    rolling_origin_splits,
)


def test_calendar_features_use_local_time(demand_frame):
    frame = add_calendar_features(demand_frame, local_tz="Asia/Shanghai")
    first = frame.iloc[0]
    local = pd.Timestamp(first["timestamp"]).tz_convert("Asia/Shanghai")
    assert first["hour_of_day"] == local.hour
    assert first["day_of_week"] == local.dayofweek
    assert bool(first["is_weekend"]) == (local.dayofweek >= 5)
    # Cyclical encodings must be on the unit circle.
    assert first["hour_sin"] ** 2 + first["hour_cos"] ** 2 == pytest.approx(1.0)


def test_lag_features_look_backwards_only(demand_frame):
    frame = add_lag_features(demand_frame)
    index = 200
    assert frame["lag_kwh_1"].iloc[index] == demand_frame["demand_kwh"].iloc[index - 1]
    assert frame["lag_kwh_24"].iloc[index] == demand_frame["demand_kwh"].iloc[index - 24]
    assert frame["roll_mean_kwh_24"].iloc[index] == pytest.approx(
        demand_frame["demand_kwh"].iloc[index - 24 : index].mean()
    )
    # The first rows cannot see the future, so they are NaN rather than zero.
    assert frame["lag_kwh_24"].isna().sum() == 24


def test_make_supervised_aligns_targets_with_horizons(feature_frame):
    X, y, index = make_supervised(feature_frame, horizons=24)
    assert len(X) == len(y) == len(index)
    assert not X.isna().any().any()
    assert set(index["horizon"].unique()) == set(range(1, 25))

    offset = (index["target_timestamp"] - pd.DatetimeIndex(index["origin"])) / pd.Timedelta(hours=1)
    assert (offset.to_numpy() == index["horizon"].to_numpy()).all()

    target = feature_frame.set_index("timestamp")["demand_kwh"]
    # .loc (not .reindex) because the same interval legitimately appears as the
    # target of several origins.
    expected = target.loc[pd.DatetimeIndex(index["target_timestamp"])].to_numpy()
    assert np.allclose(y.to_numpy(), expected)


def test_naive_columns_equal_the_value_one_day_and_one_week_earlier(feature_frame):
    X, _y, index = make_supervised(feature_frame, horizons=24)
    target = feature_frame.set_index("timestamp")["demand_kwh"]
    for hours, column in ((24, NAIVE_DAILY_COLUMN), (168, NAIVE_WEEKLY_COLUMN)):
        reference = pd.DatetimeIndex(index["target_timestamp"]) - pd.Timedelta(hours=hours)
        expected = target.loc[reference].to_numpy()
        assert np.allclose(X[column].to_numpy(), expected)


def test_supervised_calendar_features_describe_the_target_interval(feature_frame):
    X, _, index = make_supervised(feature_frame, horizons=24)
    local = pd.DatetimeIndex(index["target_timestamp"]).tz_convert("Asia/Shanghai")
    assert (X["hour_of_day"].to_numpy() == local.hour.to_numpy()).all()
    assert (X["day_of_week"].to_numpy() == np.asarray(local.dayofweek)).all()
    assert (X["is_weekend"].to_numpy() == np.asarray(local.dayofweek >= 5)).all()


def test_assert_no_leakage_passes_on_a_correct_frame(feature_frame):
    X, _, index = make_supervised(feature_frame, horizons=24)
    assert_no_leakage(X, index, feature_frame)


def test_assert_no_leakage_catches_a_corrupted_lag(feature_frame):
    X, _, index = make_supervised(feature_frame, horizons=24)
    leaky = X.copy()
    leaky["lag_kwh_24"] = leaky["lag_kwh_24"] + 1.0
    with pytest.raises(AssertionError, match="lag_kwh_24"):
        assert_no_leakage(leaky, index, feature_frame)


def test_make_supervised_rejects_a_series_shorter_than_the_horizon():
    frame = pd.DataFrame(
        {
            "timestamp": pd.date_range("2026-09-26", periods=5, freq="1h", tz="UTC"),
            "demand_kwh": np.arange(5.0),
        }
    )
    with pytest.raises(ContractError, match="need more than"):
        make_supervised(frame, horizons=24)


def test_rolling_origin_splits_are_chronological_and_disjoint():
    splits = rolling_origin_splits(n_samples=240, n_folds=3, horizon=24, min_train=72)
    assert len(splits) == 3
    for train_end, test_start, test_end in splits:
        assert train_end == test_start
        assert test_end - test_start == 24
        assert train_end >= 72
    assert splits[-1][2] == 240
    assert splits[0][0] < splits[1][0] < splits[2][0]


def test_rolling_origin_splits_reject_a_short_series():
    with pytest.raises(ContractError, match="at least"):
        rolling_origin_splits(n_samples=50, n_folds=3, horizon=24, min_train=72)
