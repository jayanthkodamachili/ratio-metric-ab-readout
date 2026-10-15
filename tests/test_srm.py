from __future__ import annotations

import numpy as np
import pytest

from ratio_readout.generate import Experiment
from ratio_readout.srm import DEFAULT_SRM_ALPHA, check_srm


def _balanced(n_control: int, n_treatment: int) -> Experiment:
    assignment = np.array([0] * n_control + [1] * n_treatment)
    return Experiment(
        assignment=assignment,
        denominator=np.full(assignment.size, 4),
        numerator=np.full(assignment.size, 1),
    )


def test_an_even_split_passes_the_gate():
    assert check_srm(_balanced(1000, 1000), 0.5).mismatched is False


def test_a_badly_skewed_split_is_caught():
    assert check_srm(_balanced(1000, 600), 0.5).mismatched is True


def test_a_split_matching_an_uneven_intended_share_passes():
    """A 90/10 design is not a mismatch, it is a design."""
    assert check_srm(_balanced(9000, 1000), 0.1).mismatched is False


def test_the_same_split_fails_when_an_even_one_was_intended():
    assert check_srm(_balanced(9000, 1000), 0.5).mismatched is True


def test_the_gate_defaults_to_a_strict_alpha():
    """At 0.05 this gate would halt one healthy experiment in twenty.

    A gate that cries wolf that often is a gate people route around, so the default is
    0.001 and the choice is tested rather than left as a constant nobody reads.
    """
    assert DEFAULT_SRM_ALPHA == 0.001
    assert check_srm(_balanced(1000, 1000), 0.5).alpha == 0.001


def test_a_tiny_imbalance_passes_at_the_strict_alpha_and_fails_at_a_loose_one():
    experiment = _balanced(1000, 1080)
    assert check_srm(experiment, 0.5, alpha=0.001).mismatched is False
    assert check_srm(experiment, 0.5, alpha=0.2).mismatched is True


def test_chi_square_is_zero_for_a_perfect_split():
    assert check_srm(_balanced(500, 500), 0.5).chi_square == pytest.approx(0.0)


def test_chi_square_grows_with_the_imbalance():
    mild = check_srm(_balanced(1000, 950), 0.5).chi_square
    severe = check_srm(_balanced(1000, 700), 0.5).chi_square
    assert severe > mild


def test_observed_share_is_reported_alongside_the_expected_one():
    result = check_srm(_balanced(750, 250), 0.5)
    assert result.observed_treatment_share == pytest.approx(0.25)
    assert result.expected_treatment_share == pytest.approx(0.5)


def test_an_experiment_with_no_users_is_refused():
    empty = Experiment(
        assignment=np.array([], dtype=int),
        denominator=np.array([], dtype=int),
        numerator=np.array([], dtype=int),
    )
    with pytest.raises(ValueError, match="no users"):
        check_srm(empty, 0.5)


def test_as_dict_carries_the_verdict_not_just_the_statistic():
    payload = check_srm(_balanced(1000, 600), 0.5).as_dict()
    assert payload["mismatched"] is True
    assert "chi_square" in payload and "p_value" in payload
