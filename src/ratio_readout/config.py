"""The frozen description of an experiment, so every estimator sees identical data.

Two knobs drive everything this repository measures: how many events a user contributes,
and how strongly one user's events resemble each other. Their product is what inflates a
naive standard error, and keeping both in one immutable object means a measured difference
between estimators cannot be an artefact of one of them seeing a different draw.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

ESTIMATORS = ("naive_event", "delta_method", "cluster_bootstrap")


class ConfigError(ValueError):
    """Raised when a scenario cannot be constructed, rather than merely being unusual."""


@dataclass(frozen=True)
class ScenarioConfig:
    """One fully specified experiment.

    Attributes:
        n_users: randomisation units, split between the two arms.
        mean_events: mean events contributed per user. The cluster size.
        icc: intra-class correlation, the share of outcome variance that is between users
            rather than within them. Zero means a user's events are no more alike than any
            two random events, which is the only case where the naive test is correct.
        base_rate: control arm event-level success probability.
        lift: relative effect applied to the treatment arm. Zero makes this an A/A test.
        treatment_share: intended share of users assigned to treatment.
        alpha: nominal significance level, the rate the false positive rate is measured
            against.
        bootstrap_resamples: resamples drawn by the cluster bootstrap.
        seed: controls assignment, event counts, propensities and outcomes.
    """

    n_users: int = 4000
    mean_events: float = 8.0
    icc: float = 0.15
    base_rate: float = 0.10
    lift: float = 0.0
    treatment_share: float = 0.5
    alpha: float = 0.05
    bootstrap_resamples: int = 1000
    seed: int = 20260215

    def __post_init__(self) -> None:
        if self.n_users < 20:
            raise ConfigError("n_users must be at least 20 to split into two usable arms")
        if self.mean_events < 1.0:
            raise ConfigError("mean_events must be at least 1, every user contributes an event")
        if not 0.0 <= self.icc < 1.0:
            raise ConfigError("icc must sit in [0, 1)")
        if not 0.0 < self.base_rate < 1.0:
            raise ConfigError("base_rate must sit strictly between 0 and 1")
        if not 0.0 < self.treatment_share < 1.0:
            raise ConfigError("treatment_share must sit strictly between 0 and 1")
        if not 0.0 < self.alpha < 1.0:
            raise ConfigError("alpha must sit strictly between 0 and 1")
        if self.bootstrap_resamples < 50:
            raise ConfigError("bootstrap_resamples below 50 cannot estimate a standard error")
        self._check_treated_rate_stays_a_probability()

    def _check_treated_rate_stays_a_probability(self) -> None:
        """Reject a lift that pushes the treated rate to or past 1.

        Without this the beta parameters go non-positive and numpy returns nan silently,
        which then propagates into a p-value of nan. A scenario that cannot exist should
        fail where it is described, not several layers down inside a simulation loop.
        """
        treated = self.base_rate * (1.0 + self.lift)
        if not 0.0 < treated < 1.0:
            raise ConfigError(
                f"lift {self.lift} drives the treated rate to {treated:.4f}, "
                "which is not a probability"
            )

    @property
    def design_effect(self) -> float:
        """The classical variance inflation factor, 1 + (m - 1) * icc.

        Published alongside the measured standard error ratio in experiment three. It is a
        prediction this repository checks rather than an output it reports, which is the
        point: a formula agreeing with a simulation is evidence both are right.
        """
        return 1.0 + (self.mean_events - 1.0) * self.icc

    def as_dict(self) -> dict:
        return asdict(self)
