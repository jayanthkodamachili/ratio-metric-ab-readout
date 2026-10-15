"""E3: the condition under which the naive test is right.

Cluster size alone breaks nothing. What breaks a naive test is cluster size combined with
within-user similarity, and this sweep isolates the second term by holding events per user
fixed and moving the correlation from zero upward. At zero the naive test should be exactly
correct, and that is the result worth having: it names the assumption rather than just
reporting that the test failed.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import table, write  # noqa: E402
from _simulate import simulate  # noqa: E402

from ratio_readout.config import ScenarioConfig  # noqa: E402

REPLICATES = 600
ICCS = (0.0, 0.02, 0.05, 0.10, 0.20, 0.40)
MEAN_EVENTS = 8.0


def run() -> dict:
    cells = []
    for icc in ICCS:
        base = ScenarioConfig(
            n_users=4000, mean_events=MEAN_EVENTS, icc=icc, lift=0.0,
            bootstrap_resamples=200, seed=300_000,
        )
        result = simulate(base, replicates=REPLICATES, include_bootstrap=False)
        cells.append({
            "icc": icc,
            "naive_fpr": result.rejection_rate["naive_event"],
            "delta_fpr": result.rejection_rate["delta_method"],
            "se_ratio": result.mean_se_ratio,
            "design_effect_sqrt": base.design_effect ** 0.5,
        })

    zero = next(c for c in cells if c["icc"] == 0.0)
    worst = max(cells, key=lambda c: c["naive_fpr"])
    return {
        "experiment": "e3_correlation",
        "question": "At what correlation does the naive test stop being correct?",
        "replicates": REPLICATES,
        "mean_events": MEAN_EVENTS,
        "cells": cells,
        "zero_icc_naive_fpr": zero["naive_fpr"],
        "zero_icc_se_ratio": zero["se_ratio"],
        "worst_icc": worst["icc"],
        "worst_naive_fpr": worst["naive_fpr"],
        "max_theory_gap": max(abs(c["se_ratio"] - c["design_effect_sqrt"]) for c in cells),
    }


def main() -> None:
    payload = run()
    rows = [
        [
            f"{c['icc']:.2f}",
            f"{c['naive_fpr']:.3f}",
            f"{c['delta_fpr']:.3f}",
            f"{c['se_ratio']:.3f}",
            f"{c['design_effect_sqrt']:.3f}",
        ]
        for c in payload["cells"]
    ]
    print(f"E3 false positive rate by intra-class correlation, {MEAN_EVENTS:.0f} events per user\n")
    print(table(
        ["icc", "naive fpr", "delta fpr", "se ratio", "predicted"],
        rows, [8, 12, 12, 11, 11],
    ))
    print()
    print(
        f"at icc 0 the naive rate is {payload['zero_icc_naive_fpr']:.3f} "
        f"with an se ratio of {payload['zero_icc_se_ratio']:.3f}; "
        f"largest gap to theory across the sweep is {payload['max_theory_gap']:.3f}"
    )
    path = write("e3_correlation", payload)
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
