"""E4: what the correct variance costs, and what it buys.

Fixing the standard error is not free. A larger standard error means a larger effect is
needed before the test will call it, which is the same as saying the experiment has less
power than the team believed. This experiment prices both sides: how many of the naive
test's wins survive the correction, and how many extra users the corrected test needs to
win them back honestly.

The uncomfortable half is the first number. Under a true null, every single one of the
naive test's wins was false, and the sweep below shows how many of them there were at the
sample sizes teams actually run.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import table, write  # noqa: E402
from _simulate import simulate  # noqa: E402

from ratio_readout.config import ScenarioConfig  # noqa: E402

REPLICATES = 500
USER_COUNTS = (1000, 2000, 4000, 8000, 16000)
TRUE_LIFT = 0.06


def run() -> dict:
    cells = []
    for n_users in USER_COUNTS:
        null_base = ScenarioConfig(
            n_users=n_users, mean_events=8.0, icc=0.15, lift=0.0,
            bootstrap_resamples=200, seed=400_000,
        )
        null_result = simulate(null_base, replicates=REPLICATES, include_bootstrap=False)

        power_base = ScenarioConfig(
            n_users=n_users, mean_events=8.0, icc=0.15, lift=TRUE_LIFT,
            bootstrap_resamples=200, seed=500_000,
        )
        power_result = simulate(power_base, replicates=REPLICATES, include_bootstrap=False)

        cells.append({
            "n_users": n_users,
            "naive_fpr": null_result.rejection_rate["naive_event"],
            "delta_fpr": null_result.rejection_rate["delta_method"],
            "naive_power": power_result.rejection_rate["naive_event"],
            "delta_power": power_result.rejection_rate["delta_method"],
        })

    # The honest power the corrected test reaches at the largest sample, against the power
    # the naive test appeared to have at the smallest.
    smallest = cells[0]
    largest = cells[-1]

    def closest_to(target: float) -> dict | None:
        eligible = [c for c in cells if c["delta_power"] >= target]
        return min(eligible, key=lambda c: c["n_users"]) if eligible else None

    naive_80 = next((c for c in cells if c["naive_power"] >= 0.80), None)
    delta_80 = closest_to(0.80)

    return {
        "experiment": "e4_what_it_costs",
        "question": "What does the corrected variance cost in power, and what does it buy?",
        "replicates": REPLICATES,
        "true_lift": TRUE_LIFT,
        "cells": cells,
        "smallest_n": smallest["n_users"],
        "smallest_naive_fpr": smallest["naive_fpr"],
        "largest_n": largest["n_users"],
        "naive_power_at_largest": largest["naive_power"],
        "delta_power_at_largest": largest["delta_power"],
        "power_gap_at_largest": largest["naive_power"] - largest["delta_power"],
        "naive_80_users": naive_80["n_users"] if naive_80 else None,
        "delta_80_users": delta_80["n_users"] if delta_80 else None,
        # The corrected test not reaching 80 percent anywhere in the swept range is the
        # finding, not a gap in the sweep. Extending the range until it did would bury the
        # thing a reader needs to see: an experiment sized on the naive variance is
        # underpowered for the effect it was sized to detect.
        "delta_reaches_80_in_range": delta_80 is not None,
        "mean_power_gap": sum(c["naive_power"] - c["delta_power"] for c in cells) / len(cells),
    }


def main() -> None:
    payload = run()
    rows = [
        [
            f"{c['n_users']}",
            f"{c['naive_fpr']:.3f}",
            f"{c['delta_fpr']:.3f}",
            f"{c['naive_power']:.3f}",
            f"{c['delta_power']:.3f}",
        ]
        for c in payload["cells"]
    ]
    print(
        f"E4 cost and benefit of the clustered variance, true lift {TRUE_LIFT:+.0%}, "
        f"{REPLICATES} replicates\n"
    )
    print(table(
        ["users", "naive fpr", "delta fpr", "naive power", "delta power"],
        rows, [9, 12, 12, 14, 14],
    ))
    print()
    naive_80 = payload["naive_80_users"]
    if payload["delta_reaches_80_in_range"]:
        print(
            f"80 percent power: naive appears to reach it at {naive_80} users, "
            f"the corrected test genuinely reaches it at {payload['delta_80_users']}"
        )
    else:
        print(
            f"the naive test appears to reach 80 percent power at {naive_80} users. "
            f"The corrected test never reaches it in this sweep: at "
            f"{payload['largest_n']} users its real power is "
            f"{payload['delta_power_at_largest']:.3f}."
        )
    path = write("e4_what_it_costs", payload)
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
