"""Shared fixtures.

Scenarios here are small. Published figures come from the experiments, not from the suite,
so a test only has to exercise a path and assert a property. A test that re-runs the
headline simulation buys nothing and costs minutes on every push.
"""

from __future__ import annotations

import pytest

from ratio_readout.config import ScenarioConfig
from ratio_readout.generate import generate


@pytest.fixture
def small_config() -> ScenarioConfig:
    return ScenarioConfig(
        n_users=400,
        mean_events=5.0,
        icc=0.2,
        bootstrap_resamples=100,
        seed=11,
    )


@pytest.fixture
def independent_config() -> ScenarioConfig:
    """The degenerate case: no between-user variance, so events really are independent."""
    return ScenarioConfig(
        n_users=400,
        mean_events=5.0,
        icc=0.0,
        bootstrap_resamples=100,
        seed=11,
    )


@pytest.fixture
def small_experiment(small_config):
    return generate(small_config)
