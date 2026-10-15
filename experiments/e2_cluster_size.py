"""E2: how the error grows with the number of events a user contributes.

The naive test is not wrong in general. It is wrong by an amount, and the amount is driven
by cluster size. At one event per user there is no cluster and nothing to get wrong. This
sweep traces the path from there to a badly broken test, which is what makes the failure
predictable rather than mysterious.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import table, write  # noqa: E402
from _simulate import simulate  # noqa: E402

from ratio_readout.config import ScenarioConfig  # noqa: E402

REPLICATES = 600
MEAN_EVENTS = (1.0, 2.0, 4.0, 8.0, 16.0, 32.0)
ICC = 0.15


def run() -> dict:
    cells = []
    for mean_events in MEAN_EVENTS:
        base = ScenarioConfig(
            n_users=4000, mean_events=mean_events, icc=ICC, lift=0.0,
            bootstrap_resamples=200, seed=200_000,
        )
        result = simulate(base, replicates=REPLICATES, include_bootstrap=False)
        cells.append({
            "mean_events": mean_events,
            "naive_fpr": result.rejection_rate["naive_event"],
            "delta_fpr": result.rejection_rate["delta_method"],
            "se_ratio": result.mean_se_ratio,
            "design_effect_sqrt": base.design_effect ** 0.5,
        })

    single = next(c for c in cells if c["mean_events"] == 1.0)
    largest = max(cells, key=lambda c: c["mean_events"])
    return {
        "experiment": "e2_cluster_size",
        "question": "How does the naive error grow with events per user?",
        "replicates": REPLICATES,
        "icc": ICC,
        "cells": cells,
        "single_event_naive_fpr": single["naive_fpr"],
        "single_event_se_ratio": single["se_ratio"],
        "largest_cluster_naive_fpr": largest["naive_fpr"],
        "largest_mean_events": largest["mean_events"],
        "max_theory_gap": max(
            abs(c["se_ratio"] - c["design_effect_sqrt"]) for c in cells
        ),
    }


def main() -> None:
    payload = run()
    rows = [
        [
            f"{c['mean_events']:.0f}",
            f"{c['naive_fpr']:.3f}",
            f"{c['delta_fpr']:.3f}",
            f"{c['se_ratio']:.3f}",
            f"{c['design_effect_sqrt']:.3f}",
        ]
        for c in payload["cells"]
    ]
    print(f"E2 false positive rate by events per user, icc {ICC}, {REPLICATES} replicates\n")
    print(table(
        ["events/user", "naive fpr", "delta fpr", "se ratio", "predicted"],
        rows, [14, 12, 12, 11, 11],
    ))
    print()
    print(
        f"at one event per user the naive rate is {payload['single_event_naive_fpr']:.3f}; "
        f"at {payload['largest_mean_events']:.0f} it is "
        f"{payload['largest_cluster_naive_fpr']:.3f}"
    )
    path = write("e2_cluster_size", payload)
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
