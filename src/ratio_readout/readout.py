"""Produce one readout: the gate, the three estimates, and the disagreement between them.

The disagreement is the product here. A readout reporting only the correct estimate would
be a better tool and a worse instrument, because the number a team needs to see is how far
the figure they have been quoting sits from the one they should have been.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ratio_readout.config import ScenarioConfig
from ratio_readout.estimators import (
    Estimate,
    cluster_bootstrap,
    delta_method,
    naive_event,
)
from ratio_readout.generate import CONTROL, TREATMENT, Experiment, generate, observed_icc
from ratio_readout.srm import SrmResult, check_srm


@dataclass(frozen=True)
class Readout:
    """Everything one experiment has to say."""

    config: ScenarioConfig
    srm: SrmResult
    estimates: dict[str, Estimate]
    control_ratio: float
    treatment_ratio: float
    n_users: int
    n_events: int
    observed_icc: float = 0.0
    _order: tuple[str, ...] = field(
        default=("naive_event", "delta_method", "cluster_bootstrap"), repr=False
    )

    @property
    def ordered(self) -> list[Estimate]:
        return [self.estimates[name] for name in self._order]

    @property
    def standard_error_ratio(self) -> float:
        """How many times larger the clustered standard error is than the naive one.

        The single number that says how much information the naive test believed it had and
        did not. Its square is the design effect.
        """
        naive = self.estimates["naive_event"].standard_error
        clustered = self.estimates["delta_method"].standard_error
        if naive <= 0.0:
            return float("inf")
        return clustered / naive

    @property
    def disagree_on_significance(self) -> bool:
        """True when the naive test calls an effect the clustered test does not.

        This is the operational harm, as opposed to the statistical one. A standard error
        being wrong by a factor of 1.5 costs nothing until it changes a decision.
        """
        alpha = self.config.alpha
        naive = self.estimates["naive_event"].significant_at(alpha)
        delta = self.estimates["delta_method"].significant_at(alpha)
        return naive != delta

    def as_dict(self) -> dict:
        return {
            "config": self.config.as_dict(),
            "srm": self.srm.as_dict(),
            "estimates": {name: est.as_dict() for name, est in self.estimates.items()},
            "control_ratio": round(self.control_ratio, 8),
            "treatment_ratio": round(self.treatment_ratio, 8),
            "n_users": self.n_users,
            "n_events": self.n_events,
            "observed_icc": round(self.observed_icc, 6),
            "standard_error_ratio": round(self.standard_error_ratio, 6),
            "disagree_on_significance": self.disagree_on_significance,
            "design_effect_predicted": round(self.config.design_effect, 6),
        }


def read_out(config: ScenarioConfig, experiment: Experiment | None = None) -> Readout:
    """Run the gate and all three estimators against one experiment.

    The experiment can be supplied rather than generated, which is what the simulation
    experiments do: they draw many experiments from one stream and would otherwise be
    forced to rebuild a config, and therefore reseed, for every replicate.
    """
    if experiment is None:
        experiment = generate(config)

    srm = check_srm(experiment, config.treatment_share)

    estimates = {
        "naive_event": naive_event(experiment),
        "delta_method": delta_method(experiment),
        "cluster_bootstrap": cluster_bootstrap(
            experiment, config.bootstrap_resamples, config.seed
        ),
    }

    return Readout(
        config=config,
        srm=srm,
        estimates=estimates,
        control_ratio=experiment.ratio(CONTROL),
        treatment_ratio=experiment.ratio(TREATMENT),
        n_users=experiment.n_users,
        n_events=experiment.n_events,
        observed_icc=observed_icc(experiment),
    )
