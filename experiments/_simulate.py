"""The A/A simulation loop every experiment here is built from.

Separated out because the loop is the measurement instrument. Each replicate draws a fresh
experiment with no true effect and asks each estimator whether it sees one. The share of
replicates where an estimator says yes is its false positive rate, and comparing that to
the nominal alpha is the only way to find out whether a p-value means what it says.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ratio_readout.config import ScenarioConfig
from ratio_readout.estimators import cluster_bootstrap, delta_method, naive_event
from ratio_readout.generate import generate

METHODS = ("naive_event", "delta_method", "cluster_bootstrap")


@dataclass(frozen=True)
class SimulationResult:
    """Rejection rates and standard errors, per method, over many replicates."""

    replicates: int
    alpha: float
    rejection_rate: dict[str, float]
    mean_standard_error: dict[str, float]
    mean_se_ratio: float

    def as_dict(self) -> dict:
        return {
            "replicates": self.replicates,
            "alpha": self.alpha,
            "rejection_rate": {k: round(v, 5) for k, v in self.rejection_rate.items()},
            "mean_standard_error": {
                k: round(v, 8) for k, v in self.mean_standard_error.items()
            },
            "mean_se_ratio": round(self.mean_se_ratio, 5),
        }


def simulate(
    base: ScenarioConfig,
    replicates: int,
    seed_offset: int = 0,
    include_bootstrap: bool = True,
) -> SimulationResult:
    """Run many independent replicates of one scenario.

    The bootstrap can be skipped. It agrees with the delta method closely enough that
    running it in every sweep cell would multiply the cost of the whole suite for a third
    line that lands on top of the second. It runs in the headline experiment, where the
    agreement is the thing being demonstrated, and is skipped in the sweeps.
    """
    rejections = {method: 0 for method in METHODS}
    errors: dict[str, list[float]] = {method: [] for method in METHODS}

    for replicate in range(replicates):
        config = ScenarioConfig(
            **{**base.as_dict(), "seed": base.seed + seed_offset + replicate}
        )
        experiment = generate(config)

        estimates = {
            "naive_event": naive_event(experiment),
            "delta_method": delta_method(experiment),
        }
        if include_bootstrap:
            estimates["cluster_bootstrap"] = cluster_bootstrap(
                experiment, config.bootstrap_resamples, config.seed
            )

        for method, estimate in estimates.items():
            errors[method].append(estimate.standard_error)
            if estimate.significant_at(config.alpha):
                rejections[method] += 1

    present = [m for m in METHODS if errors[m]]
    mean_error = {m: float(np.mean(errors[m])) for m in present}
    return SimulationResult(
        replicates=replicates,
        alpha=base.alpha,
        rejection_rate={m: rejections[m] / replicates for m in present},
        mean_standard_error=mean_error,
        mean_se_ratio=mean_error["delta_method"] / mean_error["naive_event"],
    )


def wilson_interval(successes: int, trials: int, z: float = 1.96) -> tuple[float, float]:
    """A confidence interval for a measured rate, so a rate is never read as exact.

    Wilson rather than the textbook normal interval because the rates here can sit near
    zero, where the normal interval produces a lower bound below zero and invites the
    reader to believe a precision the sample cannot support.
    """
    if trials == 0:
        return (0.0, 1.0)
    p = successes / trials
    denominator = 1 + z * z / trials
    centre = (p + z * z / (2 * trials)) / denominator
    spread = z * np.sqrt(p * (1 - p) / trials + z * z / (4 * trials * trials)) / denominator
    return (float(max(0.0, centre - spread)), float(min(1.0, centre + spread)))
