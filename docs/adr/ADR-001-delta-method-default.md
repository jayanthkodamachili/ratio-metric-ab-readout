# ADR-001: the delta method as the default, the bootstrap as the oracle

## Status

Accepted.

## Context

Two methods correct the variance of a ratio metric under cluster randomisation: a closed
form delta-method expansion, and a bootstrap that resamples users. Both are implemented
here. The question is which one the tool recommends, and why it ships two at all.

## Decision

The delta method is the default and the one the exit code is computed from. The cluster
bootstrap runs alongside it as a check, and is what a disagreement would be adjudicated
against.

## Alternatives considered

**Bootstrap everywhere.** It assumes less, which is a real advantage, and the repository
measures it agreeing with the delta method closely enough to be indistinguishable in
practice. Rejected as the default on cost: it is hundreds of times more arithmetic for a
number that lands in the same place, and a correct method nobody runs because it is slow
is not an improvement over an incorrect method they do run.

**Delta method only.** Shorter, and it would remove the slowest code in the repository.
Rejected because the closed form rests on a first order expansion, and the only honest way
to know when that expansion holds is to have something to compare it against. Shipping the
oracle is what makes the default trustworthy rather than merely conventional.

**A t-distribution rather than a normal.** With thousands of users the difference is in the
fourth decimal place and would complicate every function signature.

## Consequences

The repository carries a method it does not recommend, and spends CI time on it. In
exchange the headline claim is not "the delta method is correct" but "two methods with
different assumptions agree", which is a stronger statement and one a reviewer can check by
reading one table.
