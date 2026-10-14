"""
ONE ENGINE — stage contract.

Every stage: typed input -> typed output + provenance records + honesty marks.
Stages compose: output of one is input of the next, contracts checked at
boundaries. From the council's three syntheses (INN-121/122/123).
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class HonestyMark:
    """Reversed's tri-state, generalized: every stage output carries its
    support grade. CONFIRMED / UNKNOWN / REFUTED. No silent binaries."""
    verdict: str  # CONFIRMED | UNKNOWN | REFUTED
    basis: str    # what was checked
    not_checked: str = ""   # Five's adopted basis format
    breaks_if: str = ""

    def __post_init__(self):
        assert self.verdict in ("CONFIRMED", "UNKNOWN", "REFUTED"), self.verdict


@dataclass
class ProvenanceRecord:
    """Seven's registry, generalized: every transform logged."""
    stage: str
    input_ref: str
    output_ref: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    marks: List[str] = field(default_factory=list)  # [SYNTH] [POLICY] etc.


@dataclass
class StageOutput:
    """What every stage returns."""
    data: Any
    honesty: HonestyMark
    provenance: List[ProvenanceRecord] = field(default_factory=list)


class Stage:
    """Base class. Subclass and implement run()."""
    name: str = "stage"

    def run(self, data: Any) -> StageOutput:
        raise NotImplementedError

    def __call__(self, data: Any) -> StageOutput:
        return self.run(data)
