# ADR-003: the simple bootstrap loop, after measuring the vectorised one

## Status

Accepted, on measurements rather than taste.

## Context

The cluster bootstrap draws many resamples. The idiomatic numpy approach builds one index
matrix of shape (resamples, users) and gathers in a single operation, replacing a Python
loop. That is the version most reviewers would expect to find.

## Decision

Keep the explicit loop. Both versions were written and timed before choosing.

## The measurements

Wall clock, same machine, same inputs, best of several runs. Ratio above 1 means the loop
was slower.

| resamples | users | loop | vectorised | loop / vectorised |
| --- | --- | --- | --- | --- |
| 200 | 2000 | 0.01s | 0.00s | 2.89 |
| 200 | 20000 | 0.03s | 0.04s | 0.71 |
| 1000 | 2000 | 0.04s | 0.02s | 1.70 |
| 1000 | 20000 | 0.17s | 0.30s | 0.56 |
| 5000 | 2000 | 0.18s | 0.13s | 1.36 |
| 5000 | 20000 | 0.75s | 1.40s | 0.53 |

The vectorised version wins at small user counts and loses by roughly half at large ones,
where the index matrix stops fitting in cache and the gather becomes memory bound. The
sizes this repository actually runs at are the ones where it loses.

These are durations, so they are facts about one machine. Only the direction of the ratio
is being relied on, and it is consistent across every row at the larger size.

## Alternatives considered

**Ship the vectorised version anyway**, because it looks more numpy-literate. Rejected:
optimising into a slowdown and calling it an optimisation is the failure mode this whole
repository is about, in miniature.

**Ship both and switch on size.** Rejected as complexity bought with a branch nobody would
maintain, for a function that is not the bottleneck in any experiment here.

## Consequences

A reviewer expecting the vectorised idiom will see the loop and may read it as naive. The
docstring points at this file, so the measurement is one hop away. That seemed better than
the alternative, which is being faster-looking and slower.
