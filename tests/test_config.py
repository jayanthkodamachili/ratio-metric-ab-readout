"""Every test name states the property the configuration must hold."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from ratio_readout.config import ConfigError, ScenarioConfig


def test_default_config_is_constructible():
    assert ScenarioConfig().n_users == 4000


def test_config_is_frozen_so_an_estimator_cannot_mutate_the_shared_scenario():
    config = ScenarioConfig()
    with pytest.raises(FrozenInstanceError):
        config.seed = 1  # type: ignore[misc]


def test_too_few_users_is_rejected():
    with pytest.raises(ConfigError, match="n_users"):
        ScenarioConfig(n_users=4)


def test_mean_events_below_one_is_rejected():
    with pytest.raises(ConfigError, match="mean_events"):
        ScenarioConfig(mean_events=0.5)


@pytest.mark.parametrize("icc", [-0.1, 1.0, 1.5])
def test_icc_outside_the_unit_interval_is_rejected(icc):
    with pytest.raises(ConfigError, match="icc"):
        ScenarioConfig(icc=icc)


def test_icc_of_exactly_zero_is_allowed_because_it_is_the_interesting_limit():
    assert ScenarioConfig(icc=0.0).icc == 0.0


@pytest.mark.parametrize("rate", [0.0, 1.0, -0.2, 1.3])
def test_base_rate_outside_the_open_unit_interval_is_rejected(rate):
    with pytest.raises(ConfigError, match="base_rate"):
        ScenarioConfig(base_rate=rate)


@pytest.mark.parametrize("share", [0.0, 1.0, -0.1])
def test_treatment_share_outside_the_open_unit_interval_is_rejected(share):
    with pytest.raises(ConfigError, match="treatment_share"):
        ScenarioConfig(treatment_share=share)


@pytest.mark.parametrize("alpha", [0.0, 1.0, 2.0])
def test_alpha_outside_the_open_unit_interval_is_rejected(alpha):
    with pytest.raises(ConfigError, match="alpha"):
        ScenarioConfig(alpha=alpha)


def test_too_few_bootstrap_resamples_is_rejected():
    with pytest.raises(ConfigError, match="bootstrap_resamples"):
        ScenarioConfig(bootstrap_resamples=10)


def test_a_lift_that_pushes_the_treated_rate_past_one_is_rejected():
    """This guard exists because of a real failure during the build.

    An early power sweep ran lifts up to 15 at a base rate of 0.1. The treated rate became
    1.6, the beta shape parameter went negative, numpy returned nan without raising, and
    the p-value came back nan. The sweep completed and wrote nan into its JSON. Validation
    at construction turns that into a refusal where the scenario is described.
    """
    with pytest.raises(ConfigError, match="not a probability"):
        ScenarioConfig(base_rate=0.5, lift=1.5)


def test_a_lift_that_drives_the_treated_rate_to_zero_is_rejected():
    with pytest.raises(ConfigError, match="not a probability"):
        ScenarioConfig(base_rate=0.1, lift=-1.0)


def test_design_effect_is_one_when_events_do_not_cluster():
    assert ScenarioConfig(icc=0.0).design_effect == pytest.approx(1.0)


def test_design_effect_is_one_when_every_user_brings_a_single_event():
    assert ScenarioConfig(mean_events=1.0, icc=0.5).design_effect == pytest.approx(1.0)


def test_design_effect_grows_with_both_cluster_size_and_correlation():
    base = ScenarioConfig(mean_events=5.0, icc=0.1).design_effect
    bigger_clusters = ScenarioConfig(mean_events=10.0, icc=0.1).design_effect
    stronger_correlation = ScenarioConfig(mean_events=5.0, icc=0.3).design_effect
    assert bigger_clusters > base
    assert stronger_correlation > base


def test_design_effect_matches_the_closed_form():
    config = ScenarioConfig(mean_events=9.0, icc=0.25)
    assert config.design_effect == pytest.approx(1.0 + 8.0 * 0.25)


def test_as_dict_round_trips_into_an_equal_config():
    config = ScenarioConfig(icc=0.3, seed=99)
    assert ScenarioConfig(**config.as_dict()) == config
