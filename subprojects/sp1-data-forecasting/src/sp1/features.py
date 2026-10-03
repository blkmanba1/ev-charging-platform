"""Features for supervised demand forecasting.

Design: **direct multi-horizon forecasting with the horizon as a feature.**

Training samples are built from forecast *origins*. For an origin ``t`` and a
horizon ``h`` in ``1..H`` the target is the demand in interval ``t + h``, and the
features are

* everything known at the origin — the target's own lags and rolling statistics,
  all of them computed from intervals ``<= t`` (never later); and
* everything known about the *future* interval regardless of demand — its local
  hour of day, day of week, weekend flag, and cyclical encodings.

One model therefore produces the whole 24-hour profile from a single origin, and
there is no error accumulation from recursive one-step prediction. The lag and
rolling features are shifted so that no feature at the origin can see the
interval being predicted; :func:`assert_no_leakage` checks that property.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .contract import STORE_TZ, ContractError

LOCAL_TZ = "Asia/Shanghai"

DEFAULT_LAGS: tuple[int, ...] = (1, 2, 3, 24, 48, 168)
DEFAULT_ROLLING_WINDOWS: tuple[int, ...] = (24, 168)

#: Seasonality periods, in hourly intervals.
DAILY_PERIOD_HOURS = 24
WEEKLY_PERIOD_HOURS = 168

#: Columns holding the naive ("same interval one day / one week earlier")
#: prediction for each sample, written by :func:`make_supervised`.
NAIVE_DAILY_COLUMN = "naive_daily_kwh"
NAIVE_WEEKLY_COLUMN = "naive_weekly_kwh"

#: Calendar columns. Unlike lags, these describe the interval being predicted —
#: they are known in advance, so a day-ahead model may legitimately use them.
CALENDAR_COLUMNS: tuple[str, ...] = (
    "hour_of_day",
    "day_of_week",
    "is_weekend",
    "month",
    "hour_sin",
    "hour_cos",
    "dow_sin",
    "dow_cos",
)


def add_calendar_features(
    series: pd.DataFrame, local_tz: str = LOCAL_TZ, timestamp_column: str = "timestamp"
) -> pd.DataFrame:
    """Add local-calendar features for each interval.

    Calendar features are safe for the future: they are known in advance. They
    are derived in ``local_tz`` because charging behaviour follows the local
    clock, while the stored timestamps stay UTC.

    Returns
    -------
    pandas.DataFrame
        Copy of ``series`` plus ``hour_of_day``, ``day_of_week``, ``is_weekend``,
        ``month``, ``hour_sin``, ``hour_cos``, ``dow_sin``, ``dow_cos``.
    """
    frame = series.copy()
    local = pd.DatetimeIndex(frame[timestamp_column])
    if local.tz is None:
        local = local.tz_localize(STORE_TZ)
    local = local.tz_convert(local_tz)

    frame["hour_of_day"] = local.hour
    frame["day_of_week"] = local.dayofweek
    frame["is_weekend"] = (local.dayofweek >= 5).astype("int8")
    frame["month"] = local.month
    frame["hour_sin"] = np.sin(2 * np.pi * local.hour / 24.0)
    frame["hour_cos"] = np.cos(2 * np.pi * local.hour / 24.0)
    frame["dow_sin"] = np.sin(2 * np.pi * local.dayofweek / 7.0)
    frame["dow_cos"] = np.cos(2 * np.pi * local.dayofweek / 7.0)
    return frame


def add_lag_features(
    frame: pd.DataFrame,
    target_column: str = "demand_kwh",
    lags: tuple[int, ...] = DEFAULT_LAGS,
    rolling_windows: tuple[int, ...] = DEFAULT_ROLLING_WINDOWS,
) -> pd.DataFrame:
    """Add lagged and rolling-window features of the demand series.

    Every feature at row ``t`` uses only intervals ``<= t``, so a row can be
    used as a forecast origin without leakage. Rolling statistics are shifted by
    one interval for the same reason.

    Returns
    -------
    pandas.DataFrame
        Copy of ``frame`` plus ``lag_kwh_<n>``, ``roll_mean_kwh_<n>``,
        ``roll_std_kwh_<n>`` and ``roll_max_kwh_<n>``. The first ``max(lags)``
        rows carry NaN and are dropped by :func:`make_supervised`.
    """
    out = frame.copy()
    target = pd.to_numeric(out[target_column], errors="coerce")
    for lag in lags:
        out[f"lag_kwh_{lag}"] = target.shift(lag)
    for window in rolling_windows:
        rolled = target.shift(1).rolling(window=window, min_periods=window)
        out[f"roll_mean_kwh_{window}"] = rolled.mean()
        out[f"roll_std_kwh_{window}"] = rolled.std()
        out[f"roll_max_kwh_{window}"] = rolled.max()
    return out


def feature_columns(frame: pd.DataFrame, target_column: str = "demand_kwh") -> list[str]:
    """Return the model input columns present in ``frame`` (excludes the target).

    Internal bookkeeping columns (any name starting with ``_``) are never
    features — ``_target`` in particular would be pure leakage.
    """
    excluded = {target_column, "timestamp", "session_count"}
    return [
        c for c in frame.columns if c not in excluded and not c.startswith("_")
    ]


def make_supervised(
    frame: pd.DataFrame,
    target_column: str = "demand_kwh",
    horizons: int | tuple[int, ...] = 24,
) -> tuple[pd.DataFrame, pd.Series, pd.DataFrame]:
    """Build ``(X, y, index)`` training samples from a feature frame.

    Parameters
    ----------
    frame : pandas.DataFrame
        Output of :func:`add_calendar_features` + :func:`add_lag_features`, on a
        gap-free hourly grid in UTC.
    target_column : str
        Column to predict, in kWh per interval.
    horizons : int | tuple of int
        A single ``H`` builds horizons ``1..H``; a tuple builds exactly those.

    Returns
    -------
    X : pandas.DataFrame
        One row per (origin, horizon) pair, in interval order. Rows still inside
        a lag/rolling warm-up window are dropped, so ``X`` has no NaN.
    y : pandas.Series
        Target demand values, aligned with ``X``.
    index : pandas.DataFrame
        ``origin`` (UTC timestamp), ``target_timestamp`` (UTC) and ``horizon``
        for each row — needed to group forecasts back into origins.
    """
    if target_column not in frame.columns:
        raise ContractError(f"'{target_column}' is not in the frame")
    horizon_list = (
        tuple(range(1, horizons + 1)) if isinstance(horizons, int) else tuple(horizons)
    )
    if not horizon_list:
        raise ContractError("at least one horizon is required")
    if len(frame) <= max(horizon_list):
        raise ContractError(
            f"need more than {max(horizon_list)} intervals to build any sample, got {len(frame)}"
        )

    working = frame.reset_index(drop=True)
    working["_origin_pos"] = np.arange(len(working))
    target = pd.to_numeric(working[target_column], errors="coerce")

    records: list[pd.DataFrame] = []
    for horizon in horizon_list:
        shifted = working.copy()
        shifted["_target_pos"] = shifted["_origin_pos"] + horizon
        shifted["_target"] = target.shift(-horizon)
        # Naive predictions for the target interval, computed only when the
        # reference interval is at or before the origin (no leakage):
        # target - 24h = origin + horizon - 24h, so shift by 24 - horizon.
        shifted[NAIVE_DAILY_COLUMN] = (
            target.shift(DAILY_PERIOD_HOURS - horizon)
            if horizon <= DAILY_PERIOD_HOURS
            else np.nan
        )
        shifted[NAIVE_WEEKLY_COLUMN] = (
            target.shift(WEEKLY_PERIOD_HOURS - horizon)
            if horizon <= WEEKLY_PERIOD_HOURS
            else np.nan
        )
        records.append(shifted)

    stacked = pd.concat(records, ignore_index=True)
    stacked = stacked[stacked["_target_pos"] < len(working)].reset_index(drop=True)
    stacked["horizon"] = (stacked["_target_pos"] - stacked["_origin_pos"]).astype("int64")
    positions = stacked["_target_pos"].to_numpy()
    # Assign as a Series (not .to_numpy()) so the UTC timezone is preserved.
    stacked["_target_timestamp"] = (
        working["timestamp"].iloc[positions].reset_index(drop=True)
    )
    # Calendar features must describe the *target* interval, not the origin: they
    # are known in advance, and a profile model that thinks 03:00 is 19:00 is
    # useless. Lag and rolling features stay at the origin — those are the ones
    # that must never see the future.
    for column in CALENDAR_COLUMNS:
        if column in working.columns:
            stacked[column] = working[column].iloc[positions].to_numpy()
    stacked = stacked[stacked["_target"].notna()].reset_index(drop=True)

    inputs = feature_columns(stacked, target_column=target_column)
    stacked = stacked.sort_values(["_origin_pos", "horizon"], ignore_index=True)
    X = stacked[inputs].astype("float64")
    y = stacked["_target"].astype("float64")
    index = pd.DataFrame(
        {
            "origin": stacked["timestamp"].reset_index(drop=True),
            "target_timestamp": stacked["_target_timestamp"].reset_index(drop=True),
            "horizon": stacked["horizon"].reset_index(drop=True),
        }
    )

    # Warm-up rows still hold NaN lags/rolling stats: drop them rather than let
    # a model silently learn from missing values.
    usable = np.isfinite(X.to_numpy(dtype="float64")).all(axis=1)
    X = X[usable].reset_index(drop=True)
    y = y[usable].reset_index(drop=True)
    index = index[usable].reset_index(drop=True)
    if X.empty:
        raise ContractError("no usable samples: the series is shorter than the warm-up window")
    return X, y, index


def rolling_origin_splits(
    n_samples: int,
    n_folds: int = 5,
    horizon: int = 24,
    min_train: int = 24 * 14,
    step: int | None = None,
) -> list[tuple[int, int, int]]:
    """Return expanding-window ``(train_end, test_start, test_end)`` splits.

    Splits are chronological: training never contains an interval at or after the
    test start, which is what makes the reported accuracy honest.

    Parameters
    ----------
    n_samples : int
        Number of hourly intervals available.
    n_folds : int
        Number of test folds to produce.
    horizon : int
        Test-fold length in intervals (24 = one day).
    min_train : int
        Minimum training length in intervals.
    step : int | None
        Distance between folds; defaults to ``horizon`` (non-overlapping tests).

    Returns
    -------
    list of tuple of int
        Each tuple is ``(train_end, test_start, test_end)`` with
        ``train_end == test_start``, so training data is ``frame[:train_end]``.
    """
    step = step or horizon
    last_start = n_samples - horizon
    if last_start < min_train:
        raise ContractError(
            f"need at least {min_train + horizon} intervals to evaluate, got {n_samples}"
        )
    starts = [last_start - i * step for i in range(n_folds)][::-1]
    starts = [s for s in starts if s >= min_train]
    if not starts:
        raise ContractError(
            f"no fold fits: min_train={min_train}, horizon={horizon}, n_samples={n_samples}"
        )
    return [(s, s, s + horizon) for s in starts]


def assert_no_leakage(
    X: pd.DataFrame,
    index: pd.DataFrame,
    frame: pd.DataFrame,
    target_column: str = "demand_kwh",
) -> None:
    """Verify that no feature row can see its own target interval.

    Recomputes each lag feature from the raw series and compares it with the
    value in ``X``. Any mismatch means the feature was built with a shift that is
    too small — the classic way a forecasting model reports fantasy accuracy.

    Raises
    ------
    AssertionError
        If a lag feature does not equal the true value from the origin interval.
    """
    target = pd.to_numeric(frame[target_column], errors="coerce").to_numpy()
    positions = pd.Series(np.arange(len(frame)), index=pd.DatetimeIndex(frame["timestamp"]))
    origins = positions.reindex(pd.DatetimeIndex(index["origin"])).to_numpy()

    for column in X.columns:
        if not column.startswith("lag_kwh_"):
            continue
        lag = int(column.rsplit("_", 1)[1])
        expected = target[origins - lag]
        actual = X[column].to_numpy()
        if not np.allclose(expected, actual, equal_nan=True):
            raise AssertionError(f"feature '{column}' leaks or is misaligned with the target")
