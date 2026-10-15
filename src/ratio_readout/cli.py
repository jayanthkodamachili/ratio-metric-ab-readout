"""Command line entry point.

Exit codes carry the verdict rather than merely reporting that the program ran. The split
that matters most here is between code 1 and code 4: an experiment with no detectable
effect is a perfectly good result, while an experiment where the two estimators disagree
about whether there is an effect is a finding about the measurement process and deserves
its own code so a pipeline can route it to a human.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from ratio_readout.config import ConfigError, ScenarioConfig
from ratio_readout.readout import Readout, read_out

EXIT_NO_EFFECT = 0
EXIT_EFFECT_FOUND = 1
EXIT_BAD_CONFIG = 2
EXIT_INTERNAL_ERROR = 3
EXIT_ESTIMATORS_DISAGREE = 4
EXIT_SRM = 5


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ab-readout",
        description=(
            "Read out a ratio metric experiment three ways and report where they disagree."
        ),
    )
    parser.add_argument("--n-users", type=int, default=4000)
    parser.add_argument("--mean-events", type=float, default=8.0)
    parser.add_argument(
        "--icc",
        type=float,
        default=0.15,
        help="intra-class correlation; 0 makes a user's events independent",
    )
    parser.add_argument("--base-rate", type=float, default=0.10)
    parser.add_argument("--lift", type=float, default=0.0, help="0 runs an A/A test")
    parser.add_argument("--treatment-share", type=float, default=0.5)
    parser.add_argument("--alpha", type=float, default=0.05)
    parser.add_argument("--bootstrap-resamples", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=20260215)
    parser.add_argument("--json", action="store_true", help="emit machine readable output")
    return parser


def config_from_args(args: argparse.Namespace) -> ScenarioConfig:
    return ScenarioConfig(
        n_users=args.n_users,
        mean_events=args.mean_events,
        icc=args.icc,
        base_rate=args.base_rate,
        lift=args.lift,
        treatment_share=args.treatment_share,
        alpha=args.alpha,
        bootstrap_resamples=args.bootstrap_resamples,
        seed=args.seed,
    )


def render(readout: Readout) -> str:
    config = readout.config
    lines = [
        f"{readout.n_users} users, {readout.n_events} events, "
        f"mean {readout.n_events / readout.n_users:.2f} events per user",
        f"configured icc {config.icc:.3f}, observed {readout.observed_icc:.3f}, "
        f"true lift {config.lift:+.1%}",
        "",
        f"control {readout.control_ratio:.5f}   treatment {readout.treatment_ratio:.5f}",
        "",
        f"{'estimator':<20}{'unit':>8}{'effect':>12}{'std error':>12}{'p value':>11}{'calls it':>10}",
        "-" * 73,
    ]
    for estimate in readout.ordered:
        verdict = "effect" if estimate.significant_at(config.alpha) else "no effect"
        lines.append(
            f"{estimate.method:<20}{estimate.unit:>8}{estimate.effect:>12.5f}"
            f"{estimate.standard_error:>12.5f}{estimate.p_value:>11.4f}{verdict:>10}"
        )
    lines.append("-" * 73)
    lines.append(
        f"clustered standard error is {readout.standard_error_ratio:.2f} times the naive one "
        f"(design effect predicts {config.design_effect ** 0.5:.2f})"
    )
    if readout.disagree_on_significance:
        lines.append(
            "the naive test and the clustered test disagree about whether there is an effect"
        )
    if readout.srm.mismatched:
        lines.append(f"SAMPLE RATIO MISMATCH: p = {readout.srm.p_value:.2e}")
    return "\n".join(lines)


def exit_code_for(readout: Readout) -> int:
    if readout.srm.mismatched:
        return EXIT_SRM
    if readout.disagree_on_significance:
        return EXIT_ESTIMATORS_DISAGREE
    if readout.estimates["delta_method"].significant_at(readout.config.alpha):
        return EXIT_EFFECT_FOUND
    return EXIT_NO_EFFECT


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        config = config_from_args(args)
    except ConfigError as exc:
        print(f"invalid scenario: {exc}", file=sys.stderr)
        return EXIT_BAD_CONFIG

    try:
        readout = read_out(config)
    except Exception as exc:  # noqa: BLE001
        print(f"readout failed to complete: {exc}", file=sys.stderr)
        return EXIT_INTERNAL_ERROR

    print(json.dumps(readout.as_dict(), indent=2) if args.json else render(readout))
    return exit_code_for(readout)


if __name__ == "__main__":
    raise SystemExit(main())
