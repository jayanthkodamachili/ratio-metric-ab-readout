# ADR-005: what this repository deliberately cannot measure

## Status

Accepted. This is the boundary record, so the limits are a decision rather than an
oversight.

## Context

The experiments produce confident numbers about a real and common mistake. Several of them
are properties of the setup rather than of A/B testing in general, and a reader who takes
them for more than they are will reach wrong conclusions in their own work.

## Decision

Five things are out of scope, each for a stated reason, and the README carries them in a
section of its own rather than in a footnote.

## What is out of scope, and why

**Sequential testing and peeking.** Every test here is computed once at a fixed horizon.
Looking at a running experiment inflates the false positive rate through a mechanism this
repository does not model and does not correct. This is the sharpest limitation, because a
reader could fix their variance, keep peeking, and still be wrong at a rate this repository
would not catch. It is the Pivot, with an explicit trigger condition.

**Nested and overlapping clustering.** Users contribute events and nothing else here. Real
experiments have sessions inside users, devices shared between users, and interference
between them. Each adds a route to the same failure, and the design effect compounds in
ways a single-level model does not show.

**Real data.** The mechanism is structural and transfers. The magnitudes are properties of
this generator. No figure here should be quoted as a fact about a real product.

**Variance reduction.** CUPED and its relatives are the standard answer to the power loss
this repository measures. By leaving them out, the power figures here are a worst case: a
team that corrects the variance and then applies variance reduction gets some of that power
back, and this repository cannot say how much.

**Anything the SRM gate does not test.** The gate compares user counts per arm against the
declared split. Assignment that is numerically balanced while correlating with the metric
passes it, and that is a more dangerous failure than an imbalance, because nothing flags it.

## Observed against declared

Everything in `docs/metrics.json` is observed: produced by code here, re-run by CI. One
thing is declared rather than observed and should be read as a modelling assumption, that
this generator's distribution resembles a production experiment in any respect that matters.
It was chosen to be awkward, not to be representative.

## Rates are estimates

Every false positive rate published here is a sample proportion over a finite number of
replicates. The experiment JSON carries a Wilson interval for each headline rate, and no
rate in any document should be read as exact. The interval is Wilson rather than the
textbook normal one because these rates sit near zero, where the normal interval produces a
lower bound below zero and invites a precision the sample cannot support.

## Machine dependence

The published figures are rates, ratios and counts, all machine independent. The one place
durations appear is ADR-003, where they are the subject, are presented as a ratio, and are
labelled as facts about one machine. No duration is published as a headline anywhere.

## Consequences

The repository makes a narrower claim than its numbers would support if read carelessly,
and says so in the most prominent place a limitation can go. A reviewer who reads this file
first should find nothing in the README that overreaches it.
