from __future__ import annotations

import numpy as np
import pytest

from ratio_readout.config import ScenarioConfig
from ratio_readout.generate import (
    CONTROL,
    TREATMENT,
    Experiment,
    generate,
    observed_icc,
)


def test_generated_experiment_has_one_row_per_user(small_config):
    experiment = generate(small_config)
    assert experiment.n_users == small_config.n_users
    assert experiment.denominator.size == small_config.n_users


def test_generation_is_reproducible_from_the_seed(small_config):
    first = generate(small_config)
    second = generate(small_config)
    np.testing.assert_array_equal(first.numerator, second.numerator)
    np.testing.assert_array_equal(first.assignment, second.assignment)


def test_a_different_seed_produces_different_data(small_config):
    other = ScenarioConfig(**{**small_config.as_dict(), "seed": small_config.seed + 1})
    assert not np.array_equal(generate(small_config).numerator, generate(other).numerator)


def test_every_user_contributes_at_least_one_event(small_config):
    assert generate(small_config).denominator.min() >= 1


def test_no_user_has_more_successes_than_events(small_config):
    experiment = generate(small_config)
    assert np.all(experiment.numerator <= experiment.denominator)


def test_an_inconsistent_experiment_is_rejected_at_construction():
    with pytest.raises(ValueError, match="more successes than events"):
        Experiment(
            assignment=np.array([0, 1]),
            denominator=np.array([2, 2]),
            numerator=np.array([3, 1]),
        )


def test_mismatched_array_lengths_are_rejected():
    with pytest.raises(ValueError, match="same length"):
        Experiment(
            assignment=np.array([0, 1]),
            denominator=np.array([2]),
            numerator=np.array([1]),
        )


def test_mean_events_lands_near_the_requested_value(small_config):
    experiment = generate(small_config)
    observed = experiment.n_events / experiment.n_users
    assert abs(observed - small_config.mean_events) < 0.5


def test_treatment_share_lands_near_the_requested_value(small_config):
    experiment = generate(small_config)
    share = float(np.mean(experiment.assignment == TREATMENT))
    assert abs(share - small_config.treatment_share) < 0.08


def test_control_ratio_lands_near_the_base_rate(small_config):
    experiment = generate(small_config)
    assert abs(experiment.ratio(CONTROL) - small_config.base_rate) < 0.04


def test_a_positive_lift_raises_the_treatment_ratio():
    """Checked across seeds, because one draw can run the wrong way by chance."""
    lifted = []
    for seed in range(8):
        config = ScenarioConfig(
            n_users=3000, mean_events=5.0, icc=0.1, lift=0.5,
            bootstrap_resamples=100, seed=seed,
        )
        experiment = generate(config)
        lifted.append(experiment.ratio(TREATMENT) > experiment.ratio(CONTROL))
    assert sum(lifted) >= 7


def test_zero_icc_gives_every_user_in_an_arm_the_same_propensity(independent_config):
    """The limiting case the whole argument rests on, asserted rather than described.

    With no between-user variance the observed correlation should sit at the floor, which
    is what makes the naive estimator correct in this configuration.
    """
    assert observed_icc(generate(independent_config)) < 0.02


def test_observed_icc_tracks_the_configured_value():
    config = ScenarioConfig(n_users=5000, mean_events=8.0, icc=0.25, seed=3)
    assert abs(observed_icc(generate(config)) - 0.25) < 0.06


def test_observed_icc_is_clipped_at_zero_rather_than_reported_negative():
    """The estimator can go slightly negative on a finite sample with no real clustering.

    A negative intra-class correlation here would be an artefact of the arithmetic, not a
    finding, so it is clipped and the clipping is tested rather than assumed.
    """
    config = ScenarioConfig(n_users=60, mean_events=2.0, icc=0.0, seed=5)
    assert observed_icc(generate(config)) >= 0.0


def test_observed_icc_of_a_degenerate_single_user_experiment_is_zero():
    experiment = Experiment(
        assignment=np.array([0]), denominator=np.array([4]), numerator=np.array([2])
    )
    assert observed_icc(experiment) == 0.0


def test_observed_icc_is_zero_when_every_user_brings_exactly_one_event():
    """With one event per user there is no within-user variation to partition.

    Both mean squares collapse to zero and the ratio is undefined, so the function has to
    answer rather than divide. This is a real configuration: one event per user is what a
    signup funnel looks like.
    """
    experiment = Experiment(
        assignment=np.array([0, 0, 1, 1]),
        denominator=np.array([1, 1, 1, 1]),
        numerator=np.array([1, 1, 1, 1]),
    )
    assert observed_icc(experiment) == 0.0


def test_a_single_event_per_user_scenario_runs_end_to_end():
    """The design effect is one here, so every estimator should agree."""
    config = ScenarioConfig(n_users=800, mean_events=1.0, icc=0.3, bootstrap_resamples=100, seed=2)
    experiment = generate(config)
    assert experiment.n_events == experiment.n_users
    assert observed_icc(experiment) >= 0.0


def test_ratio_weights_users_by_their_event_count():
    """A ratio metric is not the mean of per-user rates, and the difference is the point."""
    experiment = Experiment(
        assignment=np.array([0, 0]),
        denominator=np.array([1, 99]),
        numerator=np.array([1, 0]),
    )
    assert experiment.ratio(CONTROL) == pytest.approx(1 / 100)
    mean_of_user_rates = np.mean([1 / 1, 0 / 99])
    assert experiment.ratio(CONTROL) != pytest.approx(mean_of_user_rates)


def test_ratio_of_an_empty_arm_is_refused():
    experiment = Experiment(
        assignment=np.array([0, 0]), denominator=np.array([2, 2]), numerator=np.array([1, 1])
    )
    with pytest.raises(ValueError, match="no events"):
        experiment.ratio(TREATMENT)


def test_arm_returns_only_that_arms_users(small_experiment):
    denominator, numerator = small_experiment.arm(TREATMENT)
    assert denominator.size == int(np.sum(small_experiment.assignment == TREATMENT))
    assert numerator.size == denominator.size
