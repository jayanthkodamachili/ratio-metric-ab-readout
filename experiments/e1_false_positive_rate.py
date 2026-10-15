"""E1: the headline. How often does each estimator call an effect that is not there?

Every replicate is an A/A test: both arms are drawn from the same distribution, so the
truth is that there is nothing to find. An estimator working as advertised at alpha = 0.05
should claim an effect in about 5 percent of them. The gap between that promise and what is
measured is the whole point of this repository.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import table, write  # noqa: E402
from _simulate import METHODS, simulate, wilson_interval  # noqa: E402

from ratio_readout.config import ScenarioConfig  # noqa: E402

REPLICATES = 2000
BASE = ScenarioConfig(
    n_users=4000, mean_events=8.0, icc=0.15, base_rate=0.10, lift=0.0,
    bootstrap_resamples=400, seed=100_000,
)


def run() -> dict:
    result = simulate(BASE, replicates=REPLICATES, include_bootstrap=True)

    intervals = {}
    for method in METHODS:
        rate = result.rejection_rate[method]
        low, high = wilson_interval(round(rate * REPLICATES), REPLICATES)
        intervals[method] = {"low": round(low, 5), "high": round(high, 5)}

    naive = result.rejection_rate["naive_event"]
    delta = result.rejection_rate["delta_method"]
    return {
        "experiment": "e1_false_positive_rate",
        "question": "How often does each estimator call an effect in an A/A test?",
        "scenario": BASE.as_dict(),
        "replicates": REPLICATES,
        "result": result.as_dict(),
        "wilson_intervals": intervals,
        "headline": {
            "nominal_alpha": BASE.alpha,
            "naive_fpr": naive,
            "delta_fpr": delta,
            "bootstrap_fpr": result.rejection_rate["cluster_bootstrap"],
            "naive_inflation": naive / BASE.alpha,
            "se_ratio": result.mean_se_ratio,
            "design_effect_sqrt": BASE.design_effect ** 0.5,
        },
    }


def main() -> None:
    payload = run()
    rows = []
    for method in METHODS:
        rate = payload["result"]["rejection_rate"][method]
        interval = payload["wilson_intervals"][method]
        rows.append([
            method,
            f"{rate:.3f}",
            f"[{interval['low']:.3f}, {interval['high']:.3f}]",
            f"{rate / BASE.alpha:.1f}x",
        ])
    print(f"E1 A/A false positive rate, {REPLICATES} replicates, nominal alpha {BASE.alpha}\n")
    print(table(["estimator", "measured", "95% interval", "vs nominal"], rows, [22, 11, 20, 12]))
    head = payload["headline"]
    print()
    print(
        f"mean standard error ratio {head['se_ratio']:.3f}, "
        f"design effect predicts {head['design_effect_sqrt']:.3f}"
    )
    path = write("e1_false_positive_rate", payload)
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
