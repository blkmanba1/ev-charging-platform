"""Turn charging sessions into the 1-hour demand series the contract expects.

A *session* is one EV plugged in for a period, delivering a known energy:

======================  ======  ===========================================
column                  unit    meaning
======================  ======  ===========================================
``start_time_utc``      —       ISO-8601 UTC, connection time
``end_time_utc``        —       ISO-8601 UTC, disconnection time
``energy_kwh``          kWh     energy delivered over the session
======================  ======  ===========================================

The demand series is **energy per interval** (kWh), which for a 1-hour
resolution is numerically equal to the average power in kW. Session energy is
spread over the hourly intervals it overlaps, in proportion to the overlap
duration, so a session never disappears and never double-counts.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .contract import STORE_TZ, ContractError

RESOLUTION_HOURS = 1
_LOCAL_TZ = "Asia/Shanghai"

DEMAND_COLUMNS = ("timestamp", "demand_kwh", "session_count")


def _as_ns(values: pd.Series | pd.DatetimeIndex) -> pd.Series:
    """Return a tz-aware UTC series pinned to nanosecond resolution.

    pandas 3 keeps whatever resolution a datetime column arrived with
    (``datetime64[us, UTC]`` for second-level input, ``[ns]`` for parsed
    strings). Integer arithmetic on two different resolutions produces silent
    nonsense, so the unit is pinned before any arithmetic happens.
    """
    index = pd.DatetimeIndex(values)
    if index.tz is None:
        raise ContractError("timestamps must be timezone-aware (storage is UTC)")
    index = index.tz_convert(STORE_TZ).as_unit("ns")
    return pd.Series(index, index=values.index if isinstance(values, pd.Series) else None)


def build_hourly_demand(
    sessions: pd.DataFrame,
    start_col: str = "start_time_utc",
    end_col: str = "end_time_utc",
    energy_col: str = "energy_kwh",
) -> pd.DataFrame:
    """Aggregate sessions into an hourly demand series.

    Parameters
    ----------
    sessions : pandas.DataFrame
        Session table with the three columns below (any extra columns ignored).
    start_col, end_col, energy_col : str
        Column names holding UTC start, UTC end, and energy in kWh.

    Returns
    -------
    pandas.DataFrame
        Columns ``timestamp`` (UTC hourly interval start), ``demand_kwh``
        (energy delivered in that hour) and ``session_count`` (sessions that
        delivered energy in that hour), sorted ascending. **Not** gap-free —
        call :func:`complete_grid` for that. Rows are unique per timestamp.

    Raises
    ------
    ContractError
        If a required column is missing, energy is missing/negative, or a
        timestamp cannot be parsed.
    """
    missing = [c for c in (start_col, end_col, energy_col) if c not in sessions.columns]
    if missing:
        raise ContractError(f"session table is missing columns {missing}")
    if sessions.empty:
        return pd.DataFrame(columns=list(DEMAND_COLUMNS))

    start = _as_ns(pd.to_datetime(sessions[start_col], utc=True, format="ISO8601"))
    end = _as_ns(pd.to_datetime(sessions[end_col], utc=True, format="ISO8601"))
    energy = pd.to_numeric(sessions[energy_col], errors="coerce")

    if energy.isna().any():
        raise ContractError(f"{int(energy.isna().sum())} sessions have no {energy_col}")
    if (energy < 0).any():
        raise ContractError(f"{int((energy < 0).sum())} sessions have negative {energy_col}")

    instant = ~(end > start)

    frames: list[pd.DataFrame] = []
    if (~instant).any():
        frames.append(_spread_sessions(start[~instant], end[~instant], energy[~instant]))
    if instant.any():
        # A zero/negative-length session still delivered its energy: put all of it
        # in the hour it started in, and say so rather than dropping the session.
        frames.append(
            pd.DataFrame(
                {
                    "timestamp": start[instant].dt.floor("h"),
                    "energy_kwh": energy[instant].to_numpy(),
                }
            )
        )

    spread = pd.concat(frames, ignore_index=True)
    grouped = spread.groupby("timestamp", as_index=False).agg(
        demand_kwh=("energy_kwh", "sum"),
        session_count=("energy_kwh", "size"),
    )
    grouped = grouped.sort_values("timestamp", ignore_index=True)
    grouped["session_count"] = grouped["session_count"].astype("int64")
    grouped["demand_kwh"] = grouped["demand_kwh"].astype("float64")
    return grouped


def _spread_sessions(
    start: pd.Series, end: pd.Series, energy: pd.Series
) -> pd.DataFrame:
    """Split each session's energy across the hourly intervals it overlaps.

    Returns a long frame with one row per (session, interval) carrying the share
    of that session's energy assigned to the interval.

    The arithmetic is done in integer nanoseconds because ``to_numpy()`` on a
    timezone-aware pandas column returns ``object`` rather than ``datetime64``
    (pandas 3), which cannot be added to a ``timedelta64`` offset.
    """
    hour_ns = 3_600_000_000_000
    session_start_ns = start.astype("int64").to_numpy()
    session_end_ns = end.astype("int64").to_numpy()
    duration_ns = session_end_ns - session_start_ns
    first_hour_ns = (session_start_ns // hour_ns) * hour_ns
    # The session occupies intervals starting before its end, so a session that
    # ends exactly on the hour must not create a trailing empty interval.
    last_hour_ns = ((session_end_ns - 1) // hour_ns) * hour_ns

    n_intervals = ((last_hour_ns - first_hour_ns) // hour_ns + 1).astype("int64")
    row_index = np.repeat(np.arange(len(start)), n_intervals)
    offsets = np.concatenate([np.arange(n, dtype="int64") for n in n_intervals])
    interval_start_ns = first_hour_ns[row_index] + offsets * hour_ns

    overlap_ns = np.minimum(interval_start_ns + hour_ns, session_end_ns[row_index]) - np.maximum(
        interval_start_ns, session_start_ns[row_index]
    )
    overlap_ns = np.clip(overlap_ns, 0, None)

    share = overlap_ns / duration_ns[row_index]
    return pd.DataFrame(
        {
            "timestamp": pd.to_datetime(interval_start_ns, utc=True),
            "energy_kwh": energy.to_numpy()[row_index] * share,
        }
    )


def complete_grid(
    series: pd.DataFrame,
    value_columns: tuple[str, ...] = ("demand_kwh", "session_count"),
    start: object | None = None,
    end: object | None = None,
    fill_value: float = 0.0,
) -> pd.DataFrame:
    """Reindex an hourly series onto a gap-free UTC grid.

    An absent interval means *no charging was recorded*, which for a demand
    series is a true zero, so the default fill is 0.0. That is also what makes
    the series safe for SP2, which the contract promises a gap-free input.

    Parameters
    ----------
    series : pandas.DataFrame
        Output of :func:`build_hourly_demand`.
    value_columns : tuple of str
        Columns to create on the grid; missing intervals get ``fill_value``.
    start, end : timestamp-like | None
        Grid bounds. Default: the series' own min and max. ``end`` is inclusive.
    fill_value : float
        Value for intervals absent from ``series``.

    Returns
    -------
    pandas.DataFrame
        ``timestamp`` plus ``value_columns``, exactly 1 hour apart, ascending.
    """
    if series.empty:
        raise ContractError("cannot complete a grid for an empty series")

    observed_start = pd.Timestamp(series["timestamp"].min())
    observed_end = pd.Timestamp(series["timestamp"].max())
    grid_start = pd.Timestamp(start) if start is not None else observed_start
    grid_end = pd.Timestamp(end) if end is not None else observed_end
    for label, value in (("start", grid_start), ("end", grid_end)):
        if value.tzinfo is None:
            raise ContractError(f"{label} must be timezone-aware (storage is UTC)")
    if grid_end < grid_start:
        raise ContractError(f"end {grid_end} is before start {grid_start}")

    grid = pd.date_range(grid_start.ceil("h"), grid_end.floor("h"), freq="1h", tz=STORE_TZ)
    indexed = series.set_index(_as_ns(series["timestamp"])).sort_index()
    indexed = indexed.reindex(grid)

    out = pd.DataFrame({"timestamp": grid})
    for column in value_columns:
        values = indexed[column] if column in indexed.columns else pd.Series(index=grid, dtype="float64")
        out[column] = pd.to_numeric(values, errors="coerce").fillna(fill_value).to_numpy()
    if "session_count" in out.columns:
        out["session_count"] = out["session_count"].astype("int64")
    return out


def build_uncontrolled_profile(
    sessions: pd.DataFrame,
    plug_in_hour_local: int = 18,
    max_power_kw: float = 7.0,
    local_tz: str = _LOCAL_TZ,
    power_column: str | None = "power_kw",
) -> pd.DataFrame:
    """Build the "everyone plugs in at 18:00" baseline the contract asks for.

    Each session's energy is moved to a synthetic charging block that starts at
    ``plug_in_hour_local`` local time on the day the session originally started,
    so the total energy is preserved and only its *timing* changes. The block
    charges at the session's own recorded power when the dataset has one
    (``power_column``), falling back to ``max_power_kw`` otherwise — that keeps
    a 150 kW fast-charging session from being stretched over 40 hours.

    Deliberate simplifications (documented, not hidden): no queueing, no
    transformer or connection limits, and no per-station scheduling. It is a
    worst-case *shape*, not a network simulation.

    Parameters
    ----------
    sessions : pandas.DataFrame
        Canonical session table with ``start_time_utc``, ``end_time_utc``
        and ``energy_kwh``.
    plug_in_hour_local : int
        Local clock hour at which every vehicle is assumed to plug in.
    max_power_kw : float
        Charging power used when a session has no usable power of its own, in kW.
    local_tz : str
        Timezone used to place the plug-in hour.
    power_column : str | None
        Column holding the session's charging power in kW, or ``None`` to always
        use ``max_power_kw``.

    Returns
    -------
    pandas.DataFrame
        Hourly demand in kWh per interval, **not** yet gap-filled.
    """
    if max_power_kw <= 0:
        raise ContractError("max_power_kw must be positive")
    frame = sessions.dropna(subset=["start_time_utc", "energy_kwh"]).copy()
    frame = frame[frame["energy_kwh"] > 0]
    if frame.empty:
        raise ContractError("no sessions with positive energy to build a baseline from")

    if power_column and power_column in frame.columns:
        power = pd.to_numeric(frame[power_column], errors="coerce")
        power = power.where(power > 0).fillna(max_power_kw)
    else:
        power = pd.Series(max_power_kw, index=frame.index, dtype="float64")

    local_day = pd.DatetimeIndex(frame["start_time_utc"]).tz_convert(local_tz).normalize()
    plug_in_local = local_day + pd.Timedelta(hours=plug_in_hour_local)
    plug_in_utc = plug_in_local.tz_convert(STORE_TZ)
    duration_hours = (frame["energy_kwh"] / power).clip(lower=1.0 / 60.0)

    shifted = pd.DataFrame(
        {
            "start_time_utc": plug_in_utc,
            "end_time_utc": plug_in_utc + pd.to_timedelta(duration_hours, unit="h"),
            "energy_kwh": frame["energy_kwh"].to_numpy(dtype="float64"),
        }
    )
    return build_hourly_demand(shifted)


def to_local(timestamps: pd.Series | pd.DatetimeIndex, tz: str = _LOCAL_TZ):
    """Convert UTC storage timestamps to local time for analysis and plots."""
    index = pd.DatetimeIndex(timestamps)
    if index.tz is None:
        index = index.tz_localize(STORE_TZ)
    return index.tz_convert(tz)


def profile(
    series: pd.DataFrame,
    local_tz: str = _LOCAL_TZ,
    value_column: str = "demand_kwh",
) -> pd.DataFrame:
    """Average demand by local hour-of-day and by local weekday.

    This is the "charging patterns and user behaviour" summary SP1 is asked to
    produce; it is computed in local time because human behaviour follows the
    clock, while the stored series stays UTC.

    Returns
    -------
    pandas.DataFrame
        Index = local hour of day (0-23); columns = mean, median, p95, and the
        total energy share of each hour.
    """
    frame = series.copy()
    local = to_local(frame["timestamp"], local_tz)
    frame["local_hour"] = local.hour
    frame["local_weekday"] = local.dayofweek
    values = pd.to_numeric(frame[value_column], errors="coerce")
    total = float(values.sum())
    grouped = frame.assign(_value=values).groupby("local_hour")["_value"]
    summary = pd.DataFrame(
        {
            "mean_kwh": grouped.mean(),
            "median_kwh": grouped.median(),
            "p95_kwh": grouped.quantile(0.95),
            "total_kwh": grouped.sum(),
        }
    )
    summary["share_of_energy"] = (
        summary["total_kwh"] / total if total else np.nan
    )
    return summary
