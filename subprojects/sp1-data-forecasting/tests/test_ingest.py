"""Raw-dataset adapters: column mapping, timezones, units and encodings."""

from __future__ import annotations

import pandas as pd
import pytest
from sp1.contract import ContractError
from sp1.ingest import (
    DatasetSpec,
    load_dataset,
    load_dataset_specs,
    read_hourly_load_csv,
    read_sessions_csv,
)


def _csv(tmp_path, text: str, name: str = "raw.csv", encoding: str = "utf-8"):
    path = tmp_path / name
    path.write_text(text, encoding=encoding)
    return path


def test_sessions_are_converted_to_utc_and_scaled(tmp_path):
    path = _csv(
        tmp_path,
        "开始时间,结束时间,电量(Wh),车辆\n"
        "2026-09-26 18:00:00,2026-09-26 21:00:00,21000,京A12345\n",
    )
    spec = DatasetSpec(
        key="demo",
        kind="sessions",
        path=path,
        timezone="Asia/Shanghai",
        column_map={"start": "开始时间", "end": "结束时间", "energy_kwh": "电量(Wh)", "ev_id": "车辆"},
        scales={"energy_kwh": 0.001},
    )
    sessions = read_sessions_csv(spec)
    row = sessions.iloc[0]
    assert str(row["start_time_utc"]) == "2026-09-26 10:00:00+00:00"  # 18:00 CST == 10:00 UTC
    assert row["energy_kwh"] == pytest.approx(21.0)
    assert row["power_kw"] == pytest.approx(7.0)
    assert row["ev_id"] == "京A12345"
    assert row["source"] == "demo"


def test_energy_is_derived_from_power_and_duration(tmp_path):
    path = _csv(
        tmp_path,
        "start,end,kw,minutes\n2026-09-26T10:00:00Z,2026-09-26T12:00:00Z,7,120\n",
    )
    spec = DatasetSpec(
        key="demo",
        kind="sessions",
        path=path,
        column_map={"start": "start", "end": "end", "power_kw": "kw", "duration_min": "minutes"},
    )
    sessions = read_sessions_csv(spec)
    assert sessions["energy_kwh"].iloc[0] == pytest.approx(14.0)


def test_end_is_derived_from_duration_when_absent(tmp_path):
    path = _csv(tmp_path, "start,kwh,minutes\n2026-09-26T10:00:00Z,10,150\n")
    spec = DatasetSpec(
        key="demo",
        kind="sessions",
        path=path,
        column_map={"start": "start", "energy_kwh": "kwh", "duration_min": "minutes"},
    )
    sessions = read_sessions_csv(spec)
    assert (sessions["end_time_utc"] - sessions["start_time_utc"]).iloc[0] == pd.Timedelta(hours=2.5)


def test_default_power_fills_a_missing_end_time(tmp_path):
    path = _csv(tmp_path, "start,kwh\n2026-09-26T10:00:00Z,14\n")
    spec = DatasetSpec(
        key="demo",
        kind="sessions",
        path=path,
        column_map={"start": "start", "energy_kwh": "kwh"},
        default_power_kw=7.0,
    )
    sessions = read_sessions_csv(spec)
    assert (sessions["end_time_utc"] - sessions["start_time_utc"]).iloc[0] == pd.Timedelta(hours=2)


def test_missing_mapping_is_reported_clearly(tmp_path):
    path = _csv(tmp_path, "start,kwh\n2026-09-26T10:00:00Z,14\n")
    spec = DatasetSpec(key="demo", kind="sessions", path=path, column_map={"start": "start"})
    with pytest.raises(ContractError, match="energy_kwh"):
        read_sessions_csv(spec)


def test_unknown_column_lists_what_is_available(tmp_path):
    path = _csv(tmp_path, "start,kwh\n2026-09-26T10:00:00Z,14\n")
    spec = DatasetSpec(
        key="demo",
        kind="sessions",
        path=path,
        column_map={"start": "created_at", "energy_kwh": "kwh"},
    )
    with pytest.raises(ContractError, match="created_at"):
        read_sessions_csv(spec)


def test_missing_file_says_datasets_are_not_committed(tmp_path):
    spec = DatasetSpec(
        key="demo",
        kind="sessions",
        path=tmp_path / "absent.csv",
        column_map={"start": "start", "energy_kwh": "kwh"},
    )
    with pytest.raises(ContractError, match="not committed"):
        read_sessions_csv(spec)


def test_gbk_encoded_file_is_read(tmp_path):
    path = _csv(
        tmp_path,
        "开始时间,电量\n2026-09-26 18:00:00,20\n",
        encoding="gb18030",
    )
    spec = DatasetSpec(
        key="demo",
        kind="sessions",
        path=path,
        timezone="Asia/Shanghai",
        column_map={"start": "开始时间", "energy_kwh": "电量"},
        default_power_kw=7.0,
    )
    sessions = read_sessions_csv(spec)
    assert sessions["energy_kwh"].iloc[0] == pytest.approx(20.0)
    assert str(sessions["start_time_utc"].iloc[0]) == "2026-09-26 10:00:00+00:00"


def test_sub_hourly_load_is_averaged_into_hours(tmp_path):
    path = _csv(
        tmp_path,
        "ts,kw\n2026-09-26T10:00:00Z,4\n2026-09-26T10:15:00Z,4\n"
        "2026-09-26T10:30:00Z,4\n2026-09-26T10:45:00Z,4\n"
        "2026-09-26T11:00:00Z,2\n2026-09-26T11:15:00Z,2\n"
        "2026-09-26T11:30:00Z,2\n2026-09-26T11:45:00Z,2\n",
    )
    spec = DatasetSpec(
        key="demo",
        kind="hourly_load",
        path=path,
        column_map={"timestamp": "ts", "power_kw": "kw"},
    )
    series = read_hourly_load_csv(spec)
    assert series["demand_kwh"].tolist() == pytest.approx([4.0, 2.0])


def test_coarse_resolution_is_refused_rather_than_faked(tmp_path):
    path = _csv(tmp_path, "ts,kwh\n2026-09-26,120\n2026-09-27,140\n")
    spec = DatasetSpec(
        key="demo",
        kind="hourly_load",
        path=path,
        column_map={"timestamp": "ts", "energy_kwh": "kwh"},
    )
    with pytest.raises(ContractError, match="coarser than the 1-hour contract"):
        read_hourly_load_csv(spec)


def test_dataset_specs_are_resolved_against_data_raw(tmp_path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    yaml_path = config_dir / "datasets.yaml"
    yaml_path.write_text(
        "datasets:\n"
        "  demo:\n"
        "    kind: sessions\n"
        "    path: demo/sessions.csv\n"
        "    timezone: Asia/Shanghai\n"
        "    column_map:\n"
        "      start: start\n"
        "      energy_kwh: kwh\n",
        encoding="utf-8",
    )
    specs = load_dataset_specs(yaml_path, raw_dir=tmp_path / "raw")
    assert specs["demo"].path == tmp_path / "raw" / "demo" / "sessions.csv"
    assert specs["demo"].column_map["energy_kwh"] == "kwh"


def test_dataset_specs_reject_a_yaml_outside_a_repository(tmp_path):
    yaml_path = tmp_path / "datasets.yaml"
    yaml_path.write_text("datasets:\n  demo:\n    kind: sessions\n    path: x.csv\n", encoding="utf-8")
    with pytest.raises(ContractError, match="pass raw_dir"):
        load_dataset_specs(yaml_path)


def test_multiple_paths_are_read_and_labelled(tmp_path):
    first = _csv(tmp_path, "start,kwh\n2026-09-26T10:00:00Z,10\n", name="a.csv")
    second = _csv(tmp_path, "start,kwh\n2026-09-26T11:00:00Z,20\n", name="b.csv")
    spec = DatasetSpec(
        key="multi",
        kind="sessions",
        paths=[first, second],
        column_map={"start": "start", "energy_kwh": "kwh"},
        default_power_kw=7.0,
    )
    sessions = load_dataset(spec)
    assert len(sessions) == 2
    assert sorted(sessions["source"]) == ["multi:a", "multi:b"]
    assert sessions["energy_kwh"].sum() == pytest.approx(30.0)


def test_paths_given_as_strings_are_coerced(tmp_path):
    path = _csv(tmp_path, "start,kwh\n2026-09-26T10:00:00Z,10\n")
    spec = DatasetSpec(
        key="demo",
        kind="sessions",
        path=str(path),
        paths=[str(path)],
        column_map={"start": "start", "energy_kwh": "kwh"},
        default_power_kw=7.0,
    )
    assert spec.path == path and spec.paths == [path]
    assert len(read_sessions_csv(spec)) == 1


def test_duration_in_clock_format_is_parsed(tmp_path):
    """ChargePoint-style exports give durations as hh:mm:ss, not minutes."""
    path = _csv(
        tmp_path,
        "start,energy,hhmmss\n"
        "2026-09-26T10:00:00Z,10,1:30:00\n"
        "2026-09-26T12:00:00Z,5,0:45:30\n",
    )
    spec = DatasetSpec(
        key="demo",
        kind="sessions",
        path=path,
        column_map={"start": "start", "energy_kwh": "energy", "duration_min": "hhmmss"},
    )
    sessions = read_sessions_csv(spec)
    first = sessions["end_time_utc"].iloc[0] - sessions["start_time_utc"].iloc[0]
    second = (sessions["end_time_utc"].iloc[1] - sessions["start_time_utc"].iloc[1]).total_seconds()
    assert first == pd.Timedelta(hours=1, minutes=30)
    assert second == pytest.approx(45 * 60 + 30)


def test_unparsable_duration_is_reported(tmp_path):
    path = _csv(tmp_path, "start,energy,hhmmss\n2026-09-26T10:00:00Z,10,about an hour\n")
    spec = DatasetSpec(
        key="demo",
        kind="sessions",
        path=path,
        column_map={"start": "start", "energy_kwh": "energy", "duration_min": "hhmmss"},
    )
    with pytest.raises(ContractError, match="could not parse"):
        read_sessions_csv(spec)


def test_empty_specs_file_returns_nothing(tmp_path):
    assert load_dataset_specs(tmp_path / "missing.yaml") == {}
