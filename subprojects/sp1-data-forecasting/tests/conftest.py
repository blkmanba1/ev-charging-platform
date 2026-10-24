"""Shared test fixtures.

Puts ``src/`` on ``sys.path`` so the tests run from a clean checkout without
installing the package (matching ``CONTRIBUTING.md``).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


@pytest.fixture(scope="session")
def sessions() -> pd.DataFrame:
    """Sixteen days of synthetic sessions — small, deterministic, fast.

    Long enough that the 168-hour lag/rolling warm-up still leaves several
    forecast origins behind it.
    """
    from sp1.synthetic import SyntheticSettings, generate_sessions

    return generate_sessions(
        SyntheticSettings(n_evs=60, days=16, start_date="2025-01-06"), seed=7
    )


@pytest.fixture(scope="session")
def demand_frame(sessions: pd.DataFrame) -> pd.DataFrame:
    """Gap-free hourly demand built from :func:`sessions`."""
    from sp1.hourly import build_hourly_demand, complete_grid

    return complete_grid(build_hourly_demand(sessions))


@pytest.fixture(scope="session")
def feature_frame(demand_frame: pd.DataFrame) -> pd.DataFrame:
    """Feature frame (calendar + lags + naive columns) for the demand series."""
    from sp1.pipeline import build_feature_frame

    return build_feature_frame(demand_frame, local_tz="Asia/Shanghai")
