"""A seeded beta-binomial generator, because the truth has to be known.

The quantity this repository measures is a false positive rate: how often a test calls an
effect that is not there. Measuring that requires data where the absence of an effect is a
fact rather than an estimate, which no real experiment log can provide. So the generator
draws from a distribution whose null is exact by construction.

The model is deliberately the simplest one that produces the problem. Each user carries a
propensity drawn from a beta distribution, and their events are Bernoulli draws at that
propensity. Events within a user therefore resemble each other, and the strength of that
resemblance is a single parameter. Set it to zero and every user has the same propensity,
the events become independent, and the naive test becomes correct. That limiting case is
what makes the mechanism legible rather than merely demonstrated.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ratio_readout.config import ScenarioConfig

CONTROL = 0
TREATMENT = 1


@dataclass(frozen=True)
class Experiment:
    """User level data. One row per randomisation unit, never one row per event.

    Attributes:
        assignment: arm per user, 0 control and 1 treatment.
        denominator: events contributed by the user.
        numerator: successes among those events.
    """

    assignment: np.ndarray
    denominator: np.ndarray
    numerator: np.ndarray

    def __post_init__(self) -> None:
        sizes = {self.assignment.size, self.denominator.size, self.numerator.size}
        if len(sizes) != 1:
            raise ValueError("assignment, denominator and numerator must be the same length")
        if np.any(self.numerator > self.denominator):
            raise ValueError("a user cannot have more successes than events")

    @property
    def n_users(self) -> int:
        return int(self.assignment.size)

    @property
    def n_events(self) -> int:
        return int(self.denominator.sum())

    def arm(self, which: int) -> tuple[np.ndarray, np.ndarray]:
        """Return (denominator, numerator) for one arm, at user level."""
        sel = self.assignment == which
        return self.denominator[sel], self.numerator[sel]

    def ratio(self, which: int) -> float:
        """The arm's ratio metric: total successes over total events.

        Note what this is not. It is not the mean of per-user rates. A ratio metric weights
        users by how many events they contribute, which is usually what a business means by
        "conversion rate", and it is why the variance needs the delta method rather than a
        plain standard error of a mean.
        """
        denominator, numerator = self.arm(which)
        total = denominator.sum()
        if total == 0:
            raise ValueError(f"arm {which} has no events, its ratio is undefined")
        return float(numerator.sum() / total)


def generate(config: ScenarioConfig) -> Experiment:
    """Draw one experiment from the configured distribution."""
    rng = np.random.default_rng(config.seed)

    assignment = (rng.random(config.n_users) < config.treatment_share).astype(np.int64)

    # Events per user: Poisson shifted so the minimum is one. A user with no events
    # contributes nothing to a ratio metric but still consumes a randomisation slot, which
    # is a separate problem this repository does not model.
    denominator = 1 + rng.poisson(config.mean_events - 1.0, size=config.n_users)

    rate = np.where(
        assignment == TREATMENT,
        config.base_rate * (1.0 + config.lift),
        config.base_rate,
    )

    if config.icc == 0.0:
        # The degenerate case: no between-user variance, so every user shares the arm's
        # rate and the events really are independent.
        propensity = rate
    else:
        concentration = 1.0 / config.icc - 1.0
        propensity = rng.beta(rate * concentration, (1.0 - rate) * concentration)

    numerator = rng.binomial(denominator, propensity)
    return Experiment(assignment=assignment, denominator=denominator, numerator=numerator)


def observed_icc(experiment: Experiment) -> float:
    """Estimate the intra-class correlation actually realised in a draw.

    Published next to the configured value so a reader can see that the knob does what it
    claims. Uses the standard analysis-of-variance estimator for binary data grouped by
    user, clipped at zero because the estimator can go slightly negative on a finite sample
    with no real clustering, and a negative correlation here would be an artefact rather
    than a finding.
    """
    denominator = experiment.denominator.astype(float)
    numerator = experiment.numerator.astype(float)
    total_events = denominator.sum()
    grand = numerator.sum() / total_events

    between = float(np.sum(denominator * (numerator / denominator - grand) ** 2))
    within = float(np.sum(numerator * (1 - numerator / denominator) ** 2
                          + (denominator - numerator) * (numerator / denominator) ** 2))

    n_users = experiment.n_users
    if n_users < 2 or within + between == 0:
        return 0.0

    mean_cluster = total_events / n_users
    ms_between = between / (n_users - 1)
    ms_within = within / (total_events - n_users) if total_events > n_users else 0.0
    if ms_between + ms_within == 0:
        return 0.0
    estimate = (ms_between - ms_within) / (ms_between + (mean_cluster - 1) * ms_within)
    return float(max(0.0, estimate))
