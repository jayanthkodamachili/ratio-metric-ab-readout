"""The sample ratio mismatch gate, and an honest account of what it does not catch.

An SRM check compares the realised split of users against the intended one. A significant
mismatch means the assignment mechanism is broken, and when assignment is broken no
downstream estimate is worth reading, however carefully its variance was computed. So this
runs first and can stop the readout entirely.

Its limits are the interesting part, and they are stated in the README rather than buried:
this tests the count of users in each arm and nothing else. An assignment that splits users
evenly while correlating with the metric, a redirect that silently drops a slow-loading
cohort, passes this check untouched.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import stats

from ratio_readout.generate import CONTROL, TREATMENT, Experiment

DEFAULT_SRM_ALPHA = 0.001


@dataclass(frozen=True)
class SrmResult:
    """The outcome of the gate."""

    control_users: int
    treatment_users: int
    expected_treatment_share: float
    observed_treatment_share: float
    chi_square: float
    p_value: float
    alpha: float

    @property
    def mismatched(self) -> bool:
        return self.p_value < self.alpha

    def as_dict(self) -> dict:
        return {
            "control_users": self.control_users,
            "treatment_users": self.treatment_users,
            "expected_treatment_share": round(self.expected_treatment_share, 6),
            "observed_treatment_share": round(self.observed_treatment_share, 6),
            "chi_square": round(self.chi_square, 6),
            "p_value": round(self.p_value, 8),
            "mismatched": self.mismatched,
        }


def check_srm(
    experiment: Experiment,
    expected_treatment_share: float,
    alpha: float = DEFAULT_SRM_ALPHA,
) -> SrmResult:
    """One degree of freedom chi-square on the realised user split.

    Alpha defaults to 0.001 rather than 0.05 on purpose. This gate runs on every readout,
    so at 0.05 it would halt one healthy experiment in twenty, and a gate that cries wolf
    that often is a gate people route around.
    """
    control_users = int(np.sum(experiment.assignment == CONTROL))
    treatment_users = int(np.sum(experiment.assignment == TREATMENT))
    total = control_users + treatment_users
    if total == 0:
        raise ValueError("cannot check the sample ratio of an experiment with no users")

    expected_treatment = total * expected_treatment_share
    expected_control = total * (1.0 - expected_treatment_share)

    chi_square = float(
        (treatment_users - expected_treatment) ** 2 / expected_treatment
        + (control_users - expected_control) ** 2 / expected_control
    )
    p_value = float(stats.chi2.sf(chi_square, df=1))

    return SrmResult(
        control_users=control_users,
        treatment_users=treatment_users,
        expected_treatment_share=expected_treatment_share,
        observed_treatment_share=treatment_users / total,
        chi_square=chi_square,
        p_value=p_value,
        alpha=alpha,
    )
