from __future__ import annotations

import json

import numpy as np
import pytest

from ratio_readout import cli
from ratio_readout.config import ScenarioConfig
from ratio_readout.generate import Experiment, generate
from ratio_readout.readout import read_out

FAST = ["--n-users", "400", "--mean-events", "5", "--bootstrap-resamples", "100", "--seed", "11"]


# ----- readout -----

def test_a_readout_carries_all_three_estimates(small_config):
    assert set(read_out(small_config).estimates) == {
        "naive_event", "delta_method", "cluster_bootstrap"
    }


def test_estimates_are_ordered_naive_first_so_the_table_tells_a_story(small_config):
    assert [e.method for e in read_out(small_config).ordered] == [
        "naive_event", "delta_method", "cluster_bootstrap"
    ]


def test_the_standard_error_ratio_exceeds_one_when_events_cluster(small_config):
    assert read_out(small_config).standard_error_ratio > 1.0


def test_the_standard_error_ratio_sits_near_one_when_events_do_not(independent_config):
    assert read_out(independent_config).standard_error_ratio == pytest.approx(1.0, abs=0.12)


def test_the_measured_ratio_tracks_the_predicted_design_effect():
    """The simulation and the textbook formula are independent routes to one number.

    Agreement is evidence both are right. This is the check that turns the repository from
    a demonstration into a measurement, so it is a test rather than only an experiment.
    """
    config = ScenarioConfig(n_users=6000, mean_events=8.0, icc=0.2, bootstrap_resamples=100, seed=5)
    readout = read_out(config)
    predicted = config.design_effect ** 0.5
    assert readout.standard_error_ratio == pytest.approx(predicted, rel=0.15)


def test_a_readout_can_be_given_a_prepared_experiment(small_config):
    experiment = generate(small_config)
    assert read_out(small_config, experiment).n_users == experiment.n_users


def test_disagreement_is_false_when_both_estimators_agree(small_config):
    readout = read_out(small_config)
    assert readout.disagree_on_significance == (
        readout.estimates["naive_event"].significant_at(small_config.alpha)
        != readout.estimates["delta_method"].significant_at(small_config.alpha)
    )


def test_a_known_disagreement_is_detected():
    """Seed 4 at this configuration is the case the captured demo session uses.

    The naive test calls an effect at p = 0.012 and the clustered test does not at
    p = 0.092, from the same rows.
    """
    config = ScenarioConfig(n_users=3000, lift=0.08, bootstrap_resamples=200, seed=4)
    readout = read_out(config)
    assert readout.disagree_on_significance is True
    assert readout.estimates["naive_event"].significant_at(0.05) is True
    assert readout.estimates["delta_method"].significant_at(0.05) is False


def test_an_infinite_ratio_is_reported_when_the_naive_error_is_zero(small_config):
    flat = Experiment(
        assignment=np.array([0, 0, 1, 1]),
        denominator=np.array([3, 3, 3, 3]),
        numerator=np.array([0, 0, 0, 0]),
    )
    assert np.isinf(read_out(small_config, flat).standard_error_ratio)


def test_readout_as_dict_is_json_serialisable(small_config):
    json.dumps(read_out(small_config).as_dict())


# ----- cli -----

def test_parser_defaults_match_the_documented_scenario():
    args = cli.build_parser().parse_args([])
    assert args.icc == 0.15
    assert args.alpha == 0.05
    assert args.lift == 0.0


def test_an_aa_test_exits_zero(capsys):
    code = cli.main(FAST)
    capsys.readouterr()
    assert code == cli.EXIT_NO_EFFECT


def test_a_large_real_effect_exits_one(capsys):
    code = cli.main([*FAST, "--n-users", "4000", "--lift", "0.8"])
    capsys.readouterr()
    assert code == cli.EXIT_EFFECT_FOUND


def test_a_disagreement_gets_its_own_exit_code(capsys):
    code = cli.main(["--n-users", "3000", "--lift", "0.08", "--bootstrap-resamples", "200",
                     "--seed", "4"])
    capsys.readouterr()
    assert code == cli.EXIT_ESTIMATORS_DISAGREE


def test_a_sample_ratio_mismatch_outranks_every_other_verdict(capsys):
    """Assignment being broken makes the downstream estimates unreadable, so the gate wins.

    The scenario declares an even split and the mechanism delivers 42 percent, which is
    what a misconfigured allocation looks like from the analyst's side. Without the
    injection knob this path was unreachable, and a gate that cannot fire is decoration:
    the test that found that is the reason the knob exists.
    """
    code = cli.main([*FAST, "--n-users", "4000", "--treatment-share", "0.5",
                     "--delivered-treatment-share", "0.42"])
    out = capsys.readouterr().out
    assert code == cli.EXIT_SRM
    assert "SAMPLE RATIO MISMATCH" in out


def test_without_an_injected_fault_the_gate_stays_quiet(capsys):
    cli.main(FAST)
    assert "SAMPLE RATIO MISMATCH" not in capsys.readouterr().out


def test_an_invalid_delivered_share_is_rejected(capsys):
    code = cli.main([*FAST, "--delivered-treatment-share", "1.4"])
    assert code == cli.EXIT_BAD_CONFIG
    assert "delivered_treatment_share" in capsys.readouterr().err


def test_an_impossible_scenario_exits_two_without_a_traceback(capsys):
    code = cli.main(["--base-rate", "0.9", "--lift", "0.5"])
    captured = capsys.readouterr()
    assert code == cli.EXIT_BAD_CONFIG
    assert "invalid scenario" in captured.err
    assert "Traceback" not in captured.err


def test_an_internal_failure_exits_three(monkeypatch, capsys):
    def explode(_config):
        raise RuntimeError("scipy went home")

    monkeypatch.setattr(cli, "read_out", explode)
    code = cli.main(FAST)
    captured = capsys.readouterr()
    assert code == cli.EXIT_INTERNAL_ERROR
    assert "readout failed to complete" in captured.err


def test_every_exit_code_is_distinct():
    """Six codes, six meanings. Collapsing any two makes the tool unusable in a pipeline."""
    codes = {
        cli.EXIT_NO_EFFECT, cli.EXIT_EFFECT_FOUND, cli.EXIT_BAD_CONFIG,
        cli.EXIT_INTERNAL_ERROR, cli.EXIT_ESTIMATORS_DISAGREE, cli.EXIT_SRM,
    }
    assert len(codes) == 6


def test_json_mode_emits_parseable_output(capsys):
    cli.main([*FAST, "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert set(payload["estimates"]) == {"naive_event", "delta_method", "cluster_bootstrap"}
    assert payload["config"]["seed"] == 11


def test_table_mode_names_every_estimator_and_its_unit(capsys):
    cli.main(FAST)
    out = capsys.readouterr().out
    for name in ("naive_event", "delta_method", "cluster_bootstrap"):
        assert name in out
    assert "event" in out and "user" in out


def test_table_mode_publishes_the_ratio_against_the_predicted_design_effect(capsys):
    cli.main(FAST)
    assert "times the naive one" in capsys.readouterr().out


def test_table_mode_announces_a_disagreement_in_words(capsys):
    cli.main(["--n-users", "3000", "--lift", "0.08", "--bootstrap-resamples", "200",
              "--seed", "4"])
    assert "disagree about whether there is an effect" in capsys.readouterr().out


def test_an_unknown_flag_is_rejected_by_the_parser():
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["--definitely-not-a-flag"])
