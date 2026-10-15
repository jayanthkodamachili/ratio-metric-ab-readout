"""Measure how badly a per-event significance test misreads a per-user experiment.

The package exists because of one asymmetry between what a test computes and what it can
know. A two-sample test on a per-event table performs arithmetic that is correct for
independent observations. When users were randomised, the events belonging to one user are
not independent, and the arithmetic is the same either way. The test returns a well formed
p-value, with a plausible magnitude, computed from a standard error that is too small. No
property of that number reveals the problem, because the problem is in an assumption the
number never encodes.
"""

from ratio_readout.config import ScenarioConfig
from ratio_readout.readout import Readout, read_out

__all__ = ["Readout", "ScenarioConfig", "read_out"]
__version__ = "0.1.0"
