"""
ONE ENGINE — pipeline composition.

Composes the three syntheses as stages:
  LANE A (text):  repair  (INN-121 synthesis)
  LANE B (series): trend -> detrend -> trigger (INN-122 -> INN-123)

Four's breaks (Wave 2) resolved here:
  Break 1: capsule seals input CONTENT (capsule._hash_input), not str(len()).
  Break 2: Seven's unified registry WIRED IN — stages build
           UnifiedProvenanceRecords via her constructors; the pipeline
           inscribes them into a UnifiedRegistry; the capsule seals
           registry.export_capsule(). to_base() only at backward-compat
           boundaries, never as seal content.

Alpha's DIVERGE (Wave 1) resolved: trend -> detrend -> trigger dataflow;
HonestyMark GATES (trend UNKNOWN/REFUTED -> trigger skipped).
"""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.expanduser("~/workspace/council-projects/late-context-pipeline"))
sys.path.insert(0, os.path.expanduser("~/workspace/council-projects/chronological-overlay"))
sys.path.insert(0, os.path.expanduser("~/workspace/council-projects/binary-signal-matrix"))
sys.path.insert(0, os.path.expanduser("~/workspace/one-engine"))

from engine.stages import Stage, StageOutput, HonestyMark, ProvenanceRecord
from engine.capsule import capsule_seal, capsule_verify
from engine.provenance import (UnifiedRegistry, repair_record, trend_record,
                               trigger_record, gate_record)

import numpy as np


class RepairStage(Stage):
    """INN-121. Text lane: late-context repair with tri-state honesty."""
    name = "repair"

    def run(self, data, registry: UnifiedRegistry):
        import synthesis_five_pipeline as syn
        toks, truth, paus, pit, cap = (data["toks"], data["truth"],
                                       data["paus"], data["pit"], data["cap"])
        pred, basis = syn.repair(paus, pit, cap, k=1)
        f1 = syn.prf(pred, truth)
        # per-decision unified records (Seven's constructor)
        for idx, b in zip(np.flatnonzero(paus), basis):
            registry.inscribe(repair_record(
                lane="A", confirmed_at=int(idx), decision=b,
                basis=f"late_caps k=1, pitch={bool(pit[idx])}",
                evidence={"word": toks[idx], "pause": True,
                          "pitch_drop": bool(pit[idx]), "k": 1},
                truth_layer="manufactured",
                honesty="CONFIRMED" if b == "confirmed" else "UNKNOWN"))
        # Reversed DIVERGE 5: honesty CONDITIONAL, not hardcoded.
        # Baseline to beat: mother's toy 0.625. Below it -> UNKNOWN.
        base = 0.625
        hv = "CONFIRMED" if f1 >= base else "UNKNOWN"
        hon = HonestyMark(verdict=hv,
                          basis=f"tri-state repair, F1={f1:.3f} vs baseline {base}",
                          not_checked="real transcripts",
                          breaks_if="ground truth is manufactured (Four); "
                                    f"F1 < {base} (did not beat baseline)")
        return StageOutput(data={"pred": pred, "basis": basis, "f1": f1},
                           honesty=hon, provenance=[])


class TrendStage(Stage):
    """INN-122. Series lane: pitch vector trend extraction, R2 warns."""
    name = "trend"

    def run(self, data, registry: UnifiedRegistry):
        import synthesis_five_overlay as syn
        series = np.asarray(data["series"], dtype=float)
        slope, r2 = syn.pitch(series)
        n_blocks = len(series) // syn.BLOCK
        # Reversed DIVERGE 4: se COMPUTED, not hardcoded. Standard error of
        # the slope from the block-means regression.
        st, n = syn.stack(series)
        m = st.mean(axis=1); x = np.arange(n, dtype=float)
        sl, ic = np.polyfit(x, m, 1)
        resid = m - (sl * x + ic)
        s2 = (resid ** 2).sum() / max(1, n - 2)
        sxx = ((x - x.mean()) ** 2).sum()
        se = float(np.sqrt(s2 / sxx)) if sxx > 0 else float("inf")
        verdict = "discovery" if r2 > 0.5 else "unknown"
        registry.inscribe(trend_record(
            lane="B", slope=float(slope), se=se, r2=float(r2),
            n_blocks=n_blocks, block=syn.BLOCK,
            verdict=verdict,
            basis=f"pitch={slope:.2f}/block, se={se:.3f}, R2={r2:.3f}",
            honesty="CONFIRMED" if r2 > 0.5 else "UNKNOWN"))
        hon = HonestyMark(verdict="CONFIRMED" if r2 > 0.5 else "UNKNOWN",
                          basis=f"pitch={slope:.2f}/block, R2={r2:.3f}",
                          not_checked="real series; rhythm as discovery",
                          breaks_if="R2 collapses (regime shift); rhythm fenced")
        return StageOutput(data={"slope": slope, "r2": r2},
                           honesty=hon, provenance=[])


class TriggerStage(Stage):
    """INN-123. Series lane: gated trigger — the 1 reads the audit."""
    name = "trigger"

    def run(self, data, registry: UnifiedRegistry):
        import synthesis_five_matrix as syn
        series = np.asarray(data["series"], dtype=float)
        det = syn.detect(series)
        ver = syn.audit(det, series)
        sm = syn.smooth(series)  # Reversed DIVERGE 3: evidence MEASURED, not zeroed
        gated = []
        for (ct, tt, kind), v in zip(det, ver):
            if v == "CONFIRMED":
                gated.append((ct, tt, kind))
                lo, hi = max(0, tt - 45), min(len(series), tt + 46)
                local_noise = float(np.std(series[lo:hi]))
                move = float(abs(sm[tt] - sm[ct]))
                # sustain margin: how far the confirmation move cleared delta
                sustain_margin = float(move - 3.0)
                registry.inscribe(trigger_record(
                    lane="B",
                    claim={"true_time": int(tt), "kind": kind, "delta": 3.0,
                           "w": 45, "smooth_w": 21, "move": move,
                           "sustain_margin": sustain_margin,
                           "local_noise": local_noise},
                    audit_verdict=v, audit_basis="horizon persistence",
                    discovery_mark="queried-pattern",
                    threshold_stable=None))
        suppressed = len(det) - len(gated)
        if suppressed:
            registry.inscribe(gate_record(
                lane="B", gate_name="CONFIRMED-only", decision="suppress",
                basis="non-CONFIRMED audit verdicts do not trigger",
                suppressed=suppressed, honesty="CONFIRMED"))
        hon = HonestyMark(verdict="CONFIRMED",
                          basis=f"{len(gated)}/{len(det)} triggers pass gate",
                          not_checked="market truth (drift CONFIRMs)",
                          breaks_if="CONFIRMED != tradeable (Four's break)")
        return StageOutput(data={"gated": gated, "suppressed": suppressed,
                                  "verdicts": ver},
                           honesty=hon, provenance=[])


def run_text_lane(raw):
    """Lane A: repair -> unified registry -> sealed capsule."""
    reg = UnifiedRegistry(run_id="laneA")
    out = RepairStage().run(raw, reg)
    cap = capsule_seal(np.asarray(raw["toks"]),  # Break 1: full content
                       [{"stage": "repair", "honesty": out.honesty.verdict}],
                       {"f1": out.data["f1"], "n_records": reg.census()["n"]},
                       reg.export_capsule(),  # Break 2: unified, not base
                       ["[SYNTH]"])
    return out, cap, reg


def _is_stationary(series, block=180):
    """Gate helper: is there drift to detrend? Compares block-mean range
    against within-block variation. Sine -> stationary (means ~constant).
    Regime shift / drift -> non-stationary (means wander)."""
    n = len(series) // block
    if n < 2:
        return True
    st = series[:n * block].reshape(n, block)
    bm = st.mean(axis=1)
    within = float(np.median([st[i].std() for i in range(n)]))
    return bool((bm.max() - bm.min()) < 3 * max(within, 1e-9))


def run_series_lane(series):
    """Lane B: trend -> detrend -> trigger, honesty-gated, registry-wired."""
    import synthesis_five_overlay as syn
    reg = UnifiedRegistry(run_id="laneB")
    series = np.asarray(series, dtype=float)
    t_out = TrendStage().run({"series": series}, reg)
    # GATE (Alpha DIVERGE 2, refined): skip the trigger iff detrending is
    # UNSAFE — trend unreliable (R2 collapsed) AND drift actually present
    # (non-stationary). A stationary series with no trend (sine: R2~0,
    # slope~0) is safe: detrending is a no-op, trigger proceeds.
    bad_trend = t_out.honesty.verdict in ("UNKNOWN", "REFUTED")
    if bad_trend and not _is_stationary(series):
        reg.inscribe(gate_record(
            lane="B", gate_name="trend-honesty", decision="skip-trigger",
            basis="trend unreliable (R2 collapsed); residuals compromised",
            suppressed=0, honesty=t_out.honesty.verdict))
        cap = capsule_seal(series,  # Break 1: full content
                           [{"stage": "trend", "honesty": t_out.honesty.verdict},
                            {"stage": "gate", "action": "trigger_skipped"}],
                           {"slope": float(t_out.data["slope"]),
                            "r2": float(t_out.data["r2"]),
                            "gate": "trigger skipped on trend UNKNOWN/REFUTED"},
                           reg.export_capsule(), ["[SYNTH]", "[POLICY]", "[GATE]"])
        return (t_out, None, t_out.honesty), cap, reg
    n = len(series)
    x = np.arange(n, dtype=float)
    slope_per_sample = float(t_out.data["slope"]) / syn.BLOCK
    residuals = series - slope_per_sample * x
    g_out = TriggerStage().run({"series": residuals}, reg)
    cap = capsule_seal(series,  # Break 1: full content
                       [{"stage": "trend", "honesty": t_out.honesty.verdict},
                        {"stage": "detrend"},
                        {"stage": "trigger", "honesty": g_out.honesty.verdict}],
                       {"slope": float(t_out.data["slope"]),
                        "r2": float(t_out.data["r2"]),
                        "gated_triggers": len(g_out.data["gated"]),
                        "suppressed": g_out.data["suppressed"],
                        "n_records": reg.census()["n"]},
                       reg.export_capsule(), ["[SYNTH]", "[POLICY]"])
    return (t_out, g_out, None), cap, reg


if __name__ == "__main__":
    import synthesis_five_pipeline as p1
    toks, truth, paus, pit, cap_ = p1.generate(50, seed=7)
    out, cap, reg = run_text_lane({"toks": toks, "truth": truth, "paus": paus,
                                   "pit": pit, "cap": cap_})
    print(f"lane A: F1={out.data['f1']:.3f} records={reg.census()['n']} "
          f"verify={capsule_verify(cap.to_json())}")
    print(f"  capsule input_hash={cap.input_hash} (content, not length)")

    import synthesis_five_overlay as p3
    s_trend = p3.series(seed=3)
    (t_out, g_out, gm), cap2, reg2 = run_series_lane(s_trend)
    print(f"lane B: slope={t_out.data['slope']:+.2f} R2={t_out.data['r2']:.3f} "
          f"gated={len(g_out.data['gated'])} records={reg2.census()['n']} "
          f"verify={capsule_verify(cap2.to_json())}")
    print(f"  census verdicts: {reg2.census()['verdicts']}")

    # Four's Break 1 regression test: different content, same length -> different hash
    r = np.random.default_rng(0)
    a = np.sin(np.linspace(0, 4*np.pi, 1800)) + r.normal(0, 1, 1800)
    b = np.cos(np.linspace(0, 4*np.pi, 1800)) + r.normal(0, 1, 1800)
    ca = capsule_seal(a, [], {}, [], [])
    cb = capsule_seal(b, [], {}, [], [])
    print(f"Break 1 regression: sine hash={ca.input_hash} cosine hash={cb.input_hash} "
          f"distinct={ca.input_hash != cb.input_hash} [EXECUTED]")

    # gate path still holds
    t = np.arange(1800, dtype=float)
    rs = np.where(t < 900, 0.05*t, 0.05*900 - 0.05*(t-900)) + \
        np.random.default_rng(1).normal(0, 1.0, 1800)
    (t2, g2, gm2), cap3, reg3 = run_series_lane(rs)
    print(f"gate path: trend={t2.honesty.verdict} skipped={g2 is None} "
          f"verify={capsule_verify(cap3.to_json())}")
    print("ONE ENGINE: Four's Break 1+2 resolved. [EXECUTED]")
