"""Contract compliance: the guarantees SP2 and SP4 are told they can rely on."""

from __future__ import annotations

import json

import pandas as pd
import pytest
from sp1.contract import (
    FORECAST_COLUMNS,
    ContractError,
    format_timestamp,
    meta_path,
    parse_timestamps,
    read_meta,
    read_series_csv,
    validate_series,
    write_meta,
    write_series_csv,
)


def _series(n: int = 6, start: str = "2026-09-26T00:00:00Z") -> pd.DataFrame:
    timestamps = pd.date_range(start, periods=n, freq="1h", tz="UTC")
    values = pd.Series(range(1, n + 1), dtype="float64")
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "predicted_demand_kwh": values,
            "lower_bound_kwh": values - 0.5,
            "upper_bound_kwh": values + 0.5,
        }
    )


def test_format_timestamp_is_iso_utc_without_microseconds():
    assert format_timestamp("2026-09-26T14:00:00Z") == "2026-09-26T14:00:00Z"
    # A naive timestamp is interpreted as UTC (storage is always UTC).
    assert format_timestamp(pd.Timestamp("2026-09-26 14:00")) == "2026-09-26T14:00:00Z"
    # Local time is converted, not relabelled.
    assert (
        format_timestamp(pd.Timestamp("2026-09-26 22:00", tz="Asia/Shanghai"))
        == "2026-09-26T14:00:00Z"
    )


def test_format_timestamp_rejects_off_hour_values():
    with pytest.raises(ContractError):
        format_timestamp("2026-09-26T14:30:00Z")


def test_write_then_read_round_trip(tmp_path):
    path = tmp_path / "sp1-demand-forecast-v1.csv"
    write_series_csv(_series(), path)
    frame = read_series_csv(path)
    assert list(frame.columns) == list(FORECAST_COLUMNS)
    assert frame["timestamp"].dt.tz is not None
    assert not validate_series(frame)


def test_missing_values_are_written_as_empty_cells(tmp_path):
    frame = _series()
    frame.loc[2, ["lower_bound_kwh", "upper_bound_kwh"]] = float("nan")
    path = tmp_path / "bounds.csv"
    write_series_csv(frame, path)
    text = path.read_text(encoding="utf-8")
    assert "NaN" not in text and "nan" not in text
    assert ",," in text  # empty cells, not placeholders
    reread = read_series_csv(path)
    assert reread["lower_bound_kwh"].isna().sum() == 1


def test_reader_rejects_placeholder_tokens(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text(
        "timestamp,predicted_demand_kwh,lower_bound_kwh,upper_bound_kwh\n"
        "2026-09-26T00:00:00Z,N/A,,\n",
        encoding="utf-8",
    )
    with pytest.raises(ContractError, match="forbidden missing-value token"):
        read_series_csv(path)


def test_reader_rejects_non_numeric_cells(tmp_path):
    path = tmp_path / "bad2.csv"
    path.write_text(
        "timestamp,predicted_demand_kwh,lower_bound_kwh,upper_bound_kwh\n"
        "2026-09-26T00:00:00Z,unknown,,\n",
        encoding="utf-8",
    )
    with pytest.raises(ContractError, match="not numeric"):
        read_series_csv(path)


def test_write_rejects_negative_values(tmp_path):
    frame = _series()
    frame.loc[1, "predicted_demand_kwh"] = -1.0
    with pytest.raises(ContractError, match="negative"):
        write_series_csv(frame, tmp_path / "neg.csv")


def test_validate_detects_gaps_duplicates_and_order():
    frame = _series()
    gapped = frame.drop(index=2).reset_index(drop=True)
    assert any("gaps" in problem for problem in validate_series(gapped))

    duplicated = pd.concat([frame, frame.iloc[[1]]], ignore_index=True)
    problems = validate_series(duplicated)
    assert any("duplicate" in problem for problem in problems)

    shuffled = frame.iloc[[1, 0, 2, 3, 4, 5]].reset_index(drop=True)
    assert any("sorted" in problem for problem in validate_series(shuffled))


def test_validate_detects_off_hour_and_naive_timestamps():
    frame = _series()
    frame["timestamp"] = frame["timestamp"].dt.tz_localize(None)
    assert any("timezone-naive" in problem for problem in validate_series(frame))

    frame = _series()
    frame.loc[0, "timestamp"] = frame.loc[0, "timestamp"] + pd.Timedelta(minutes=30)
    assert any("hour boundaries" in problem for problem in validate_series(frame))


def test_validate_detects_bounds_violations():
    frame = _series()
    frame.loc[0, "lower_bound_kwh"] = frame.loc[0, "predicted_demand_kwh"] + 1
    assert any("outside its bounds" in problem for problem in validate_series(frame))

    frame = _series()
    frame.loc[0, "lower_bound_kwh"] = frame.loc[0, "upper_bound_kwh"] + 1
    assert any("lower_bound_kwh exceeds" in problem for problem in validate_series(frame))


def test_validate_requires_a_fully_populated_forecast():
    frame = _series()
    frame.loc[0, "predicted_demand_kwh"] = float("nan")
    assert any("empty cells" in problem for problem in validate_series(frame))


def test_meta_file_name_and_contents(tmp_path):
    csv_path = tmp_path / "sp1-demand-forecast-v1.csv"
    write_series_csv(_series(), csv_path)
    write_meta(csv_path, source="unit test", units={"predicted_demand_kwh": "kWh"})

    assert meta_path(csv_path).name == "sp1-demand-forecast-v1.meta.json"
    meta = read_meta(csv_path)
    assert meta["generated_by"] == "SP1"
    assert meta["resolution"] == "1h"
    assert meta["timezone"] == "UTC"
    assert meta["generated_at"].endswith("Z")
    assert meta["units"]["predicted_demand_kwh"] == "kWh"


def test_meta_rejects_missing_keys(tmp_path):
    csv_path = tmp_path / "x.csv"
    write_series_csv(_series(), csv_path)
    meta_path(csv_path).write_text(json.dumps({"schema_version": "1.0"}), encoding="utf-8")
    with pytest.raises(ContractError, match="missing required key"):
        read_meta(csv_path)


def test_parse_timestamps_is_utc():
    parsed = parse_timestamps(["2026-09-26T00:00:00Z", "2026-09-26T01:00:00Z"])
    assert str(parsed.tz) == "UTC"
    assert (parsed[1] - parsed[0]) == pd.Timedelta(hours=1)
