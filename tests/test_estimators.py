from __future__ import annotations

from dataclasses import FrozenInstanceError

import numpy as np
import pytest

from ratio_readout.config import ScenarioConfig
from ratio_readout.estimators import (
    Estimate,
    _delta_variance,
    _two_sided,
    cluster_bootstrap,
    delta_method,
    naive_event,
    observed_effect,
)
from ratio_readout.generate import CONTROL, TREATMENT, Experiment, generate

ESTIMATOR_FUNCS = (naive_event, delta_method)


@pytest.mark.parametrize("estimator", ESTIMATOR_FUNCS)
def test_every_estimator_reports_the_same_point_estimate(estimator, small_experiment):
    """The effect is a fact about the data. Only its uncertainty is in dispute."""
    assert estimator(small_experiment).effect == pytest.approx(
        observed_effect(small_experiment)
    )


def test_the_bootstrap_reports_the_same_point_estimate_too(small_experiment, small_config):
    estimate = cluster_bootstrap(small_experiment, small_config.bootstrap_resamples, 3)
    assert estimate.effect == pytest.approx(observed_effect(small_experiment))


def test_clustered_standard_error_exceeds_the_naive_one_when_events_cluster(small_experiment):
    assert delta_method(small_experiment).standard_error > naive_event(
        small_experiment
    ).standard_error


def test_the_two_standard_errors_agree_when_events_do_not_cluster(independent_config):
    """The limiting case. With no clustering the naive estimator is simply correct.

    This is what makes the repository an explanation rather than a demonstration: the
    naive standard error is not wrong in general, it is wrong under a condition, and the
    condition can be switched off.
    """
    experiment = generate(independent_config)
    naive = naive_event(experiment).standard_error
    clustered = delta_method(experiment).standard_error
    assert clustered / naive == pytest.approx(1.0, abs=0.12)


def test_the_delta_method_tracks_the_bootstrap(small_experiment):
    """The closed form is only usable if it agrees with the method that assumes less."""
    delta = delta_method(small_experiment).standard_error
    boot = cluster_bootstrap(small_experiment, 400, seed=5).standard_error
    assert delta == pytest.approx(boot, rel=0.15)


def test_the_bootstrap_is_reproducible_from_its_seed(small_experiment):
    first = cluster_bootstrap(small_experiment, 200, seed=9).standard_error
    second = cluster_bootstrap(small_experiment, 200, seed=9).standard_error
    assert first == second


def test_a_different_bootstrap_seed_moves_the_estimate_a_little(small_experiment):
    first = cluster_bootstrap(small_experiment, 200, seed=1).standard_error
    second = cluster_bootstrap(small_experiment, 200, seed=2).standard_error
    assert first != second
    assert first == pytest.approx(second, rel=0.3)


@pytest.mark.parametrize("estimator", ESTIMATOR_FUNCS)
def test_every_p_value_is_a_probability(estimator, small_experiment):
    assert 0.0 <= estimator(small_experiment).p_value <= 1.0


def test_an_identical_pair_of_arms_produces_a_p_value_near_one():
    experiment = Experiment(
        assignment=np.array([0, 0, 0, 0, 1, 1, 1, 1]),
        denominator=np.array([10, 10, 10, 10, 10, 10, 10, 10]),
        numerator=np.array([3, 3, 3, 3, 3, 3, 3, 3]),
    )
    assert naive_event(experiment).p_value == pytest.approx(1.0)


def test_a_zero_standard_error_yields_a_p_value_of_one_rather_than_a_division_error():
    """Arms that are identical to the last event give a degenerate variance.

    Returning 1.0 is the honest answer: data with no spread cannot distinguish the arms.
    Raising here would turn a legitimate if unusual dataset into a crash.
    """
    z, p = _two_sided(effect=0.0, standard_error=0.0)
    assert (z, p) == (0.0, 1.0)


def test_a_non_finite_standard_error_is_also_handled():
    assert _two_sided(effect=1.0, standard_error=float("nan"))[1] == 1.0


def test_delta_variance_of_a_single_user_is_infinite_rather_than_a_crash():
    """One user carries no information about between-user variance."""
    variance = _delta_variance(np.array([5]), np.array([2]))
    assert np.isinf(variance)


def test_delta_variance_falls_as_users_are_added():
    rng = np.random.default_rng(4)
    small = _delta_variance(rng.integers(1, 10, 50), rng.integers(0, 2, 50))
    rng = np.random.default_rng(4)
    large_x = rng.integers(1, 10, 5000)
    large_y = rng.integers(0, 2, 5000)
    assert _delta_variance(large_x, large_y) < small


def test_a_larger_effect_produces_a_smaller_p_value():
    def p_for(lift: float) -> float:
        config = ScenarioConfig(
            n_users=3000, mean_events=6.0, icc=0.1, lift=lift,
            bootstrap_resamples=100, seed=21,
        )
        return delta_method(generate(config)).p_value

    assert p_for(0.5) < p_for(0.05)


def test_the_naive_estimator_is_labelled_with_the_event_as_its_unit(small_experiment):
    """The unit is published because it is the whole disagreement, in one word."""
    assert naive_event(small_experiment).unit == "event"
    assert delta_method(small_experiment).unit == "user"


def test_significance_is_decided_against_the_supplied_alpha():
    estimate = Estimate("x", effect=1.0, standard_error=1.0, z_score=1.0, p_value=0.04, unit="user")
    assert estimate.significant_at(0.05) is True
    assert estimate.significant_at(0.01) is False


def test_estimates_are_frozen_so_a_report_cannot_edit_a_measurement(small_experiment):
    estimate = naive_event(small_experiment)
    with pytest.raises(FrozenInstanceError):
        estimate.p_value = 0.0  # type: ignore[misc]


def test_estimate_as_dict_carries_every_published_field(small_experiment):
    payload = delta_method(small_experiment).as_dict()
    assert set(payload) == {
        "method", "effect", "standard_error", "z_score", "p_value", "unit"
    }


def test_observed_effect_is_treatment_minus_control(small_experiment):
    assert observed_effect(small_experiment) == pytest.approx(
        small_experiment.ratio(TREATMENT) - small_experiment.ratio(CONTROL)
    )
