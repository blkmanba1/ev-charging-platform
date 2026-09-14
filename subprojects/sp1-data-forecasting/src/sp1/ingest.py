"""Raw-dataset adapters: read whatever the dataset looks like, emit one schema.

A Chinese charging dataset may be published as session records or as an already
aggregated load series, in local time, with energy in kWh or Wh. Rather than
write one bespoke loader per dataset, every dataset is described by a
:class:`DatasetSpec` (see ``subprojects/sp1-data-forecasting/config/datasets.yaml``)
and read through one of two adapters:

``kind: sessions``
    Needs a start time plus an end time, a duration, or a power value, and an
    energy or a power value. Produces the canonical session table.
``kind: hourly_load``
    Needs a timestamp and an energy or a power value. Produces a 1-hour demand
    series directly.

The canonical session table has these columns:

======================  ======  ==============================================
column                  unit    meaning
======================  ======  ==============================================
``session_id``          —       opaque, unique within the dataset
``ev_id``               —       vehicle identifier when the dataset has one
``station_id``          —       station/charger identifier when available
``start_time_utc``      —       ISO-8601 UTC connection time
``end_time_utc``        —       ISO-8601 UTC disconnection time
``energy_kwh``          kWh     energy delivered
``power_kw``            kW      average power, derived when not published
``source``              —       dataset key, so mixed inputs stay traceable
======================  ======  ==============================================
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path

import pandas as pd
import yaml

from .contract import STORE_TZ, ContractError

CANONICAL_SESSION_COLUMNS: tuple[str, ...] = (
    "session_id",
    "ev_id",
    "station_id",
    "start_time_utc",
    "end_time_utc",
    "energy_kwh",
    "power_kw",
    "source",
)

SESSION_KINDS = ("sessions", "hourly_load")


@dataclass
class DatasetSpec:
    """Description of one raw dataset and how to read it.

    Attributes
    ----------
    key : str
        Short identifier used on the command line and in the meta ``source``.
    kind : str
        ``"sessions"`` or ``"hourly_load"``.
    path : pathlib.Path | None
        File under ``data/raw/`` (absolute after loading). ``None`` for the
        synthetic fallback.
    paths : list of pathlib.Path
        Several files that belong to one dataset (e.g. one CSV per city). They
        are concatenated, and each row's ``source`` records which file it came
        from.
    timezone : str
        Timezone the file's timestamps are written in; storage converts to UTC.
    column_map : dict
        Maps canonical names (``start``, ``end``, ``energy_kwh``, ...) to the
        dataset's own column names. ``end``/``energy_kwh`` may be omitted when a
        duration or power column makes them derivable.
    scales : dict
        Multiplier per canonical column, e.g. ``{"energy_kwh": 0.001}`` for Wh.
    default_power_kw : float | None
        Charger power assumed when a session has energy but no end time.
    description, licence, url : str
        Provenance, copied into the meta file and ``data/README.md``.
    """

    key: str
    kind: str
    path: Path | None = None
    paths: list[Path] = field(default_factory=list)
    timezone: str = "Asia/Shanghai"
    column_map: dict[str, str] = field(default_factory=dict)
    scales: dict[str, float] = field(default_factory=dict)
    default_power_kw: float | None = None
    description: str = ""
    licence: str = ""
    url: str = ""

    def __post_init__(self) -> None:
        if self.kind not in SESSION_KINDS:
            raise ContractError(f"{self.key}: kind must be one of {SESSION_KINDS}, got {self.kind!r}")
        # Accept plain strings so ad-hoc specs (scripts, notebooks, tests) behave
        # like specs loaded from YAML.
        if self.path is not None:
            self.path = Path(self.path)
        self.paths = [Path(path) for path in self.paths]


def load_dataset_specs(path: str | Path, raw_dir: str | Path | None = None) -> dict[str, DatasetSpec]:
    """Read ``datasets.yaml`` and return ``{key: DatasetSpec}``.

    Parameters
    ----------
    path : str | Path
        The YAML file, normally
        ``subprojects/sp1-data-forecasting/config/datasets.yaml``.
    raw_dir : str | Path | None
        Directory that relative dataset paths are resolved against. Defaults to
        the repository's ``data/raw`` (found by walking up from the YAML file).
    """
    path = Path(path)
    if not path.is_file():
        return {}
    raw_dir = Path(raw_dir) if raw_dir is not None else _infer_raw_dir(path)
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    entries = payload.get("datasets", {}) or {}
    specs: dict[str, DatasetSpec] = {}
    for key, entry in entries.items():
        entry = dict(entry or {})
        raw_path = entry.pop("path", None)
        raw_paths = entry.pop("paths", None) or []
        entry["path"] = _resolve_raw_path(raw_path, raw_dir)
        entry["paths"] = [p for p in (_resolve_raw_path(item, raw_dir) for item in raw_paths) if p]
        specs[key] = DatasetSpec(key=key, **entry)
    return specs


def _infer_raw_dir(config_path: Path) -> Path:
    """Find ``data/raw`` by walking up from ``datasets.yaml``."""
    for candidate in config_path.resolve().parents:
        if (candidate / "config.yaml").is_file() and (candidate / "data").is_dir():
            return candidate / "data" / "raw"
    raise ContractError(
        f"could not infer data/raw above {config_path}; pass raw_dir= explicitly"
    )


def _resolve_raw_path(value: str | None, raw_dir: Path) -> Path | None:
    """Resolve a path from ``datasets.yaml`` against ``data/raw``."""
    if not value:
        return None
    path = Path(value)
    return path if path.is_absolute() else raw_dir / path


def read_sessions_csv(spec: DatasetSpec) -> pd.DataFrame:
    """Read a session-level CSV dataset into the canonical session table.

    Parameters
    ----------
    spec : DatasetSpec
        Must have ``kind="sessions"`` and a readable ``path``.

    Returns
    -------
    pandas.DataFrame
        Canonical session columns; missing optional columns are ``None``.
        ``energy_kwh`` is non-negative and ``end_time_utc > start_time_utc``,
        except where a zero-length session has been padded to one minute by
        :func:`_derive_end`.

    Raises
    ------
    ContractError
        If a required mapping is missing or the derived values are invalid.
    """
    frame = _read_csv(spec)
    mapping = spec.column_map
    if "start" not in mapping:
        raise ContractError(f"{spec.key}: column_map needs a 'start' entry")

    start = _to_utc(_column(frame, mapping["start"], spec), spec.timezone)
    end = (
        _to_utc(_column(frame, mapping["end"], spec), spec.timezone)
        if mapping.get("end")
        else None
    )
    duration_min = _parse_duration_minutes(
        _column(frame, mapping["duration_min"], spec)
        if mapping.get("duration_min")
        else None,
        spec,
    )
    power = _scaled(frame, mapping.get("power_kw"), spec, "power_kw")
    energy = _scaled(frame, mapping.get("energy_kwh"), spec, "energy_kwh")

    if energy is None and power is not None:
        if duration_min is None and end is None:
            raise ContractError(
                f"{spec.key}: a power column needs either a duration or an end time "
                "to derive energy"
            )
        hours = (
            duration_min / 60.0
            if duration_min is not None
            else (end - start).dt.total_seconds() / 3600.0
        )
        energy = power * hours
    if energy is None:
        raise ContractError(f"{spec.key}: column_map needs 'energy_kwh' or 'power_kw'")
    if end is None:
        if duration_min is not None:
            end = start + pd.to_timedelta(duration_min, unit="m")
        elif power is not None:
            end = start + pd.to_timedelta(energy / power.where(power > 0), unit="h")
        elif spec.default_power_kw:
            end = start + pd.to_timedelta(
                (energy / spec.default_power_kw).clip(lower=1.0 / 60.0), unit="h"
            )
        else:
            raise ContractError(
                f"{spec.key}: column_map needs 'end', 'duration_min' or 'power_kw' "
                "to place the session in time"
            )
    end, energy = _derive_end(start, end, energy, spec)

    sessions = pd.DataFrame(
        {
            "session_id": _text_column(frame, mapping.get("session_id"), default_prefix=spec.key),
            "ev_id": _text_column(frame, mapping.get("ev_id"), default_prefix=None),
            "station_id": _text_column(frame, mapping.get("station_id"), default_prefix=None),
            "start_time_utc": start,
            "end_time_utc": end,
            "energy_kwh": energy.astype("float64"),
            "source": spec.key,
        }
    )
    sessions["power_kw"] = (
        sessions["energy_kwh"]
        / ((sessions["end_time_utc"] - sessions["start_time_utc"]).dt.total_seconds() / 3600.0)
    ).astype("float64")
    return sessions[list(CANONICAL_SESSION_COLUMNS)]


def read_hourly_load_csv(spec: DatasetSpec) -> pd.DataFrame:
    """Read an already-aggregated load series and put it on an hourly UTC grid.

    Parameters
    ----------
    spec : DatasetSpec
        Must have ``kind="hourly_load"`` and a ``timestamp`` entry in
        ``column_map``, plus ``energy_kwh`` or ``power_kw``.

    Returns
    -------
    pandas.DataFrame
        ``timestamp`` (UTC, hourly) and ``demand_kwh``.

    Raises
    ------
    ContractError
        If the source resolution is coarser than 1 hour — a daily or monthly
        total cannot be turned into an hourly profile without a disaggregation
        model, and inventing one silently would fake the data.
    """
    frame = _read_csv(spec)
    mapping = spec.column_map
    if "timestamp" not in mapping:
        raise ContractError(f"{spec.key}: column_map needs a 'timestamp' entry")
    timestamps = _to_utc(_column(frame, mapping["timestamp"], spec), spec.timezone)

    energy = _scaled(frame, mapping.get("energy_kwh"), spec, "energy_kwh")
    power = _scaled(frame, mapping.get("power_kw"), spec, "power_kw")
    if energy is None and power is None:
        raise ContractError(f"{spec.key}: column_map needs 'energy_kwh' or 'power_kw'")

    series = pd.DataFrame({"timestamp": timestamps})
    series["value"] = (energy if energy is not None else power).astype("float64")
    series = series.dropna(subset=["timestamp", "value"]).sort_values("timestamp")

    spacing = series["timestamp"].diff().dropna()
    if not spacing.empty:
        median_minutes = spacing.dt.total_seconds().median() / 60.0
        if median_minutes > 60:
            raise ContractError(
                f"{spec.key}: source resolution is {median_minutes:.0f} min, coarser than the "
                "1-hour contract. Sub-hourly data can be aggregated; daily or monthly totals "
                "need an explicit disaggregation model — do not fake an hourly profile."
            )

    hourly = (
        series.set_index("timestamp")["value"]
        .resample("1h")
        .agg("sum" if energy is not None else "mean")
        .dropna()
        .reset_index()
    )
    hourly = hourly.rename(columns={"value": "demand_kwh"})
    hourly["demand_kwh"] = hourly["demand_kwh"].clip(lower=0.0)
    return hourly


def load_dataset(spec: DatasetSpec) -> pd.DataFrame:
    """Dispatch to the adapter for ``spec.kind``.

    When ``spec.paths`` lists several files (one per city, say), they are read
    and concatenated, and each row's ``source`` records which file it came from.
    """
    if spec.paths:
        frames: list[pd.DataFrame] = []
        for path in spec.paths:
            frame = _load_single(replace(spec, path=path))
            frame["source"] = f"{spec.key}:{path.stem}"
            frames.append(frame)
        return pd.concat(frames, ignore_index=True)
    return _load_single(spec)


def _load_single(spec: DatasetSpec) -> pd.DataFrame:
    if spec.kind == "sessions":
        return read_sessions_csv(spec)
    if spec.kind == "hourly_load":
        return read_hourly_load_csv(spec)
    raise ContractError(f"{spec.key}: unsupported kind {spec.kind!r}")


def write_interim_table(frame: pd.DataFrame, path: str | Path) -> Path:
    """Write an interim table as UTF-8 CSV with ISO-8601 UTC timestamps."""
    out = frame.copy()
    for column in ("start_time_utc", "end_time_utc", "timestamp"):
        if column in out.columns:
            out[column] = [
                value.strftime("%Y-%m-%dT%H:%M:%SZ") if pd.notna(value) else ""
                for value in pd.DatetimeIndex(out[column])
            ]
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(path, index=False, encoding="utf-8", na_rep="", lineterminator="\n")
    return path


def read_interim_table(path: str | Path) -> pd.DataFrame:
    """Read a table written by :func:`write_interim_table`."""
    frame = pd.read_csv(Path(path), dtype=str, keep_default_na=False, encoding="utf-8")
    for column in ("start_time_utc", "end_time_utc", "timestamp"):
        if column in frame.columns:
            frame[column] = pd.to_datetime(frame[column], utc=True, format="ISO8601")
    for column in ("energy_kwh", "power_kw", "demand_kwh", "session_count"):
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _read_csv(spec: DatasetSpec) -> pd.DataFrame:
    if spec.path is None:
        raise ContractError(f"{spec.key}: no path configured (see datasets.yaml / data/raw)")
    if not spec.path.is_file():
        raise ContractError(
            f"{spec.key}: raw file not found at {spec.path}. Datasets are not committed — "
            "download it and record it in data/README.md."
        )
    # Chinese datasets are frequently distributed as GBK/GB18030, not UTF-8.
    # ``low_memory=False`` also silences the mixed-type DtypeWarning these
    # government exports trigger (their columns arrive as strings).
    last_error: Exception | None = None
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return pd.read_csv(spec.path, encoding=encoding, low_memory=False)
        except UnicodeDecodeError as error:
            last_error = error
    raise ContractError(f"{spec.key}: could not decode {spec.path.name}: {last_error}")


def _column(frame: pd.DataFrame, name: str, spec: DatasetSpec) -> pd.Series:
    if name not in frame.columns:
        raise ContractError(
            f"{spec.key}: column '{name}' is not in {spec.path.name}; "
            f"found {list(frame.columns)}"
        )
    return frame[name]


def _scaled(
    frame: pd.DataFrame, name: str | None, spec: DatasetSpec, canonical: str
) -> pd.Series | None:
    if not name:
        return None
    values = pd.to_numeric(_column(frame, name, spec), errors="coerce")
    return values * float(spec.scales.get(canonical, 1.0))


def _text_column(
    frame: pd.DataFrame, name: str | None, default_prefix: str | None
) -> pd.Series:
    if name and name in frame.columns:
        return frame[name].astype("string")
    if default_prefix is None:
        return pd.Series([None] * len(frame), dtype="string")
    return pd.Series([f"{default_prefix}-{i:07d}" for i in range(len(frame))], dtype="string")


def _parse_duration_minutes(
    values: pd.Series | None, spec: DatasetSpec
) -> pd.Series | None:
    """Parse a duration column into minutes.

    Accepts plain numbers (already minutes) and the ``hh:mm:ss`` / ``h:mm:ss``
    form that ChargePoint-style exports use. The distinction matters: several
    datasets publish both *occupancy* and *charging* duration, and spreading a
    session's energy over occupancy would flatten the load profile badly.

    Parameters
    ----------
    values : pandas.Series | None
        Raw column, or ``None`` when the mapping has no duration entry.
    spec : DatasetSpec
        Used for error messages and ``scales``.

    Returns
    -------
    pandas.Series | None
        Minutes as floats, or ``None`` when there is nothing to parse.
    """
    if values is None:
        return None
    text = values.astype("string").str.strip()
    numeric = pd.to_numeric(text, errors="coerce")
    clock = text.str.extract(r"^(?:(?P<h>\d+):)?(?P<m>\d{1,2}):(?P<s>\d{1,2})$")
    clock_minutes = (
        pd.to_numeric(clock["h"], errors="coerce").fillna(0) * 60
        + pd.to_numeric(clock["m"], errors="coerce")
        + pd.to_numeric(clock["s"], errors="coerce") / 60.0
    )
    minutes = numeric.where(numeric.notna(), clock_minutes)
    unparsed = minutes.isna() & text.notna() & (text != "")
    if unparsed.any():
        examples = text[unparsed].head(3).tolist()
        raise ContractError(
            f"{spec.key}: could not parse {int(unparsed.sum())} durations, e.g. {examples}"
        )
    return minutes * float(spec.scales.get("duration_min", 1.0))


def _to_utc(values: pd.Series, timezone: str) -> pd.Series:
    """Parse timestamps, interpret naive values in ``timezone``, return UTC.

    Accepts strict ISO-8601 (``2026-09-26T10:00:00Z``) and the space-separated
    form Chinese exports commonly use (``2026-09-26 18:00:00``).
    """
    parsed = pd.to_datetime(values, errors="coerce", format="ISO8601")
    if parsed.isna().any():
        fallback = pd.to_datetime(values, errors="coerce", format="mixed")
        parsed = parsed.fillna(fallback)
    if parsed.isna().all():
        raise ContractError(
            f"no timestamp in column could be parsed; first values: {list(values[:3])}"
        )
    if getattr(parsed.dt, "tz", None) is None:
        parsed = parsed.dt.tz_localize(timezone, ambiguous="NaT", nonexistent="NaT")
    return parsed.dt.tz_convert(STORE_TZ)


def _derive_end(
    start: pd.Series, end: pd.Series, energy: pd.Series, spec: DatasetSpec
) -> tuple[pd.Series, pd.Series]:
    """Repair sessions whose end time is missing or not after the start.

    Uses ``default_power_kw`` when configured; otherwise the session is treated
    as instantaneous and padded by one minute, so its energy still lands in the
    hour it started. Every repair is reported by the caller through the row count.
    """
    bad = end.isna() | (end <= start)
    if not bad.any():
        return end, energy
    if spec.default_power_kw:
        hours = (energy[bad] / spec.default_power_kw).clip(lower=1 / 60.0)
        end = end.copy()
        end.loc[bad] = start[bad] + pd.to_timedelta(hours, unit="h")
        return end, energy
    end = end.copy()
    end.loc[bad] = start[bad] + pd.Timedelta(minutes=1)
    return end, energy


def dataset_looks_empty(sessions: pd.DataFrame) -> bool:
    """True when a session table carries no usable energy."""
    return sessions.empty or float(sessions["energy_kwh"].fillna(0).sum()) <= 0.0
