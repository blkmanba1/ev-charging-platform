"""Session -> hourly demand aggregation: energy must be conserved, not lost."""

from __future__ import annotations

import pandas as pd
import pytest
from sp1.contract import ContractError
from sp1.hourly import (
    build_hourly_demand,
    build_uncontrolled_profile,
    complete_grid,
    profile,
    to_local,
)


def _session(start: str, end: str, energy: float) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "start_time_utc": [pd.Timestamp(start, tz="UTC")],
            "end_time_utc": [pd.Timestamp(end, tz="UTC")],
            "energy_kwh": [energy],
        }
    )


def test_energy_is_conserved_across_hourly_bins(sessions):
    demand = build_hourly_demand(sessions)
    assert demand["demand_kwh"].sum() == pytest.approx(sessions["energy_kwh"].sum(), rel=1e-9)


def test_session_spanning_two_hours_is_split_by_overlap():
    # 00:45 -> 01:45 is one hour of charging, a quarter of it in the first hour.
    demand = build_hourly_demand(_session("2026-09-26T00:45:00Z", "2026-09-26T01:45:00Z", 6.0))
    by_hour = demand.set_index("timestamp")["demand_kwh"]
    assert by_hour.loc[pd.Timestamp("2026-09-26T00:00:00Z")] == pytest.approx(1.5)
    assert by_hour.loc[pd.Timestamp("2026-09-26T01:00:00Z")] == pytest.approx(4.5)


def test_whole_hour_session_lands_in_one_bin():
    demand = build_hourly_demand(_session("2026-09-26T00:00:00Z", "2026-09-26T01:00:00Z", 7.0))
    assert len(demand) == 1
    assert demand["demand_kwh"].iloc[0] == pytest.approx(7.0)
    assert demand["session_count"].iloc[0] == 1


def test_zero_length_session_keeps_its_energy():
    """A session with no duration must not silently vanish from the totals."""
    demand = build_hourly_demand(_session("2026-09-26T05:20:00Z", "2026-09-26T05:20:00Z", 3.0))
    assert demand["demand_kwh"].sum() == pytest.approx(3.0)
    assert demand["timestamp"].iloc[0] == pd.Timestamp("2026-09-26T05:00:00Z")


def test_multiple_sessions_in_one_hour_are_summed():
    frame = pd.concat(
        [
            _session("2026-09-26T00:00:00Z", "2026-09-26T01:00:00Z", 5.0),
            _session("2026-09-26T00:10:00Z", "2026-09-26T01:00:00Z", 5.0),
        ],
        ignore_index=True,
    )
    demand = build_hourly_demand(frame)
    assert demand["demand_kwh"].iloc[0] == pytest.approx(10.0)
    assert demand["session_count"].iloc[0] == 2


def test_complete_grid_fills_absent_intervals_with_zero():
    sparse = build_hourly_demand(
        pd.concat(
            [
                _session("2026-09-26T00:00:00Z", "2026-09-26T01:00:00Z", 4.0),
                _session("2026-09-26T05:00:00Z", "2026-09-26T06:00:00Z", 2.0),
            ],
            ignore_index=True,
        )
    )
    grid = complete_grid(sparse)
    assert len(grid) == 6
    assert grid["demand_kwh"].tolist() == [4.0, 0.0, 0.0, 0.0, 0.0, 2.0]
    assert grid["timestamp"].diff().dropna().eq(pd.Timedelta(hours=1)).all()


def test_complete_grid_extends_to_the_requested_bounds():
    sparse = build_hourly_demand(_session("2026-09-26T02:00:00Z", "2026-09-26T03:00:00Z", 1.0))
    grid = complete_grid(
        sparse,
        start=pd.Timestamp("2026-09-26T00:00:00Z"),
        end=pd.Timestamp("2026-09-26T04:00:00Z"),
    )
    assert len(grid) == 5
    assert grid["demand_kwh"].sum() == pytest.approx(1.0)


def test_complete_grid_rejects_naive_bounds():
    sparse = build_hourly_demand(_session("2026-09-26T02:00:00Z", "2026-09-26T03:00:00Z", 1.0))
    with pytest.raises(ContractError, match="timezone-aware"):
        complete_grid(sparse, start=pd.Timestamp("2026-09-26T00:00:00"), end=None)


def test_negative_energy_is_rejected():
    with pytest.raises(ContractError, match="negative"):
        build_hourly_demand(_session("2026-09-26T00:00:00Z", "2026-09-26T01:00:00Z", -1.0))


def test_missing_end_column_is_rejected():
    frame = pd.DataFrame(
        {
            "start_time_utc": [pd.Timestamp("2026-09-26T00:00:00Z")],
            "energy_kwh": [1.0],
        }
    )
    with pytest.raises(ContractError, match="missing columns"):
        build_hourly_demand(frame)


def test_uncontrolled_profile_moves_energy_to_the_local_evening():
    frame = pd.concat(
        [
            _session("2026-09-26T01:00:00Z", "2026-09-26T02:00:00Z", 14.0),  # 09:00 local
            _session("2026-09-26T03:00:00Z", "2026-09-26T04:00:00Z", 14.0),  # 11:00 local
        ],
        ignore_index=True,
    )
    baseline = build_uncontrolled_profile(frame, plug_in_hour_local=18, max_power_kw=7.0)
    assert baseline["demand_kwh"].sum() == pytest.approx(28.0)
    local_hours = to_local(baseline["timestamp"]).hour.unique().tolist()
    assert 18 in local_hours
    assert baseline["demand_kwh"].max() == pytest.approx(14.0)  # 2 vehicles x 7 kW in one hour


def test_uncontrolled_profile_uses_the_session_power_when_available():
    """A 150 kW session must not be stretched over 40 hours by a 7 kW default."""
    frame = pd.DataFrame(
        {
            "start_time_utc": [pd.Timestamp("2026-09-26T01:00:00Z")],
            "end_time_utc": [pd.Timestamp("2026-09-26T03:00:00Z")],
            "energy_kwh": [300.0],
            "power_kw": [150.0],
        }
    )
    baseline = build_uncontrolled_profile(frame, plug_in_hour_local=18, max_power_kw=7.0)
    assert baseline["demand_kwh"].sum() == pytest.approx(300.0)
    assert len(baseline) == 2  # two hours at 150 kW, not 43 hours at 7 kW


def test_profile_shares_sum_to_one(sessions):
    demand = complete_grid(build_hourly_demand(sessions))
    summary = profile(demand)
    assert len(summary) == 24
    assert summary["share_of_energy"].sum() == pytest.approx(1.0)
    assert (summary["total_kwh"] >= 0).all()
