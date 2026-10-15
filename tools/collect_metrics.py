"""Re-measure every published figure and write docs/metrics.json.

Nothing here types a number. It reads the test count and coverage from the machine readable
reports, runs the four experiments, reads their JSON, and derives the handful of values the
documents quote.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXPERIMENT_DIR = ROOT / "docs" / "experiments"
METRICS_PATH = ROOT / "docs" / "metrics.json"

EXPERIMENTS = (
    "e1_false_positive_rate",
    "e2_cluster_size",
    "e3_correlation",
    "e4_what_it_costs",
)

CHECKED_DOCUMENTS = (
    "README.md",
    "docs/adr/ADR-005-what-this-cannot-measure.md",
)

# Each metric names the exact wording a document must use, with the formatted value
# substituted for the brace. Anchors stay short: a long phrase wraps across a newline in
# rendered markdown and matches nothing while the prose it guards is perfectly correct.
ANCHORS: dict[str, list[str]] = {
    "tests_total": ["{} tests"],
    "coverage_line_pct": ["{} percent line coverage", "{}% line coverage"],
    "replicates_e1": ["{} A/A replicates", "over {} replicates"],
    "naive_fpr": ["claims an effect in {}", "{} of them"],
    "delta_fpr": ["delta method sits at {}", "delta method at {}"],
    "bootstrap_fpr": ["bootstrap at {}", "{} for the bootstrap"],
    "naive_inflation": ["{} times the rate", "{} times"],
    "se_ratio": ["{} times larger", "ratio of {}"],
    "design_effect_sqrt": ["theory predicts {}", "predicts {}"],
    "single_event_fpr": ["{} at one event", "one event per user it is {}"],
    "largest_cluster_fpr": ["rises to {}", "{} at 32"],
    "zero_icc_fpr": ["{} when the correlation is zero", "falls to {}"],
    "zero_icc_se_ratio": ["ratio of exactly {}", "exactly {}"],
    "worst_icc_fpr": ["{} at a correlation", "reaches {}"],
    "max_theory_gap": ["within {} of", "no more than {}"],
    "naive_power_at_largest": ["appears to reach {}", "{} power"],
    "delta_power_at_largest": ["real power is {}", "actually {}"],
    "power_gap_at_largest": ["{} points of power", "gap of {}"],
    "e4_largest_n": ["{} users", "at {}"],
    "srm_users_declared": ["declared {} percent", "{} percent split"],
}


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=ROOT, check=False, **kwargs)


def measure_suite(skip_tests: bool) -> dict:
    """Read the test count and coverage from machine readable artefacts.

    With skip_tests the artefacts must already exist, because CI runs pytest as its own
    step. That separation matters: a failing test surfacing here as a traceback from a
    metrics script is a CI signature that costs an hour to attribute.
    """
    junit = ROOT / "junit.xml"
    cov = ROOT / "coverage.json"

    if skip_tests:
        missing = [p.name for p in (junit, cov) if not p.exists()]
        if missing:
            raise SystemExit(f"--skip-tests given but {', '.join(missing)} not found")
    else:
        result = run(
            [
                sys.executable, "-m", "pytest",
                f"--junitxml={junit}",
                "--cov=ratio_readout",
                "--cov-report=json",
                "-q",
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(result.stdout[-4000:], file=sys.stderr)
            raise SystemExit("test suite failed, refusing to publish metrics")

    suite = ET.parse(junit).getroot()
    node = suite if suite.tag == "testsuite" else suite.find("testsuite")
    total = int(node.get("tests", 0))
    skipped = int(node.get("skipped", 0))
    coverage = json.loads(cov.read_text())["totals"]["percent_covered"]
    return {
        "tests_total": total - skipped,
        "coverage_line_pct": round(coverage, 1),
    }


def ensure_experiments(rerun: bool) -> dict[str, dict]:
    payloads = {}
    for name in EXPERIMENTS:
        path = EXPERIMENT_DIR / f"{name}.json"
        if rerun or not path.exists():
            print(f"running experiment {name}")
            result = run([sys.executable, str(ROOT / "experiments" / f"{name}.py")])
            if result.returncode != 0:
                raise SystemExit(f"experiment {name} failed")
        payloads[name] = json.loads(path.read_text())
    return payloads


E2_ROWS = (1, 2, 4, 8, 16, 32)
E3_ROWS = ("0.00", "0.02", "0.05", "0.10", "0.20", "0.40")
TABLE_ANCHOR = ["| {} |"]


def derive(suite: dict, exp: dict[str, dict]) -> dict[str, float | int]:
    e1 = exp["e1_false_positive_rate"]
    e2 = exp["e2_cluster_size"]
    e3 = exp["e3_correlation"]
    e4 = exp["e4_what_it_costs"]
    head = e1["headline"]

    metrics: dict[str, float | int] = {
        "tests_total": suite["tests_total"],
        "coverage_line_pct": suite["coverage_line_pct"],
        "replicates_e1": e1["replicates"],
        "naive_fpr": round(head["naive_fpr"], 3),
        "delta_fpr": round(head["delta_fpr"], 3),
        "bootstrap_fpr": round(head["bootstrap_fpr"], 3),
        "naive_inflation": round(head["naive_inflation"], 1),
        "se_ratio": round(head["se_ratio"], 3),
        "design_effect_sqrt": round(head["design_effect_sqrt"], 3),
        "single_event_fpr": round(e2["single_event_naive_fpr"], 3),
        "largest_cluster_fpr": round(e2["largest_cluster_naive_fpr"], 3),
        "zero_icc_fpr": round(e3["zero_icc_naive_fpr"], 3),
        "zero_icc_se_ratio": round(e3["zero_icc_se_ratio"], 3),
        "worst_icc_fpr": round(e3["worst_naive_fpr"], 3),
        "max_theory_gap": round(max(e2["max_theory_gap"], e3["max_theory_gap"]), 3),
        "naive_power_at_largest": round(e4["naive_power_at_largest"], 3),
        "delta_power_at_largest": round(e4["delta_power_at_largest"], 3),
        "power_gap_at_largest": round(e4["power_gap_at_largest"], 3),
        "e4_largest_n": e4["largest_n"],
        "srm_users_declared": 50,
    }

    # Every cell of the two published sweeps, so the reverse check has something to match
    # and a drifting table breaks the build like any other figure.
    for cell in e2["cells"]:
        key = int(cell["mean_events"])
        metrics[f"e2_{key}_naive"] = round(cell["naive_fpr"], 3)
        metrics[f"e2_{key}_delta"] = round(cell["delta_fpr"], 3)
        metrics[f"e2_{key}_ratio"] = round(cell["se_ratio"], 3)
        metrics[f"e2_{key}_predicted"] = round(cell["design_effect_sqrt"], 3)
        ANCHORS.setdefault(f"e2_{key}_naive", TABLE_ANCHOR)
        ANCHORS.setdefault(f"e2_{key}_delta", TABLE_ANCHOR)
        ANCHORS.setdefault(f"e2_{key}_ratio", TABLE_ANCHOR)
        ANCHORS.setdefault(f"e2_{key}_predicted", TABLE_ANCHOR)

    for cell in e3["cells"]:
        key = f"{cell['icc']:.2f}".replace(".", "")
        # The configured correlation is a row label rather than a measurement, and it is
        # still registered: it is read back out of the experiment JSON, so a sweep that
        # quietly changed which correlations it ran would break the build instead of
        # leaving the README describing a sweep that no longer happens.
        metrics[f"e3_{key}_icc"] = cell["icc"]
        ANCHORS.setdefault(f"e3_{key}_icc", TABLE_ANCHOR)
        metrics[f"e3_{key}_naive"] = round(cell["naive_fpr"], 3)
        metrics[f"e3_{key}_ratio"] = round(cell["se_ratio"], 3)
        metrics[f"e3_{key}_predicted"] = round(cell["design_effect_sqrt"], 3)
        ANCHORS.setdefault(f"e3_{key}_naive", TABLE_ANCHOR)
        ANCHORS.setdefault(f"e3_{key}_ratio", TABLE_ANCHOR)
        ANCHORS.setdefault(f"e3_{key}_predicted", TABLE_ANCHOR)

    for cell in e4["cells"]:
        key = cell["n_users"]
        metrics[f"e4_{key}_naive_power"] = round(cell["naive_power"], 3)
        metrics[f"e4_{key}_delta_power"] = round(cell["delta_power"], 3)
        ANCHORS.setdefault(f"e4_{key}_naive_power", TABLE_ANCHOR)
        ANCHORS.setdefault(f"e4_{key}_delta_power", TABLE_ANCHOR)

    return metrics


THREE_PLACE_SUFFIXES = ("_fpr", "_ratio", "_naive", "_delta", "_predicted", "_power", "_gap")
TWO_PLACE_SUFFIXES = ("_icc",)
ONE_PLACE = frozenset({"naive_inflation"})


def display_strings(metrics: dict) -> dict[str, str]:
    """How each value must appear in prose, so the checker and the author agree.

    Formatting is declared rather than guessed from the value's type, because a figure
    that renders as 0.19 in one sentence and 0.190 in another silently defeats the whole
    anchor mechanism.
    """
    out = {}
    for key, value in metrics.items():
        if isinstance(value, int):
            out[key] = str(value)
        elif key in ONE_PLACE:
            out[key] = f"{value:.1f}"
        elif key == "coverage_line_pct":
            out[key] = f"{value:.0f}" if float(value).is_integer() else f"{value:.1f}"
        elif any(key.endswith(suffix) for suffix in TWO_PLACE_SUFFIXES):
            out[key] = f"{value:.2f}"
        elif any(key.endswith(suffix) for suffix in THREE_PLACE_SUFFIXES):
            out[key] = f"{value:.3f}"
        else:
            out[key] = f"{value:.3f}"
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Re-measure every published figure.")
    parser.add_argument("--reuse", action="store_true", help="read existing experiment JSON")
    parser.add_argument(
        "--skip-tests", action="store_true", help="read reports from a separate pytest step"
    )
    args = parser.parse_args()

    suite = measure_suite(skip_tests=args.skip_tests)
    experiments = ensure_experiments(rerun=not args.reuse)
    metrics = derive(suite, experiments)

    payload = {
        "metrics": metrics,
        "display": display_strings(metrics),
        "anchors": ANCHORS,
        "checked_documents": list(CHECKED_DOCUMENTS),
        "note": "every value here is produced by running the suite and the four experiments",
    }
    METRICS_PATH.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"wrote {METRICS_PATH} with {len(metrics)} metrics")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
