# ADR-002: validate by simulation rather than by derivation

## Status

Accepted.

## Context

The claim is that a per-event test misstates its variance under user-level randomisation.
That can be established two ways: derive the variance algebraically and assert the algebra,
or simulate many experiments under a known null and measure how often each test is wrong.

## Decision

Simulate. The headline figure is a measured false positive rate over thousands of A/A
replicates, and the design effect formula appears only as a prediction the simulation is
checked against.

## Alternatives considered

**Assert the algebra in tests.** Faster, deterministic, and it would prove the
implementation matches the formula. Rejected because it proves the wrong thing. A reader
does not care whether the code implements the delta method correctly; they care how often
the test they are using today reaches a wrong conclusion. Only a simulation reports that,
in the unit a practitioner thinks in.

**Cite the literature and skip the measurement.** The design effect is textbook and
citing it would be defensible. Rejected because the repository's whole value is that it
measures rather than asserts, and because a formula quoted without a check is ind
distinguishable from a formula quoted wrongly only by luck.

**Both, with the derivation as the primary claim.** Considered and inverted. The formula is
the secondary claim precisely because its agreement with an independent simulation is the
evidence. Leading with it would waste that.

## Consequences

Published rates are sample proportions and carry sampling error, so every one is reported
with a confidence interval in the experiment JSON and never described as exact. The suite
also costs minutes rather than seconds in CI, which is the price of measuring the thing
that matters instead of the thing that is cheap to assert.
