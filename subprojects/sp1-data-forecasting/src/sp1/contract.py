"""Contract-compliant I/O for the SP1 output files.

Implements the format pinned in ``docs/integration-contract.md`` (v0.2):

* CSV, one header row, UTF-8, comma-separated, no index column.
* ``timestamp`` is an ISO-8601 UTC interval **start** ending in ``Z``.
* All intervals are exactly 1 hour (``resolution: "1h"``).
* Missing values are **empty cells** — never ``NaN``, ``null``, ``-`` or ``N/A``.
* Every output file ships with a sibling ``<name>.meta.json``.

The meta file name convention implemented here is ``sp1-demand-forecast-v1.csv``
-> ``sp1-demand-forecast-v1.meta.json`` (the ``.csv`` suffix is replaced by
``.meta.json``). See ``docs/integration-contract.md`` §"Cross-cutting: the meta
file" for the fields.

Public API
----------
- :func:`format_timestamp` — pandas timestamp -> contract string.
- :func:`parse_timestamps` — contract strings -> tz-aware UTC ``DatetimeIndex``.
- :func:`write_series_csv` / :func:`read_series_csv` — series round-trip.
- :func:`write_meta` / :func:`read_meta` — sibling meta file.
- :func:`validate_series` — the checks SP2/SP4 are entitled to rely on.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

SCHEMA_VERSION = "1.0"
RESOLUTION = "1h"
STORE_TZ = "UTC"
GENERATED_BY = "SP1"

#: Columns of ``sp1-demand-forecast-v1.csv`` (and the identical baseline file).
FORECAST_COLUMNS: tuple[str, ...] = (
    "timestamp",
    "predicted_demand_kwh",
    "lower_bound_kwh",
    "upper_bound_kwh",
)

#: Columns that carry numbers and may be empty when not modelled.
VALUE_COLUMNS: tuple[str, ...] = (
    "predicted_demand_kwh",
    "lower_bound_kwh",
    "upper_bound_kwh",
)

#: Tokens that must never appear in a numeric cell.
FORBIDDEN_MISSING_TOKENS: frozenset[str] = frozenset(
    {"nan", "null", "n/a", "na", "none", "-", "--", "?"}
)

_ISO_Z = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

META_SUFFIX = ".meta.json"


class ContractError(ValueError):
    """Raised when a file violates ``docs/integration-contract.md``."""


# --------------------------------------------------------------------------- #
# timestamps
# --------------------------------------------------------------------------- #
def format_timestamp(value: object) -> str:
    """Return ``value`` as an ISO-8601 UTC interval start, e.g. ``2026-09-26T14:00:00Z``.

    Parameters
    ----------
    value : pandas.Timestamp | datetime | str
        Naive values are interpreted as UTC (storage is always UTC).

    Returns
    -------
    str
        Contract string, truncated to the hour.

    Raises
    ------
    ContractError
        If the value is not on an exact hour boundary.
    """
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        ts = ts.tz_localize(STORE_TZ)
    else:
        ts = ts.tz_convert(STORE_TZ)
    if ts.minute or ts.second or ts.microsecond:
        raise ContractError(
            f"timestamp {ts.isoformat()} is not on an exact hour boundary; "
            f"the contract fixes a 1-hour resolution"
        )
    return ts.strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_timestamps(values: Iterable[object]) -> pd.DatetimeIndex:
    """Parse contract timestamps into a tz-aware UTC ``DatetimeIndex``.

    Parameters
    ----------
    values : iterable of str
        Values as written by :func:`format_timestamp`.

    Returns
    -------
    pandas.DatetimeIndex
        UTC-localised, sorted-checking is left to :func:`validate_series`.
    """
    parsed = pd.to_datetime(list(values), utc=True, format="ISO8601")
    return pd.DatetimeIndex(parsed)


# --------------------------------------------------------------------------- #
# series files
# --------------------------------------------------------------------------- #
def write_series_csv(
    frame: pd.DataFrame,
    path: str | Path,
    columns: Sequence[str] = FORECAST_COLUMNS,
    value_columns: Sequence[str] = VALUE_COLUMNS,
) -> Path:
    """Write ``frame`` as a contract-compliant time-series CSV.

    Parameters
    ----------
    frame : pandas.DataFrame
        Must contain ``timestamp`` plus every column in ``columns``. Extra
        columns are dropped.
    path : str | Path
        Destination, e.g. ``data/processed/sp1-demand-forecast-v1.csv``.
    columns : sequence of str
        Column order to write.
    value_columns : sequence of str
        Columns cast to float. ``NaN`` becomes an empty cell.

    Returns
    -------
    pathlib.Path
        The path written.
    """
    missing = [c for c in columns if c not in frame.columns]
    if missing:
        raise ContractError(f"cannot write {path}: missing columns {missing}")
    if frame.empty:
        raise ContractError(f"cannot write {path}: frame is empty")

    out = pd.DataFrame({"timestamp": [format_timestamp(t) for t in frame["timestamp"]]})
    for column in columns:
        if column == "timestamp":
            continue
        out[column] = pd.to_numeric(frame[column], errors="coerce").astype("float64")

    for column in value_columns:
        if column in out.columns and (out[column].dropna() < 0).any():
            raise ContractError(f"cannot write {path}: negative values in {column}")

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(path, index=False, encoding="utf-8", na_rep="", lineterminator="\n")
    return path


def read_series_csv(
    path: str | Path,
    required_value_columns: Sequence[str] = ("predicted_demand_kwh",),
) -> pd.DataFrame:
    """Read a contract time-series CSV and check its raw text is compliant.

    Parameters
    ----------
    path : str | Path
        File written by :func:`write_series_csv`.
    required_value_columns : sequence of str
        Columns that must exist and be non-empty.

    Returns
    -------
    pandas.DataFrame
        ``timestamp`` as UTC ``datetime64``, value columns as ``float64``.
    """
    path = Path(path)
    if not path.exists():
        raise ContractError(f"{path} does not exist")

    raw = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8")
    if "timestamp" not in raw.columns:
        raise ContractError(f"{path}: no 'timestamp' column")

    problems: list[str] = []
    for column in raw.columns:
        if column == "timestamp":
            continue
        for row_number, token in enumerate(raw[column], start=2):
            text = token.strip()
            if text == "":
                continue
            if text.lower() in FORBIDDEN_MISSING_TOKENS:
                problems.append(
                    f"{path}: line {row_number} column '{column}' uses the forbidden "
                    f"missing-value token {text!r}; missing values must be empty cells"
                )
                continue
            try:
                float(text)
            except ValueError:
                problems.append(
                    f"{path}: line {row_number} column '{column}' is not numeric: {text!r}"
                )
    if problems:
        raise ContractError("\n".join(problems[:20]))

    frame = pd.read_csv(path, keep_default_na=True, encoding="utf-8")
    frame["timestamp"] = parse_timestamps(frame["timestamp"])
    for column in raw.columns:
        if column != "timestamp":
            frame[column] = pd.to_numeric(frame[column], errors="coerce").astype("float64")
    return frame


def validate_series(
    frame: pd.DataFrame,
    required_value_columns: Sequence[str] = ("predicted_demand_kwh",),
    check_gap_free: bool = True,
    expected_columns: Sequence[str] | None = FORECAST_COLUMNS,
) -> list[str]:
    """Return the list of contract violations in ``frame`` (empty means valid).

    Checks: required columns, exact-hour timestamps, strictly increasing and
    unique timestamps, a gap-free 1-hour grid, non-negative values, and
    ``lower_bound_kwh <= predicted_demand_kwh <= upper_bound_kwh`` wherever the
    bounds are present. These are the guarantees SP2/SP4 are told they may rely on.

    Parameters
    ----------
    frame : pandas.DataFrame
        Frame as produced by :func:`read_series_csv` (timestamp as UTC datetime).
    required_value_columns : sequence of str
        Columns that must exist and be fully populated.
    check_gap_free : bool
        Require every consecutive pair of intervals to be exactly 1 hour apart.
    expected_columns : sequence of str | None
        When given, flags any column outside this set. Pass ``None`` to allow extras.

    Returns
    -------
    list of str
        Human-readable problem descriptions.
    """
    problems: list[str] = []
    if frame.empty:
        return ["frame is empty"]

    if expected_columns is not None:
        unexpected = [c for c in frame.columns if c not in expected_columns]
        if unexpected:
            problems.append(f"unexpected columns {unexpected}")

    for column in ("timestamp", *required_value_columns):
        if column not in frame.columns:
            problems.append(f"missing required column '{column}'")
    if problems:
        return problems

    timestamps = pd.DatetimeIndex(frame["timestamp"])
    if timestamps.tz is None:
        problems.append("timestamp column is timezone-naive; storage must be UTC")
    off_hour = [
        str(t) for t in timestamps if t.minute or t.second or t.microsecond
    ]
    if off_hour:
        problems.append(f"{len(off_hour)} timestamps are not on hour boundaries, e.g. {off_hour[0]}")
    if timestamps.has_duplicates:
        problems.append("timestamp column contains duplicate intervals")
    if not timestamps.is_monotonic_increasing:
        problems.append("timestamp column is not sorted ascending")

    if check_gap_free and len(timestamps) > 1 and not timestamps.has_duplicates:
        deltas = timestamps.to_series().diff().dropna()
        bad = deltas[deltas != pd.Timedelta(hours=1)]
        if not bad.empty:
            problems.append(
                f"{len(bad)} interval gaps are not exactly 1h, first at {bad.index[0]}"
            )

    for column in required_value_columns:
        values = pd.to_numeric(frame[column], errors="coerce")
        n_missing = int(values.isna().sum())
        if n_missing:
            problems.append(f"'{column}' has {n_missing} empty cells; it must be fully populated")
        if (values.dropna() < 0).any():
            problems.append(f"'{column}' contains negative values")

    bounds = [c for c in ("lower_bound_kwh", "upper_bound_kwh") if c in frame.columns]
    if len(bounds) == 2:
        lower = pd.to_numeric(frame["lower_bound_kwh"], errors="coerce")
        upper = pd.to_numeric(frame["upper_bound_kwh"], errors="coerce")
        predicted = pd.to_numeric(frame["predicted_demand_kwh"], errors="coerce")
        both = lower.notna() & upper.notna()
        if (lower[both] > upper[both]).any():
            problems.append("lower_bound_kwh exceeds upper_bound_kwh in some rows")
        if (lower[both] < 0).any() or (upper[both] < 0).any():
            problems.append("confidence bounds contain negative values")
        outside = both & ((predicted < lower) | (predicted > upper))
        if outside.any():
            problems.append(
                f"{int(outside.sum())} rows have predicted_demand_kwh outside its bounds"
            )
    return problems


def assert_valid_series(
    frame: pd.DataFrame,
    required_value_columns: Sequence[str] = ("predicted_demand_kwh",),
    check_gap_free: bool = True,
) -> None:
    """Raise :class:`ContractError` if ``frame`` violates the contract."""
    problems = validate_series(
        frame, required_value_columns=required_value_columns, check_gap_free=check_gap_free
    )
    if problems:
        raise ContractError("; ".join(problems))


# --------------------------------------------------------------------------- #
# meta files
# --------------------------------------------------------------------------- #
def meta_path(csv_path: str | Path) -> Path:
    """Return the sibling meta path for a CSV, e.g. ``x.csv`` -> ``x.meta.json``."""
    csv_path = Path(csv_path)
    return csv_path.with_suffix(META_SUFFIX)


def write_meta(
    csv_path: str | Path,
    source: str,
    units: Mapping[str, str],
    generated_by: str = GENERATED_BY,
    resolution: str = RESOLUTION,
    extra: Mapping[str, object] | None = None,
    generated_at: datetime | None = None,
) -> Path:
    """Write ``<csv_path without .csv>.meta.json``.

    Parameters
    ----------
    csv_path : str | Path
        The CSV this meta describes.
    source : str
        Human-readable provenance, e.g. ``"Science Data Bank <doi> (2023)"`` or
        ``"synthetic profile calibrated to China Charging Alliance 2024"``.
    units : mapping of str to str
        Unit per value column, e.g. ``{"predicted_demand_kwh": "kWh"}``.
    generated_by : str
        Sub-project id — ``"SP1"``.
    resolution : str
        ``"1h"``.
    extra : mapping | None
        Additional non-breaking keys, e.g. ``{"synthetic": True}``.
    generated_at : datetime | None
        Defaults to now (UTC).

    Returns
    -------
    pathlib.Path
        The meta file written.
    """
    generated_at = generated_at or datetime.now(timezone.utc)
    payload: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "generated_by": generated_by,
        "source": source,
        "resolution": resolution,
        "timezone": STORE_TZ,
        "units": dict(units),
    }
    if extra:
        payload.update(extra)

    path = meta_path(csv_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def read_meta(csv_path: str | Path) -> dict:
    """Read and lightly check the meta file belonging to ``csv_path``."""
    path = meta_path(csv_path)
    if not path.exists():
        raise ContractError(f"{path} does not exist; every output needs its .meta.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    for key in ("schema_version", "generated_at", "generated_by", "source", "resolution"):
        if key not in payload:
            raise ContractError(f"{path} is missing required key '{key}'")
    if payload["resolution"] != RESOLUTION:
        raise ContractError(f"{path}: resolution must be {RESOLUTION!r}")
    if not _ISO_Z.match(str(payload["generated_at"])):
        raise ContractError(f"{path}: generated_at must look like 2026-10-01T09:12:00Z")
    return payload
