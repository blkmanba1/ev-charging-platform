"""Forecasting models, rolling-origin evaluation and residual-based intervals.

Three kinds of model are provided behind one interface (``fit`` / ``predict``):

* **naive baselines** — read the ``naive_daily_kwh`` / ``naive_weekly_kwh``
  columns that :func:`sp1.features.make_supervised` writes for each sample;
* **a seasonal profile** — mean demand by local hour-of-week, fitted on training
  data only;
* **machine-learning models** — ridge regression, random forest, gradient
  boosting, and XGBoost when it is installed.

Mixing them in one evaluation is the point: SP1 has to show that the ML model
earns its complexity against a naive baseline, not just report an error number.

Because demand is zero for most hours of the day, percentage errors are unstable;
:func:`summarize_metrics` therefore leads with **WAPE** (total absolute error
over total demand) and reports MAPE only for informative intervals.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, RegressorMixin
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from .contract import ContractError
from .features import (
    LOCAL_TZ,
    NAIVE_DAILY_COLUMN,
    NAIVE_WEEKLY_COLUMN,
    make_supervised,
)

Z_90 = 1.6448536269514722  # two-sided 90% normal quantile


# --------------------------------------------------------------------------- #
# models
# --------------------------------------------------------------------------- #
class ColumnSelector(BaseEstimator, RegressorMixin):
    """Baseline "model" that returns one pre-computed column of ``X``.

    Parameters
    ----------
    column : str
        Name of a column of the feature frame that already holds the prediction,
        e.g. ``naive_daily_kwh`` (the value 24 hours before the target interval).
    """

    def __init__(self, column: str):
        self.column = column

    def fit(self, X: pd.DataFrame, y: object = None):
        """No-op; the prediction is already in ``X``."""
        self.columns_ = list(X.columns)
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Return ``X[column]`` as a float array (kWh per interval)."""
        if self.column not in X.columns:
            raise ContractError(f"column '{self.column}' is not in the feature matrix")
        return pd.to_numeric(X[self.column], errors="coerce").fillna(0.0).to_numpy(dtype="float64")


class HourOfWeekProfile(BaseEstimator, RegressorMixin):
    """Seasonal profile baseline: mean demand per local (weekday, hour).

    Fitted on training rows only. Unseen combinations fall back to the global
    training mean, so the model always returns a finite number.
    """

    def fit(self, X: pd.DataFrame, y: object):
        frame = pd.DataFrame(
            {
                "day_of_week": np.asarray(X["day_of_week"]),
                "hour_of_day": np.asarray(X["hour_of_day"]),
                "y": np.asarray(y, dtype="float64"),
            }
        )
        self.profile_ = frame.groupby(["day_of_week", "hour_of_day"])["y"].mean()
        self.global_mean_ = float(frame["y"].mean())
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Return the fitted profile value for each row (kWh per interval)."""
        keys = pd.MultiIndex.from_arrays(
            [np.asarray(X["day_of_week"]), np.asarray(X["hour_of_day"])]
        )
        values = self.profile_.reindex(keys).to_numpy(dtype="float64")
        return np.where(np.isfinite(values), values, self.global_mean_)


def build_models(random_state: int = 42) -> dict[str, BaseEstimator]:
    """Return the model zoo, cheap baselines first.

    Returns
    -------
    dict of str to estimator
        Keys are stable names used in the metrics report. XGBoost is included
        only when the package is importable.
    """
    models: dict[str, BaseEstimator] = {
        "naive_daily": ColumnSelector(NAIVE_DAILY_COLUMN),
        "naive_weekly": ColumnSelector(NAIVE_WEEKLY_COLUMN),
        "hour_of_week_profile": HourOfWeekProfile(),
        "ridge": Pipeline(
            [("scaler", StandardScaler()), ("ridge", Ridge(alpha=1.0))]
        ),
        "random_forest": RandomForestRegressor(
            n_estimators=200,
            min_samples_leaf=2,
            n_jobs=-1,
            random_state=random_state,
        ),
        "gradient_boosting": HistGradientBoostingRegressor(
            max_iter=300, learning_rate=0.06, random_state=random_state
        ),
    }
    try:  # pragma: no cover - depends on the local environment
        from xgboost import XGBRegressor

        models["xgboost"] = XGBRegressor(
            n_estimators=400,
            learning_rate=0.05,
            max_depth=6,
            subsample=0.9,
            colsample_bytree=0.9,
            random_state=random_state,
            n_jobs=-1,
        )
    except ImportError:  # pragma: no cover
        pass
    return models


# --------------------------------------------------------------------------- #
# metrics
# --------------------------------------------------------------------------- #
def summarize_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, object]:
    """Return MAE / RMSE / WAPE / sMAPE / R² for a pair of arrays.

    All values are in kWh per interval except the three ratios, which are
    dimensionless. WAPE is reported first because it is stable when many
    intervals have zero demand.

    Parameters
    ----------
    y_true, y_pred : array-like
        Actual and predicted demand, same length, kWh per 1-hour interval.
    """
    y_true = np.asarray(y_true, dtype="float64")
    y_pred = np.asarray(y_pred, dtype="float64")
    if y_true.shape != y_pred.shape:
        raise ContractError(f"shape mismatch: {y_true.shape} vs {y_pred.shape}")
    if y_true.size == 0:
        raise ContractError("cannot score an empty prediction")

    error = y_pred - y_true
    denominator = float(np.abs(y_true).sum())
    scale = float(np.abs(y_true).mean())
    smape_denominator = np.abs(y_true) + np.abs(y_pred)
    informative = smape_denominator > 0
    variance = float(((y_true - y_true.mean()) ** 2).sum())
    return {
        "mae_kwh": float(np.abs(error).mean()),
        "rmse_kwh": float(np.sqrt((error**2).mean())),
        "wape": float(np.abs(error).sum() / denominator) if denominator else float("nan"),
        "smape": float(
            (2 * np.abs(error)[informative] / smape_denominator[informative]).mean()
        )
        if informative.any()
        else float("nan"),
        "rmse_over_mean": float(np.sqrt((error**2).mean()) / scale) if scale else float("nan"),
        "r2": float(1 - (error**2).sum() / variance) if variance else float("nan"),
        "n_intervals": int(y_true.size),
        "mean_actual_kwh": float(y_true.mean()),
    }


# --------------------------------------------------------------------------- #
# rolling-origin backtest
# --------------------------------------------------------------------------- #
@dataclass
class BacktestResult:
    """Out-of-sample forecasts produced by a rolling-origin backtest.

    Attributes
    ----------
    predictions : pandas.DataFrame
        ``timestamp`` (UTC interval start), ``actual_kwh``, ``predicted_kwh``,
        ``horizon``, ``origin`` — one row per forecast interval.
    metrics : dict
        Overall metrics plus ``per_horizon`` (list of dicts) and
        ``residual_std_by_horizon`` (used to build confidence bounds).
    """

    predictions: pd.DataFrame
    metrics: dict = field(default_factory=dict)


def rolling_backtest(
    feature_frame: pd.DataFrame,
    model: BaseEstimator,
    horizon: int = 24,
    step: int = 24,
    min_train_intervals: int = 24 * 14,
    target_column: str = "demand_kwh",
    last_origin: object | None = None,
    n_origins: int | None = None,
    origin_hour_local: int | None = 0,
    local_tz: str = LOCAL_TZ,
    train_window_intervals: int | None = None,
) -> BacktestResult:
    """Forecast every interval in the evaluation window, one origin at a time.

    For each origin the model is fitted **only** on samples whose target
    interval lies strictly before that origin, so every prediction is genuinely
    out of sample. Origins are spaced ``step`` intervals apart (24 = one
    day-ahead forecast per day), and only origins whose full horizon fits inside
    the data are used, so the evaluation window is always gap-free.

    Parameters
    ----------
    feature_frame : pandas.DataFrame
        Gap-free hourly frame with calendar, lag and naive columns.
    model : estimator
        Anything with ``fit`` / ``predict``, e.g. from :func:`build_models`.
    horizon : int
        Forecast horizon in intervals.
    step : int
        Distance between consecutive origins.
    min_train_intervals : int
        Minimum number of hourly intervals of history that must precede an
        origin, counted from the start of the series.
    target_column : str
        Column to predict, kWh per interval.
    last_origin : timestamp-like | None
        Latest origin to use; defaults to the last origin with a full horizon.
    n_origins : int | None
        Keep only the most recent ``n_origins`` origins (default: all of them).
    origin_hour_local : int | None
        Anchor origins to this local clock hour (0 = local midnight, i.e. a
        genuine day-ahead forecast). ``None`` uses whatever intervals the data
        happens to offer.
    local_tz : str
        Timezone used for ``origin_hour_local``.
    train_window_intervals : int | None
        Cap the training history to this many intervals before each origin
        (``24 * 365`` = one year). ``None`` uses all history, which is correct
        but slow on multi-year datasets; a bounded window is also what an
        operational forecaster would actually do.

    Returns
    -------
    BacktestResult
        Predictions for every interval in the evaluation window, plus metrics.
    """
    X, y, index = make_supervised(feature_frame, target_column=target_column, horizons=horizon)
    origins = pd.DatetimeIndex(index["origin"]).unique().sort_values()
    max_timestamp = pd.Timestamp(feature_frame["timestamp"].max())
    full_horizon = max_timestamp - pd.Timedelta(hours=horizon)

    latest = pd.Timestamp(last_origin) if last_origin is not None else full_horizon
    latest = min(latest, full_horizon)
    available = [origin for origin in origins if origin <= latest]
    if origin_hour_local is not None:
        aligned = [
            origin
            for origin in available
            if origin.tz_convert(local_tz).hour == origin_hour_local
            and origin.tz_convert(local_tz).minute == 0
        ]
        if aligned:
            available = aligned
    if not available:
        raise ContractError("no forecast origin available; the series is too short")
    # Walk backwards from the most recent origin in steps of ``step`` *hours*
    # (not list positions: once origins are anchored to local midnight the list
    # is already daily, and stepping by index would skip 24 days at a time).
    if step < 1:
        raise ContractError(f"step must be at least 1 hour, got {step}")
    available_set = set(available)
    cursor = available[-1]
    earliest = available[0]
    selected: list[pd.Timestamp] = []
    while cursor >= earliest:
        if cursor in available_set:
            selected.append(cursor)
        cursor = cursor - pd.Timedelta(hours=step)
    selected = selected[::-1]
    if n_origins is not None:
        selected = selected[-int(n_origins) :]
    if not selected:
        raise ContractError("no forecast origin available; the series is too short")

    first_timestamp = pd.Timestamp(feature_frame["timestamp"].min())
    target_timestamps = pd.DatetimeIndex(index["target_timestamp"])
    predictions: list[pd.DataFrame] = []
    for origin in selected:
        history_intervals = (origin - first_timestamp) / pd.Timedelta(hours=1)
        if history_intervals < min_train_intervals:
            continue
        # DatetimeIndex comparison already yields a numpy boolean array.
        train_mask = np.asarray(target_timestamps < origin)
        if train_window_intervals:
            window_start = pd.Timestamp(origin) - pd.Timedelta(hours=train_window_intervals)
            train_mask &= np.asarray(pd.DatetimeIndex(index["origin"]) >= window_start)
        test_mask = np.asarray(index["origin"] == origin)
        fitted = model.fit(X[train_mask], y[train_mask])
        predicted = np.asarray(fitted.predict(X[test_mask]), dtype="float64")
        predicted = np.clip(predicted, 0.0, None)
        subset = index.loc[test_mask].reset_index(drop=True)
        predictions.append(
            pd.DataFrame(
                {
                    "timestamp": pd.DatetimeIndex(subset["target_timestamp"]),
                    "predicted_kwh": predicted,
                    "actual_kwh": y[test_mask].to_numpy(dtype="float64"),
                    "horizon": subset["horizon"].to_numpy(dtype="int64"),
                    "origin": pd.DatetimeIndex(subset["origin"]),
                }
            )
        )
    if not predictions:
        raise ContractError(
            "no origin had enough training data; lower min_train_intervals or supply more history"
        )

    combined = pd.concat(predictions, ignore_index=True).sort_values("timestamp")
    combined = combined.drop_duplicates(subset="timestamp", keep="first").reset_index(drop=True)

    metrics = summarize_metrics(combined["actual_kwh"], combined["predicted_kwh"])
    per_horizon = []
    residual_std: dict[int, float] = {}
    for h, group in combined.groupby("horizon"):
        horizon_metrics = summarize_metrics(group["actual_kwh"], group["predicted_kwh"])
        horizon_metrics["horizon"] = int(h)
        per_horizon.append(horizon_metrics)
        residual_std[int(h)] = float((group["predicted_kwh"] - group["actual_kwh"]).std(ddof=1))
    metrics["per_horizon"] = per_horizon
    metrics["residual_std_by_horizon"] = {str(k): v for k, v in sorted(residual_std.items())}
    metrics["n_origins"] = int(combined["origin"].nunique())
    return BacktestResult(predictions=combined, metrics=metrics)


def add_residual_intervals(
    predictions: pd.DataFrame,
    residual_std_by_horizon: dict[str, float],
    z: float = Z_90,
) -> pd.DataFrame:
    """Add ``lower_bound_kwh`` / ``upper_bound_kwh`` from backtest residuals.

    The interval is ``prediction ± z * std(residual)`` at the same horizon, taken
    from the rolling-origin backtest. It is an empirical, per-horizon interval —
    cheap and honest — and the method is recorded in the meta file so SP5 does
    not mistake it for a model-based interval.

    Parameters
    ----------
    predictions : pandas.DataFrame
        Must contain ``predicted_kwh`` and ``horizon``.
    residual_std_by_horizon : dict
        Keys are horizons as strings (JSON round-trip friendly).
    z : float
        Multiplier; the default is the two-sided 90% normal quantile.

    Returns
    -------
    pandas.DataFrame
        Copy of ``predictions`` with both bound columns (kWh), clipped at zero.
    """
    out = predictions.copy()
    std = pd.to_numeric(
        out["horizon"].map({int(k): v for k, v in residual_std_by_horizon.items()}),
        errors="coerce",
    ).fillna(0.0)
    out["lower_bound_kwh"] = np.clip(out["predicted_kwh"] - z * std, 0.0, None)
    out["upper_bound_kwh"] = out["predicted_kwh"] + z * std
    return out


def evaluate_models(
    feature_frame: pd.DataFrame,
    models: dict[str, BaseEstimator] | None = None,
    horizon: int = 24,
    step: int = 24,
    min_train_intervals: int = 24 * 14,
    target_column: str = "demand_kwh",
    last_origin: object | None = None,
    n_origins: int | None = None,
    origin_hour_local: int | None = 0,
    local_tz: str = LOCAL_TZ,
    train_window_intervals: int | None = None,
) -> dict[str, BacktestResult]:
    """Run :func:`rolling_backtest` for every model and return the results.

    Returns
    -------
    dict of str to BacktestResult
        Keyed by model name, so the caller can rank models by WAPE and pick the
        winner for the contract output.
    """
    models = models or build_models()
    results: dict[str, BacktestResult] = {}
    for name, model in models.items():
        results[name] = rolling_backtest(
            feature_frame,
            model,
            horizon=horizon,
            step=step,
            min_train_intervals=min_train_intervals,
            target_column=target_column,
            last_origin=last_origin,
            n_origins=n_origins,
            origin_hour_local=origin_hour_local,
            local_tz=local_tz,
            train_window_intervals=train_window_intervals,
        )
    return results


def ranking_table(results: dict[str, BacktestResult]) -> pd.DataFrame:
    """Return one row per model with its overall metrics, ranked by WAPE."""
    rows = []
    for name, result in results.items():
        row = {k: v for k, v in result.metrics.items() if not isinstance(v, (list, dict))}
        row["model"] = name
        rows.append(row)
    table = pd.DataFrame(rows).set_index("model")
    return table.sort_values("wape")
