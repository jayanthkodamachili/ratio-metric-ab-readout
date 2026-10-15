"""Three ways to put a standard error on the same observed difference.

Read the three functions together. Every one computes the identical point estimate, because
the point estimate is not in dispute: the treated ratio minus the control ratio is a fact
about the data. They disagree only about how uncertain that number is, and that disagreement
is the entire subject of this repository.

The naive estimator is not a strawman. It is what a two-sample proportion test does when
pointed at a per-event table, which is the shape most event logs arrive in, and it is
correct whenever the events really are independent.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import stats

from ratio_readout.generate import CONTROL, TREATMENT, Experiment


@dataclass(frozen=True)
class Estimate:
    """One estimator's verdict on one experiment."""

    method: str
    effect: float
    standard_error: float
    z_score: float
    p_value: float
    unit: str

    def significant_at(self, alpha: float) -> bool:
        return self.p_value < alpha

    def as_dict(self) -> dict:
        return {
            "method": self.method,
            "effect": round(self.effect, 8),
            "standard_error": round(self.standard_error, 8),
            "z_score": round(self.z_score, 6),
            "p_value": round(self.p_value, 8),
            "unit": self.unit,
        }


def _two_sided(effect: float, standard_error: float) -> tuple[float, float]:
    """Return (z, p). A zero standard error means the data cannot separate the arms."""
    if standard_error <= 0.0 or not np.isfinite(standard_error):
        return 0.0, 1.0
    z = effect / standard_error
    return float(z), float(2.0 * stats.norm.sf(abs(z)))


def observed_effect(experiment: Experiment) -> float:
    return experiment.ratio(TREATMENT) - experiment.ratio(CONTROL)


def naive_event(experiment: Experiment) -> Estimate:
    """Treat every event as its own independent observation.

    This is the mistake, and it is worth being precise about why it is one. Pooling a user's
    events into a flat table does not destroy the correlation between them, it only hides
    it. The resulting standard error counts each event as a full unit of information when a
    user contributing eight correlated events has supplied rather less than eight events'
    worth. The arithmetic below is exactly right for the data it thinks it has.
    """
    rates, variances = [], []
    for arm in (CONTROL, TREATMENT):
        denominator, numerator = experiment.arm(arm)
        events = float(denominator.sum())
        successes = float(numerator.sum())
        rate = successes / events
        rates.append(rate)
        variances.append(rate * (1.0 - rate) / events)

    effect = rates[1] - rates[0]
    standard_error = float(np.sqrt(variances[0] + variances[1]))
    z, p = _two_sided(effect, standard_error)
    return Estimate("naive_event", effect, standard_error, z, p, unit="event")


def _delta_variance(denominator: np.ndarray, numerator: np.ndarray) -> float:
    """Variance of a ratio of means, with the user as the unit.

    For R = mean(Y) / mean(X), the first order expansion gives
    Var(R) = (Var(Y) - 2R Cov(X, Y) + R^2 Var(X)) / (n * mean(X)^2).
    Every term is computed across users, which is what makes this correct under user level
    randomisation regardless of how many events each user brought.
    """
    x = denominator.astype(float)
    y = numerator.astype(float)
    n = x.size
    if n < 2:
        return float("inf")
    x_bar = x.mean()
    ratio = y.mean() / x_bar
    var_x = x.var(ddof=1)
    var_y = y.var(ddof=1)
    cov_xy = float(np.cov(x, y, ddof=1)[0, 1])
    return float((var_y - 2.0 * ratio * cov_xy + ratio * ratio * var_x) / (n * x_bar * x_bar))


def delta_method(experiment: Experiment) -> Estimate:
    """Put the variance on the user, where the randomisation happened.

    The default recommendation of this repository, for a reason that is about cost rather
    than correctness: it agrees with the bootstrap closely enough to be indistinguishable
    in practice while being a closed form that runs in microseconds.
    """
    variance = sum(_delta_variance(*experiment.arm(arm)) for arm in (CONTROL, TREATMENT))
    effect = observed_effect(experiment)
    standard_error = float(np.sqrt(variance))
    z, p = _two_sided(effect, standard_error)
    return Estimate("delta_method", effect, standard_error, z, p, unit="user")


def cluster_bootstrap(experiment: Experiment, resamples: int, seed: int) -> Estimate:
    """Resample users with replacement, never events.

    Serves as the oracle. It assumes almost nothing about the shape of the metric, so where
    it agrees with the delta method the closed form can be trusted, and where it disagrees
    the closed form is the one to doubt.

    The loop is deliberate. A vectorised version that draws all resamples as one index
    matrix was written, measured, and discarded: it wins at small user counts and loses by
    roughly half at the sizes that matter, because the index matrix stops fitting in cache.
    ADR-003 carries the measurements.
    """
    rng = np.random.default_rng(seed)
    index = {arm: np.flatnonzero(experiment.assignment == arm) for arm in (CONTROL, TREATMENT)}

    differences = np.empty(resamples, dtype=float)
    for draw in range(resamples):
        arm_ratios = []
        for arm in (CONTROL, TREATMENT):
            take = rng.choice(index[arm], size=index[arm].size, replace=True)
            arm_ratios.append(
                experiment.numerator[take].sum() / experiment.denominator[take].sum()
            )
        differences[draw] = arm_ratios[1] - arm_ratios[0]

    effect = observed_effect(experiment)
    standard_error = float(differences.std(ddof=1))
    z, p = _two_sided(effect, standard_error)
    return Estimate("cluster_bootstrap", effect, standard_error, z, p, unit="user")
