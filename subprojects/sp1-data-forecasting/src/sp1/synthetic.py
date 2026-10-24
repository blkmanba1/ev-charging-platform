"""Calibrated synthetic charging sessions — an explicit, labelled fallback.

This module exists for two reasons: the test suite needs deterministic input,
and if no session-level Chinese dataset can be obtained, the project needs a
documented fallback rather than a stall. **Anything produced here is synthetic**
and every output that uses it says so in its meta file (``synthetic: true``) and
in its ``source`` string, because presenting it as measured data would be
research misconduct.

Calibration assumptions (all openly stated so they can be challenged and
replaced by published Chinese statistics when we have them):

* Private passenger EVs in China drive roughly 12,000–15,000 km/year
  (China Charging Alliance / industry reporting), i.e. ~35 km/day, and consume
  ~15 kWh/100 km — about **5 kWh/day per vehicle** on average once vehicle
  efficiency and non-charging days are accounted for. The generator targets
  that daily mean so the aggregate scale is defensible.
* Charging is split between **home evening** (plug-in 17:00–22:00 local, the
  evening peak the project is about) and **workplace daytime** (08:00–17:00,
  weekdays only). Roughly 60% of sessions are home, 40% workplace.
* Session energy is log-normal: home ~22 kWh mean, workplace ~14 kWh mean.
* AC charging at 7 kW; a small share of sessions use 60 kW DC fast charging.
* Weekends shift sessions later and add afternoon charging.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .contract import STORE_TZ
from .ingest import CANONICAL_SESSION_COLUMNS

LOCAL_TZ = "Asia/Shanghai"


@dataclass(frozen=True)
class SyntheticSettings:
    """Knobs for :func:`generate_sessions`; defaults are the calibration above.

    Attributes
    ----------
    n_evs : int
        Number of vehicles simulated.
    days : int
        Number of local days to simulate.
    start_date : str
        First local day (ISO date). A Monday keeps the weekday pattern clean.
    home_share : float
        Share of sessions that are home evening sessions.
    weekday_charge_probability : float
        Probability that a given vehicle charges on a given day.
    home_energy_mean_kwh, home_energy_sigma : float
        Log-normal parameters for home session energy.
    work_energy_mean_kwh, work_energy_sigma : float
        Log-normal parameters for workplace session energy.
    ac_power_kw : float
        AC charger power.
    dc_power_kw : float
        DC fast-charger power.
    dc_share : float
        Share of sessions served by a DC charger.
    target_daily_kwh_per_ev : float
        Aggregate calibration target, in kWh per vehicle per day.
    """

    n_evs: int = 200
    days: int = 120
    start_date: str = "2025-01-06"
    home_share: float = 0.6
    weekday_charge_probability: float = 0.20
    home_energy_mean_kwh: float = 22.0
    home_energy_sigma: float = 0.45
    work_energy_mean_kwh: float = 14.0
    work_energy_sigma: float = 0.40
    ac_power_kw: float = 7.0
    dc_power_kw: float = 60.0
    dc_share: float = 0.08
    target_daily_kwh_per_ev: float = 5.0


def generate_sessions(
    settings: SyntheticSettings | None = None,
    seed: int | None = 42,
) -> pd.DataFrame:
    """Generate synthetic sessions in the canonical session schema.

    Parameters
    ----------
    settings : SyntheticSettings | None
        Defaults to :class:`SyntheticSettings`.
    seed : int | None
        Seed for reproducibility; ``None`` gives a fresh draw each run.

    Returns
    -------
    pandas.DataFrame
        Canonical session columns (see :mod:`sp1.ingest`) with UTC timestamps.
        The calendar covers ``settings.days`` local days from
        ``settings.start_date``, so it is gap-free once aggregated.
    """
    settings = settings or SyntheticSettings()
    rng = np.random.default_rng(seed)

    days = pd.date_range(settings.start_date, periods=settings.days, freq="D")
    ev_ids = [f"SYN-EV-{i:04d}" for i in range(settings.n_evs)]
    records: list[dict[str, object]] = []
    counter = 0

    for day in days:
        is_weekend = day.dayofweek >= 5
        # Seasonal factor: winter and summer consumption is higher than shoulder
        # months (cabin heating/cooling), peaking in January and July.
        month = day.month
        seasonal = 1.0 + 0.18 * np.cos(2 * np.pi * (month - 1) / 12.0)
        probability = settings.weekday_charge_probability * (1.35 if is_weekend else 1.0)
        charging = rng.random(settings.n_evs) < probability

        for index in np.flatnonzero(charging):
            is_home = rng.random() < settings.home_share
            if is_home:
                mean = settings.home_energy_mean_kwh
                sigma = settings.home_energy_sigma
                if is_weekend:
                    hour = float(rng.choice([12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22],
                                            p=[0.03, 0.04, 0.05, 0.06, 0.07, 0.10,
                                               0.16, 0.18, 0.14, 0.10, 0.07]))
                else:
                    hour = float(rng.choice([17, 18, 19, 20, 21, 22, 23],
                                            p=[0.16, 0.26, 0.24, 0.16, 0.10, 0.05, 0.03]))
            else:
                if is_weekend:
                    continue  # workplace charging is a weekday activity
                mean = settings.work_energy_mean_kwh
                sigma = settings.work_energy_sigma
                hour = float(rng.choice([8, 9, 10, 11, 12, 13], p=[0.3, 0.28, 0.16, 0.1, 0.1, 0.06]))

            energy = float(np.clip(rng.lognormal(np.log(mean), sigma), 1.0, 90.0)) * seasonal
            power = settings.dc_power_kw if rng.random() < settings.dc_share else settings.ac_power_kw
            duration_hours = max(energy / power, 1.0 / 60.0)

            start_local = day + pd.Timedelta(hours=hour, minutes=int(rng.integers(0, 60)))
            counter += 1
            records.append(
                {
                    "session_id": f"SYN-{counter:08d}",
                    "ev_id": ev_ids[index],
                    "station_id": "SYN-HOME" if is_home else "SYN-WORK",
                    "start_time_utc": start_local.tz_localize(
                        LOCAL_TZ, ambiguous="NaT", nonexistent="NaT"
                    ).tz_convert(STORE_TZ),
                    "end_time_utc": (
                        start_local + pd.Timedelta(hours=duration_hours)
                    ).tz_localize(LOCAL_TZ, ambiguous="NaT", nonexistent="NaT").tz_convert(STORE_TZ),
                    "energy_kwh": round(energy, 4),
                    "power_kw": round(energy / duration_hours, 4),
                    "source": "synthetic",
                }
            )

    sessions = pd.DataFrame.from_records(records, columns=list(CANONICAL_SESSION_COLUMNS))
    return sessions.dropna(subset=["start_time_utc"]).reset_index(drop=True)


def calibration_report(sessions: pd.DataFrame, settings: SyntheticSettings | None = None) -> dict:
    """Summarise what the generator actually produced, for the meta file.

    Returns
    -------
    dict
        Session count, total and mean daily energy, mean energy per vehicle per
        day (the calibration target), mean session energy and the gap to the
        target, so a reader can see how close the simulation landed.
    """
    settings = settings or SyntheticSettings()
    if sessions.empty:
        return {"n_sessions": 0, "mean_daily_kwh_per_ev": 0.0}

    local_start = pd.DatetimeIndex(sessions["start_time_utc"]).tz_convert(LOCAL_TZ)
    days = local_start.normalize().nunique()
    total = float(sessions["energy_kwh"].sum())
    per_ev_day = total / (settings.n_evs * days) if days else 0.0
    return {
        "n_sessions": len(sessions),
        "n_days": int(days),
        "total_energy_kwh": round(total, 2),
        "mean_session_energy_kwh": round(float(sessions["energy_kwh"].mean()), 3),
        "mean_daily_kwh_per_ev": round(per_ev_day, 3),
        "target_daily_kwh_per_ev": settings.target_daily_kwh_per_ev,
        "target_gap_ratio": round(per_ev_day / settings.target_daily_kwh_per_ev, 3),
    }
