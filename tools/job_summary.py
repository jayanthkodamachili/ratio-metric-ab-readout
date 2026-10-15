"""Print the table a reviewer should actually see, for the CI job summary.

It leads with the power cost rather than the false positive rate. The inflated false
positive rate is the attention-getting number and it flatters the tool; the power cost is
what a team has to accept to adopt the fix, so that goes first.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
METRICS = ROOT / "docs" / "metrics.json"
E4 = ROOT / "docs" / "experiments" / "e4_what_it_costs.json"


def main() -> int:
    if not METRICS.exists() or not E4.exists():
        print("### receipts\n\nexperiment output missing, nothing to summarise.")
        return 0

    metrics = json.loads(METRICS.read_text())["metrics"]
    e4 = json.loads(E4.read_text())

    print("### What the correct variance costs\n")
    print(
        f"A true lift of {e4['true_lift']:+.0%}, measured both ways. The naive column is "
        "what a team believes it has.\n"
    )
    print("| users | naive power | real power | gap |")
    print("| --- | --- | --- | --- |")
    for cell in e4["cells"]:
        gap = cell["naive_power"] - cell["delta_power"]
        print(
            f"| {cell['n_users']} | {cell['naive_power']:.3f} "
            f"| {cell['delta_power']:.3f} | {gap:.3f} |"
        )
    print()
    if not e4["delta_reaches_80_in_range"]:
        print(
            f"The corrected test never reaches 80 percent power in this sweep. At "
            f"{metrics['e4_largest_n']} users its real power is "
            f"{metrics['delta_power_at_largest']:.3f} while the naive test appears to "
            f"reach {metrics['naive_power_at_largest']:.3f}.\n"
        )
    print(
        f"Under a true null the naive test claims an effect in "
        f"{metrics['naive_fpr']:.3f} of replicates against a nominal 0.05, "
        f"{metrics['naive_inflation']:.1f} times the advertised rate."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
