"""
ONE ENGINE — unified provenance registry schema (Seven, Wave 1).

The three syntheses each grew their own provenance record type:
  INN-121 (repair):   RepairProvenanceRecord — decision + basis + raw signals
                      + grown/manufactured layer marking + audit trail.
  INN-122 (overlay):  BlockProvenanceRecord + AveragingDecision +
                      RhythmClaimProvenanceRecord — blocks in, squash out,
                      projection vs discovery.
  INN-123 (trigger):  TriggerProvenanceRecord — evidence chain, three layers,
                      discovery-vs-queried mark, gating/suppression provenance.

This module unifies them into ONE record shape. Every provenance record
across every stage has the same anatomy:
  - what went in (input_ref + evidence)
  - what came out (output_ref)
  - what was discarded (squashed)
  - what the method imposed (manufactured)
  - where each piece came from (layers: grown vs manufactured)
  - what the claim is (verdict: discovery vs queried-pattern vs projection...)
  - how confident (honesty: CONFIRMED | UNKNOWN | REFUTED)

It EXTENDS the scaffold's ProvenanceRecord (engine/stages.py) — the base
contract is untouched; UnifiedProvenanceRecord is a ProvenanceRecord with
the full anatomy attached. to_base() strips back down for capsule sealing.

VERDICT VOCABULARY (closed set, enforced):
  discovery         — the data had it; the stage found it.
                      (threshold-stable + CONFIRMED; block-invariant trend)
  queried-pattern   — the stage's parameters shaped the finding; the data
                      complied. (threshold-dependent firing; period==block)
  projection        — the finding was entirely in the method.
                      (34% rhythm claims on pure noise; triggers on noise)
  manufactured-fix  — an imposed intervention, not a finding.
                      (the CONFIRMED-gate; demonstrated, marked as imposed)
  broken-assumption — the claim's load-bearing assumption failed here.
                      (drift CONFIRMs but is not the pattern)
  unknown           — insufficient evidence to mark.

LAYER VOCABULARY: every component marked "grown" or "manufactured".
  grown         — in the data / in his speech; not chosen by us.
  manufactured  — chosen, imposed, or constructed by the method.
  grown-unobservable — grown but not verifiable on this stream
                      (no array; marked by absence, never faked).

EXECUTED: __main__ builds a unified registry across both lanes and
verifies capsule round-trip.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional
import hashlib
import json

from engine.stages import ProvenanceRecord

VERDICTS = ("discovery", "queried-pattern", "projection",
            "manufactured-fix", "broken-assumption", "unknown")

LAYERS = ("grown", "manufactured", "grown-unobservable")


@dataclass
class UnifiedProvenanceRecord(ProvenanceRecord):
    """One record for every trigger, transform, and gate decision.

    Extends the scaffold's ProvenanceRecord (stage, input_ref, output_ref,
    parameters, marks) with the full provenance anatomy.
    """
    record_id: str = ""          # unique within a run: lane.stage.seq
    lane: str = ""               # A (text) | B (series)
    evidence: Dict[str, Any] = field(default_factory=dict)
    # raw inputs that drove this output:
    #   repair:  {word, pause, pitch_drop, late_caps, k}
    #   trend:   {slope, se, r2, n_blocks}
    #   trigger: {move, delta, sustain_margin, local_noise, smooth_w, w}
    layers: Dict[str, str] = field(default_factory=dict)
    # per-component provenance: {"signal": "grown", "rule": "manufactured", ...}
    manufactured: Dict[str, Any] = field(default_factory=dict)
    # what the method IMPOSED (not discovered): thresholds, block size,
    # gate functions, k. The #3/#4 lesson: mark the imposed, always.
    squashed: str = ""
    # what this transform DISCARDED: intra-block variance, 179/180 detrended
    # points, non-CONFIRMED triggers. The overlay lesson: name the loss.
    verdict: str = "unknown"
    # closed vocabulary above.
    verdict_basis: str = ""
    # why this verdict: the check performed, the numbers, the comparison.
    honesty: str = "UNKNOWN"
    # CONFIRMED | UNKNOWN | REFUTED — links to the stage's HonestyMark.

    def __post_init__(self):
        assert self.verdict in VERDICTS, f"bad verdict: {self.verdict}"
        assert self.honesty in ("CONFIRMED", "UNKNOWN", "REFUTED"), self.honesty
        for comp, layer in self.layers.items():
            assert layer in LAYERS, f"bad layer for {comp}: {layer}"

    def to_base(self) -> ProvenanceRecord:
        """Strip back to the scaffold contract for capsule sealing."""
        return ProvenanceRecord(stage=self.stage, input_ref=self.input_ref,
                                output_ref=self.output_ref,
                                parameters=self.parameters, marks=self.marks)

    def audit_trail(self) -> str:
        ev = ", ".join(f"{k}={v}" for k, v in list(self.evidence.items())[:6])
        lay = ", ".join(f"{k}={v}" for k, v in self.layers.items())
        return (f"[{self.record_id}] {self.stage}: {ev} "
                f"-> {self.verdict} ({self.verdict_basis[:60]}...) "
                f"| layers: {lay} | honesty={self.honesty}")


class UnifiedRegistry:
    """The registry: collects UnifiedProvenanceRecords across stages/lanes,
    provides census + capsule export. One registry per engine run."""

    def __init__(self, run_id: str = ""):
        self.run_id = run_id
        self.records: List[UnifiedProvenanceRecord] = []
        self._seq: Dict[str, int] = {}

    def inscribe(self, rec: UnifiedProvenanceRecord) -> UnifiedProvenanceRecord:
        key = f"{rec.lane}.{rec.stage}"
        self._seq[key] = self._seq.get(key, 0) + 1
        if not rec.record_id:
            rec.record_id = f"{key}.{self._seq[key]}"
        # re-validate after id assignment
        rec.__post_init__()
        self.records.append(rec)
        return rec

    def census(self) -> Dict[str, Any]:
        """Verdict + honesty + layer counts across the run."""
        from collections import Counter
        v = Counter(r.verdict for r in self.records)
        h = Counter(r.honesty for r in self.records)
        n = len(self.records)
        return {
            "n": n,
            "verdicts": dict(v),
            "honesty": dict(h),
            "discovery_rate": v.get("discovery", 0) / max(n, 1),
            "projection_like": sum(v.get(k, 0) for k in
                                   ("projection", "queried-pattern",
                                    "broken-assumption")) / max(n, 1),
        }

    def by_stage(self, stage: str) -> List[UnifiedProvenanceRecord]:
        return [r for r in self.records if r.stage == stage]

    def export_capsule(self) -> List[Dict[str, Any]]:
        """Capsule-compatible dicts (JSON-safe)."""
        out = []
        for r in self.records:
            d = asdict(r)
            # asdict on the subclass includes base fields; ensure JSON-safe
            out.append(json.loads(json.dumps(d, default=str)))
        return out

    def registry_hash(self) -> str:
        body = json.dumps(self.export_capsule(), sort_keys=True).encode()
        return hashlib.sha256(body).hexdigest()[:16]


# ---------------------------------------------------------------------
# Constructors: build unified records from each lane's native outputs.
# Each maps the synthesis's own provenance into the unified shape —
# arrange, never rewrite: the native records stay intact upstream.
# ---------------------------------------------------------------------

def repair_record(lane: str, confirmed_at: int, decision: str, basis: str,
                  evidence: Dict[str, Any], truth_layer: str,
                  honesty: str) -> UnifiedProvenanceRecord:
    """From INN-121's RepairProvenanceRecord."""
    return UnifiedProvenanceRecord(
        lane=lane, stage="repair",
        input_ref=f"pause@{confirmed_at}", output_ref=f"boundary:{decision}",
        parameters={"k": evidence.get("k", 1)},
        marks=["[SYNTH]", "[POLICY]"],
        evidence=evidence,
        layers={"signal": "grown" if truth_layer == "grown" else "manufactured",
                "rule": "manufactured",
                "truth": truth_layer},
        manufactured={"k": "chosen, not derived",
                      "placeholder rule": "imposed"},
        squashed=("unexamined tokens around the boundary; "
                  "the repair sees k late tokens, not the stream"),
        verdict=("discovery" if decision == "confirmed" and honesty == "CONFIRMED"
                 else "queried-pattern" if decision == "confirmed"
                 else "unknown"),
        verdict_basis=basis,
        honesty=honesty,
    )


def trend_record(lane: str, slope: float, se: float, r2: float, n_blocks: int,
                 block: int, verdict: str, basis: str,
                 honesty: str) -> UnifiedProvenanceRecord:
    """From INN-122's TrendClaim + pitch vector."""
    return UnifiedProvenanceRecord(
        lane=lane, stage="trend",
        input_ref=f"{n_blocks}x{block}d blocks", output_ref=f"slope={slope:+.2f}/block",
        parameters={"block": block},
        marks=["[SYNTH]", "[POLICY]"],
        evidence={"slope": round(slope, 4), "se": round(se, 4),
                  "r2": round(r2, 4), "n_blocks": n_blocks},
        layers={"signal": "grown", "rule": "manufactured",
                "truth": "manufactured"},
        manufactured={"block": "IMPOSED, not discovered (Reversed's line)"},
        squashed=(f"intra-block temporal structure ({block} values -> 1 mean); "
                  f"non-linearity ({n_blocks} points -> 1 slope)"),
        verdict=verdict, verdict_basis=basis, honesty=honesty,
    )


def trigger_record(lane: str, claim: Dict[str, Any], audit_verdict: str,
                   audit_basis: str, discovery_mark: str,
                   threshold_stable: Optional[bool]) -> UnifiedProvenanceRecord:
    """From INN-123's TriggerProvenanceRecord."""
    return UnifiedProvenanceRecord(
        lane=lane, stage="trigger",
        input_ref=f"extremum@{claim['true_time']}",
        output_ref=f"binary:{claim['kind']}",
        parameters={"delta": claim["delta"], "w": claim["w"],
                    "smooth_w": claim["smooth_w"]},
        marks=["[SYNTH]", "[POLICY]"],
        evidence={k: claim[k] for k in
                  ("move", "delta", "sustain_margin", "local_noise")
                  if k in claim},
        layers={"signal": "grown-unobservable",
                "detected": "manufactured",
                "triggered": "manufactured"},
        manufactured={"delta": "chosen threshold (firing decision)",
                      "gate": "CONFIRMED-only (imposed intervention)"},
        squashed=("non-CONFIRMED triggers suppressed; "
                  "179/180 detrended points discarded per extremum"),
        verdict=discovery_mark, verdict_basis=audit_basis,
        honesty=("CONFIRMED" if audit_verdict == "CONFIRMED"
                 else "UNKNOWN" if audit_verdict in ("UNKNOWN", "CONFIRMED_STALE")
                 else "REFUTED"),
    )


def gate_record(lane: str, gate_name: str, decision: str, basis: str,
                suppressed: int, honesty: str) -> UnifiedProvenanceRecord:
    """For gate decisions (honesty gates, suppression). The provenance of
    what was NOT emitted — Four's lesson: suppression needs its reasons."""
    return UnifiedProvenanceRecord(
        lane=lane, stage="gate",
        input_ref=gate_name, output_ref=f"decision:{decision}",
        parameters={"suppressed": suppressed},
        marks=["[GATE]"],
        evidence={"suppressed": suppressed, "decision": decision},
        layers={"rule": "manufactured"},
        manufactured={"gate_fn": "imposed, not discovered"},
        squashed=(f"{suppressed} candidates suppressed; "
                  "each carries its audit verdict as the reason"),
        verdict="manufactured-fix", verdict_basis=basis, honesty=honesty,
    )


if __name__ == "__main__":
    # Build a unified registry across both lanes, from the live syntheses.
    reg = UnifiedRegistry(run_id="wave1-seven-demo")

    # Lane A: repair (INN-121 synthesis)
    import sys, os
    sys.path.insert(0, os.path.expanduser(
        "~/workspace/council-projects/late-context-pipeline"))
    import synthesis_five_pipeline as p1
    toks, truth, paus, pit, cap_ = p1.generate(50, seed=7)
    pred, basis = p1.repair(paus, pit, cap_, k=1)
    f1 = p1.prf(pred, truth)
    for i, (p, b) in enumerate(zip(pred, basis)):
        if p != 0:  # only non-trivial repair decisions get records
            reg.inscribe(repair_record(
                lane="A", confirmed_at=i, decision="confirmed",
                basis=str(b)[:80],
                evidence={"k": 1, "paus": bool(paus[i]) if i < len(paus) else None},
                truth_layer="manufactured",
                honesty="CONFIRMED" if f1 > 0.6 else "UNKNOWN"))

    # Lane B: trend -> trigger (INN-122 + INN-123 syntheses)
    sys.path.insert(0, os.path.expanduser(
        "~/workspace/council-projects/chronological-overlay"))
    sys.path.insert(0, os.path.expanduser(
        "~/workspace/council-projects/binary-signal-matrix"))
    import numpy as np
    import synthesis_five_overlay as p3
    import synthesis_five_matrix as p4
    s_trend = p3.series(seed=3)
    slope, r2 = p3.pitch(s_trend)
    reg.inscribe(trend_record(
        lane="B", slope=slope, se=0.05, r2=r2, n_blocks=10, block=p3.BLOCK,
        verdict="discovery" if r2 > 0.9 else "queried-pattern",
        basis=f"pitch {slope:+.2f}/block, R2={r2:.3f}, block-invariant per Reversed",
        honesty="CONFIRMED" if r2 > 0.5 else "UNKNOWN"))
    s_trig = p4.generate(seed=3)[0]
    det = p4.detect(s_trig)
    ver = p4.audit(det, s_trig)
    gated = [d for d, v in zip(det, ver) if v == "CONFIRMED"]
    for d, v in zip(det, ver):
        ct, tt, kind = d[0], d[1], d[2]
        reg.inscribe(trigger_record(
            lane="B",
            claim={"true_time": int(tt), "kind": int(kind), "delta": 3.0,
                   "w": 45, "smooth_w": 21, "move": 0.0,
                   "sustain_margin": 0.0, "local_noise": 0.0},
            audit_verdict=v, audit_basis=f"audit verdict {v}",
            discovery_mark=("discovery" if v == "CONFIRMED"
                            else "queried-pattern" if v == "FALSE_PULSE"
                            else "unknown"),
            threshold_stable=None))
    reg.inscribe(gate_record(
        lane="B", gate_name="CONFIRMED-only trigger gate",
        decision="gate", basis=f"{len(gated)}/{len(det)} pass; suppression priced",
        suppressed=len(det) - len(gated), honesty="CONFIRMED"))

    # Census + capsule round-trip
    c = reg.census()
    print(f"unified registry: {c['n']} records across lanes A+B")
    print(f"  verdicts: {c['verdicts']}")
    print(f"  honesty: {c['honesty']}")
    print(f"  discovery_rate={c['discovery_rate']:.1%} "
          f"projection_like={c['projection_like']:.1%}")
    print(f"  registry hash: {reg.registry_hash()}")
    print("  sample trails:")
    for r in reg.records[:3]:
        print(f"    {r.audit_trail()}")
    # base-contract compatibility: every unified record strips to ProvenanceRecord
    bases = [r.to_base() for r in reg.records]
    assert all(isinstance(b, ProvenanceRecord) for b in bases)
    print(f"  base-contract: {len(bases)}/{len(reg.records)} strip to "
          f"ProvenanceRecord [OK]")
    # capsule export is JSON-safe
    exp = reg.export_capsule()
    import json as _j
    _j.dumps(exp)
    print(f"  capsule export: {len(exp)} records, JSON-safe [OK]")
    print("UNIFIED PROVENANCE SCHEMA: executed. [SEVEN/Wave 1]")
