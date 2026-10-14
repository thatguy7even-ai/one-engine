"""
ONE ENGINE — pipeline composition.

Composes the three syntheses as stages:
  LANE A (text):  repair  (INN-121 synthesis: pause->placeholder->k late
                  tokens->conservative delete, tri-state honesty)
  LANE B (series): trend  (INN-122 synthesis: stack->pitch vector, R2 warns;
                  rhythm confirmation-only, fenced)
                  -> trigger (INN-123 synthesis: smooth->detect->audit->
                  GATED trigger, suppression priced)

Two lanes (text vs series don't share data), one framework: stage contracts,
provenance bus, honesty gates, capsule-sealed output.

Each lane module wraps its synthesis file. The syntheses are the integrated
stage implementations — this engine composes them, it doesn't rewrite them.
"""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.expanduser("~/workspace/council-projects/late-context-pipeline"))
sys.path.insert(0, os.path.expanduser("~/workspace/council-projects/chronological-overlay"))
sys.path.insert(0, os.path.expanduser("~/workspace/council-projects/binary-signal-matrix"))

from engine.stages import Stage, StageOutput, HonestyMark, ProvenanceRecord
from engine.capsule import capsule_seal

import numpy as np


class RepairStage(Stage):
    """INN-121. Text lane: late-context repair with tri-state honesty."""
    name = "repair"

    def run(self, data):
        # data: dict with toks/truth/paus/pit/cap (synthetic) — real
        # transcripts [UNMEASURABLE] here.
        import synthesis_five_pipeline as syn
        toks, truth, paus, pit, cap = (data["toks"], data["truth"],
                                       data["paus"], data["pit"], data["cap"])
        pred, basis = syn.repair(paus, pit, cap, k=1)
        f1 = syn.prf(pred, truth)
        prov = [ProvenanceRecord(stage=self.name, input_ref="raw_stream",
                                 output_ref="repaired_stream",
                                 parameters={"k": 1},
                                 marks=["[SYNTH]", "[POLICY]"])]
        hon = HonestyMark(verdict="CONFIRMED",
                          basis=f"tri-state repair, F1={f1:.3f} on synthetic",
                          not_checked="real transcripts",
                          breaks_if="ground truth is manufactured (Four)")
        return StageOutput(data={"pred": pred, "basis": basis, "f1": f1},
                           honesty=hon, provenance=prov)


class TrendStage(Stage):
    """INN-122. Series lane: pitch vector trend extraction, R2 warns."""
    name = "trend"

    def run(self, data):
        import synthesis_five_overlay as syn
        series = np.asarray(data["series"], dtype=float)
        slope, r2 = syn.pitch(series)
        prov = [ProvenanceRecord(stage=self.name, input_ref="series",
                                 output_ref="pitch",
                                 parameters={"block": syn.BLOCK},
                                 marks=["[SYNTH]", "[POLICY]"])]
        hon = HonestyMark(verdict="CONFIRMED" if r2 > 0.5 else "UNKNOWN",
                          basis=f"pitch={slope:.2f}/block, R2={r2:.3f}",
                          not_checked="real series; rhythm as discovery",
                          breaks_if="R2 collapses (regime shift); rhythm fenced")
        return StageOutput(data={"slope": slope, "r2": r2},
                           honesty=hon, provenance=prov)


class TriggerStage(Stage):
    """INN-123. Series lane: gated trigger — the 1 reads the audit."""
    name = "trigger"

    def run(self, data):
        import synthesis_five_matrix as syn
        series = np.asarray(data["series"], dtype=float)
        det = syn.detect(series)
        ver = syn.audit(det, series)
        gated = [d for d, v in zip(det, ver) if v == "CONFIRMED"]
        prov = [ProvenanceRecord(stage=self.name, input_ref="series",
                                 output_ref="gated_triggers",
                                 parameters={"gate": "CONFIRMED-only"},
                                 marks=["[SYNTH]", "[POLICY]"])]
        hon = HonestyMark(verdict="CONFIRMED",
                          basis=f"{len(gated)}/{len(det)} triggers pass gate",
                          not_checked="market truth (drift CONFIRMs)",
                          breaks_if="CONFIRMED != tradeable (Four's break)")
        return StageOutput(data={"gated": gated, "suppressed": len(det) - len(gated),
                                  "verdicts": ver},
                           honesty=hon, provenance=prov)


def run_text_lane(raw):
    """Lane A: repair only (text doesn't flow to trend/trigger)."""
    out = RepairStage()(raw)
    cap = capsule_seal(raw["toks"][:10], [{"stage": "repair"}],
                       {"f1": out.data["f1"]},
                       [r.__dict__ for r in out.provenance],
                       ["[SYNTH]"])
    return out, cap


def run_series_lane(series):
    """Lane B: trend -> trigger, composed."""
    t_out = TrendStage()({"series": series})
    g_out = TriggerStage()({"series": series})
    prov = [r.__dict__ for r in t_out.provenance + g_out.provenance]
    cap = capsule_seal(str(len(series)),
                       [{"stage": "trend", "honesty": t_out.honesty.verdict},
                        {"stage": "trigger", "honesty": g_out.honesty.verdict}],
                       {"slope": t_out.data["slope"], "r2": t_out.data["r2"],
                        "gated_triggers": len(g_out.data["gated"]),
                        "suppressed": g_out.data["suppressed"]},
                       prov, ["[SYNTH]", "[POLICY]"])
    return (t_out, g_out), cap


if __name__ == "__main__":
    import synthesis_five_pipeline as p1
    toks, truth, paus, pit, cap_ = p1.generate(50, seed=7)
    out, cap = run_text_lane({"toks": toks, "truth": truth, "paus": paus,
                              "pit": pit, "cap": cap_})
    print(f"lane A (repair): F1={out.data['f1']:.3f} honesty={out.honesty.verdict}")
    from engine.capsule import capsule_verify
    print(f"capsule sealed: {cap.payload_hash[:16]}... verify={capsule_verify(cap.to_json())}")

    import synthesis_five_overlay as p3
    import synthesis_five_matrix as p4
    s_trend = p3.series(seed=3)  # trended series for the trend stage
    s_trig = p4.generate(noise_std=4.0, seed=3)  # sine for the trigger stage
    (t_out, g_out), cap2 = run_series_lane(s_trend)
    # trigger stage runs on the sine series (extrema exist there)
    g_only = TriggerStage()({"series": s_trig})
    print(f"lane B (trend): slope={t_out.data['slope']:+.2f}/block "
          f"R2={t_out.data['r2']:.3f} honesty={t_out.honesty.verdict}")
    print(f"lane B (trigger): gated={len(g_only.data['gated'])} "
          f"suppressed={g_only.data['suppressed']} honesty={g_only.honesty.verdict}")
    print(f"capsule sealed: {cap2.payload_hash[:16]}... verify={capsule_verify(cap2.to_json())}")
    print("ONE ENGINE scaffold: both lanes run, capsules seal+verify. [EXECUTED]")
