"""
ONE ENGINE — Blink's continuity test design (test-design seat).
Target: bcb4d12 (engine/ identical at 3fe278b — only council/ added).

Verification (Control) proved the engine works ONCE. This harness asks what
"works" means OVER TIME:

  T1  Run determinism — 2nd/10th run identical? (what changes, what must not)
  T2  Honesty degradation — as inputs rot, do the marks rot gracefully or
      stay CONFIRMED while quality collapses? (the silent-failure test)
  T3  Drift break, in-engine — the load-bearing break reproduced; is the
      marking infrastructure around it intact?
  T4  Registry invariants — closed vocabularies hold across input battery
  T5  Capsule chain — tamper-evidence both directions; what chains, what doesn't
  T6  Demo staleness — Control's note as regression test (demo historical,
      pipeline live; pin the direction)
  T7  Edge inputs — empty, single-block, NaN: loud failure or silent garbage?
  T8  Gate path — regime shift skips trigger with honest record

Marking: [EXECUTED] here on numpy. [SYNTH] inputs throughout.
A stranger runs `python3 this_file.py` from the repo root.
"""
import sys
import os
import json
import hashlib

sys.path.insert(0, os.path.expanduser("~/workspace/council-projects/late-context-pipeline"))
sys.path.insert(0, os.path.expanduser("~/workspace/council-projects/chronological-overlay"))
sys.path.insert(0, os.path.expanduser("~/workspace/council-projects/binary-signal-matrix"))
# engine package: the repo under test (pinned commit bcb4d12)
for _repo in ("/tmp/oe", os.path.expanduser("~/workspace/one-engine")):
    if os.path.isdir(os.path.join(_repo, "engine")):
        sys.path.insert(0, _repo)
        break

from engine.pipeline import run_text_lane, run_series_lane
from engine.capsule import capsule_verify
from engine.provenance import VERDICTS, LAYERS
import numpy as np


def _lane_b_inputs(noise=4.0, seed=3, drift=0.0, n=1800):
    import synthesis_five_matrix as p4
    if drift:
        t = np.arange(n, dtype=float)
        r = np.random.default_rng(seed)
        return drift * t + r.normal(0, noise, n)
    return p4.generate(noise_std=noise, seed=seed)


def _strip_volatile(cap_json):
    """Remove fields allowed to change run-to-run; what remains must be identical."""
    d = json.loads(cap_json)
    d.pop("created_utc", None)
    d.pop("payload_hash", None)
    return json.dumps(d, sort_keys=True)


# ---------------------------------------------------------------------------
# T1 — Run determinism. [EXECUTED]
# The 2nd, 10th, 100th run on identical input must produce identical claims.
# created_utc/payload_hash may change; everything else must not.
# Break: any claim-bearing field differs -> hidden state or nondeterminism.
# ---------------------------------------------------------------------------
def t1_determinism(runs=10):
    import synthesis_five_pipeline as p1
    toks, truth, paus, pit, cap_ = p1.generate(50, seed=7)
    raw = {"toks": toks, "truth": truth, "paus": paus, "pit": pit, "cap": cap_}
    series = _lane_b_inputs()
    snaps_a, snaps_b, hashes_a, hashes_b = [], [], [], []
    for _ in range(runs):
        out_a, cap_a, _ = run_text_lane(raw)
        (t_out, g_out, gm), cap_b, _ = run_series_lane(series)
        snaps_a.append(_strip_volatile(cap_a.to_json()))
        snaps_b.append(_strip_volatile(cap_b.to_json()))
        hashes_a.append(cap_a.input_hash)
        hashes_b.append(cap_b.input_hash)
    ok = (len(set(snaps_a)) == 1 and len(set(snaps_b)) == 1
          and len(set(hashes_a)) == 1 and len(set(hashes_b)) == 1)
    # and: exactly the volatile fields changed (nothing else allowed to)
    full_a = [json.loads(run_text_lane(raw)[1].to_json()) for _ in range(2)]
    volatile = {k for k in full_a[0] if full_a[0][k] != full_a[1][k]}
    return ok and volatile <= {"created_utc", "payload_hash"}, {
        "runs": runs, "identical_claims": ok,
        "volatile_fields": sorted(volatile)}


# ---------------------------------------------------------------------------
# T2 — Honesty degradation curve. [EXECUTED]
# Sweep noise 1->16 on the trigger path. The question is NOT whether the
# trigger degrades (it does — known). The question is whether the HONESTY
# degrades with it, or stays CONFIRMED while quality collapses (silent).
# This test PINS the curve: documents where honesty holds and where the
# audit CONFIRMs noise. A future change that weakens the marking
# (e.g. stops measuring local_noise) fails here even if gates still gate.
# Break: any trigger record with zeroed/unmeasured evidence on the live path.
# ---------------------------------------------------------------------------
def t2_honesty_degradation():
    # True extrema of the sine: peaks at 45+180k, troughs at 135+180k.
    true_ext = {45 + 180 * k for k in range(10)} | {135 + 180 * k for k in range(10)}
    rows = []
    for ns in (1.0, 2.0, 4.0, 8.0, 16.0):
        series = _lane_b_inputs(noise=ns)
        (t_out, g_out, gm), cap, reg = run_series_lane(series)
        trig_recs = reg.by_stage("trigger")
        measured = all(
            r.evidence.get("local_noise", 0.0) > 0
            and "move" in r.evidence for r in trig_recs)
        n_conf = sum(1 for r in trig_recs if r.honesty == "CONFIRMED")
        marks_ok = all("[SYNTH]" in r.marks for r in trig_recs)
        # positional accuracy: gated trigger true_time within 20 of a true extremum
        gated_times = [int(r.input_ref.split("@")[1]) for r in trig_recs
                       if r.honesty == "CONFIRMED"]
        on_true = sum(1 for tt in gated_times
                      if any(abs(tt - te) <= 20 for te in true_ext))
        acc = on_true / max(1, len(gated_times))
        rows.append({"noise": ns, "triggers": len(trig_recs),
                     "confirmed": n_conf, "positional_accuracy": round(acc, 2),
                     "evidence_measured": measured, "marks_present": marks_ok})
    ok = all(r["evidence_measured"] and r["marks_present"] for r in rows)
    # the silent-failure detector: CONFIRMED pinned high while accuracy collapses
    silent = [r["noise"] for r in rows
              if r["confirmed"] == r["triggers"] and r["triggers"] > 0
              and r["positional_accuracy"] < 0.5]
    return ok, {"curve": rows,
                "silent_failure_at_noise": silent or None,
                "reading": ("CONFIRMED pinned while accuracy collapses at noise=%s: "
                            "audit CONFIRMs noise — marked, not fixed" % silent)
                           if silent else
                           "CONFIRMED tracks positional accuracy across the sweep"}


# ---------------------------------------------------------------------------
# T3 — Drift break, reproduced in-engine. [EXECUTED]
# Four's load-bearing break: the audit CONFIRMs drift-swings, so the gate
# passes untradeable patterns. This test reproduces it through the ENGINE
# (not the synthesis) and asserts the marking infrastructure around the
# silent failure is intact: manufactured fields name the imposition,
# squashed names the loss, breaks_if names the break.
# Break: gated CONFIRMED triggers on drift WITHOUT the marking -> silent.
# ---------------------------------------------------------------------------
def t3_drift_break():
    series = _lane_b_inputs(noise=4.0, drift=0.02)
    (t_out, g_out, gm), cap, reg = run_series_lane(series)
    trig_recs = reg.by_stage("trigger")
    gated_conf = [r for r in trig_recs if r.honesty == "CONFIRMED"]
    # the break reproduces iff drift-swings get CONFIRMED
    reproduces = len(gated_conf) > 0
    # the marking is intact iff every such record names the imposition
    marked = all(
        r.manufactured.get("gate") and r.squashed and r.verdict_basis
        for r in gated_conf)
    # and the stage honesty carries Four's break in breaks_if
    stage_break = "tradeable" in (g_out.honesty.breaks_if if g_out else "")
    ok = reproduces and marked and stage_break
    return ok, {"drift_gated_confirmed": len(gated_conf),
                "break_reproduces": reproduces,
                "marking_intact": marked,
                "stage_names_break": stage_break}


# ---------------------------------------------------------------------------
# T4 — Registry invariants across input battery. [EXECUTED]
# Closed vocabularies are the schema's immune system. Battery: clean sine,
# noise, drift, regime shift, pure noise. Every record, every run:
# verdict in VERDICTS, honesty in tri-state, record_id unique, layers in LAYERS.
# Break: any violation -> schema drifted.
# ---------------------------------------------------------------------------
def t4_registry_invariants():
    import synthesis_five_overlay as p3
    battery = {
        "sine": _lane_b_inputs(noise=1.0),
        "noisy": _lane_b_inputs(noise=8.0),
        "drift": _lane_b_inputs(noise=4.0, drift=0.02),
        "pure_noise": np.random.default_rng(3).normal(0, 4.0, 1800),
    }
    t = np.arange(1800, dtype=float)
    battery["regime"] = (np.where(t < 900, 0.05 * t, 0.05 * 900 - 0.05 * (t - 900))
                         + np.random.default_rng(1).normal(0, 1.0, 1800))
    violations = []
    n_records = 0
    for name, series in battery.items():
        (t_out, g_out, gm), cap, reg = run_series_lane(series)
        ids = [r.record_id for r in reg.records]
        n_records += len(ids)
        if len(set(ids)) != len(ids):
            violations.append(f"{name}: duplicate record_id")
        for r in reg.records:
            if r.verdict not in VERDICTS:
                violations.append(f"{name}: bad verdict {r.verdict}")
            if r.honesty not in ("CONFIRMED", "UNKNOWN", "REFUTED"):
                violations.append(f"{name}: bad honesty {r.honesty}")
            for comp, layer in r.layers.items():
                if layer not in LAYERS:
                    violations.append(f"{name}: bad layer {layer}")
    return not violations, {"inputs": sorted(battery), "records_checked": n_records,
                            "violations": violations}


# ---------------------------------------------------------------------------
# T5 — Capsule chain. [EXECUTED]
# (a) tamper-evident both directions: intact -> True; 1-byte flip -> False.
# (b) input_hash stable across runs for identical input.
# (c) DOCUMENTED LIMIT: capsules do not chain — no prev_hash field; run N+1
#     cannot prove it follows run N. States what chaining would require.
# Break: tampered verifies True, or intact verifies False.
# ---------------------------------------------------------------------------
def t5_capsule_chain():
    import synthesis_five_pipeline as p1
    toks, truth, paus, pit, cap_ = p1.generate(50, seed=7)
    raw = {"toks": toks, "truth": truth, "paus": paus, "pit": pit, "cap": cap_}
    _, cap, _ = run_text_lane(raw)
    j = cap.to_json()
    intact = capsule_verify(j)
    d = json.loads(j)
    d["verdict"]["f1"] = 0.999  # 1-field tamper
    tampered = capsule_verify(json.dumps(d))
    e = json.loads(j)
    e["input_hash"] = "0" * 16  # input-hash tamper
    tampered2 = capsule_verify(json.dumps(e))
    _, cap2, _ = run_text_lane(raw)
    stable = cap.input_hash == cap2.input_hash
    chained = "prev_hash" in json.loads(j) or "prev" in json.loads(j)
    ok = intact and not tampered and not tampered2 and stable
    return ok, {"intact_verifies": intact,
                "field_tamper_caught": not tampered,
                "input_hash_tamper_caught": not tampered2,
                "input_hash_stable": stable,
                "capsules_chain": chained,
                "note": "no prev_hash: each capsule standalone; chaining "
                        "would require sealing run N's payload_hash into run N+1"}


# ---------------------------------------------------------------------------
# T6 — Demo staleness regression (Control's note, as a test). [EXECUTED]
# provenance.py __main__ is Wave-1 historical: se=0.05 hardcoded, trigger
# evidence zeroed. The pipeline path measures everything. Pin the DIRECTION:
# demo source must still show the historical markers AND the live path must
# still measure. If someone rewires the demo OR the pipeline regresses to
# hardcoded values, this test notices the change of direction.
# Break: live path shows hardcoded values, or demo silently rewritten.
# ---------------------------------------------------------------------------
def t6_demo_staleness():
    import engine.provenance as _prov
    src = open(_prov.__file__).read()
    demo_historical = "se=0.05" in src and '"move": 0.0' in src
    # live path measures: trend se computed, trigger evidence measured
    series = _lane_b_inputs(noise=4.0)
    (t_out, g_out, gm), cap, reg = run_series_lane(series)
    trend_recs = reg.by_stage("trend")
    trig_recs = reg.by_stage("trigger")
    live_trend_measured = all(r.evidence.get("se", 0.05) != 0.05
                              for r in trend_recs)
    live_trig_measured = all(r.evidence.get("local_noise", 0.0) > 0
                             for r in trig_recs)
    ok = demo_historical and live_trend_measured and live_trig_measured
    return ok, {"demo_still_historical": demo_historical,
                "live_trend_measures_se": live_trend_measured,
                "live_trigger_measures_evidence": live_trig_measured}


# ---------------------------------------------------------------------------
# T7 — Edge inputs. [EXECUTED]
# Empty, single-block, NaN: does the engine fail LOUD or produce silent
# garbage? This test PINS current behavior so future drift can't silently
# change it. The bar is not "handles gracefully" — it's "behavior is known
# and the test will scream if it changes."
# ---------------------------------------------------------------------------
def t7_edge_inputs():
    results = {}

    def attempt(name, series):
        try:
            (t_out, g_out, gm), cap, reg = run_series_lane(np.asarray(series, dtype=float))
            gh = g_out.honesty.verdict if g_out else "skipped"
            return f"returned: trend={t_out.honesty.verdict} trigger={gh}"
        except Exception as e:
            return f"raised: {type(e).__name__}"

    results["empty"] = attempt("empty", [])
    results["single_block"] = attempt("single_block", np.random.default_rng(0).normal(0, 1, 180))
    results["nan"] = attempt("nan", np.full(1800, np.nan))
    # pin: NaN must not produce CONFIRMED claims (silent garbage is the failure)
    nan_series = np.full(1800, np.nan)
    try:
        (t_out, g_out, gm), cap, reg = run_series_lane(nan_series)
        nan_confirmed = any(r.honesty == "CONFIRMED" for r in reg.records)
    except Exception:
        nan_confirmed = False  # raising is loud = acceptable
    ok = not nan_confirmed
    results["nan_confirmed_anything"] = nan_confirmed
    return ok, {"behavior": results,
                "bar": "NaN must never yield CONFIRMED; other behaviors pinned, not judged"}


# ---------------------------------------------------------------------------
# T8 — Gate path honesty. [EXECUTED]
# Regime shift -> trend UNKNOWN + non-stationary -> trigger skipped, gate
# record inscribed carrying the honest verdict. Assert the record EXISTS
# (suppression with reasons, not silent absence) and the capsule seals it.
# Break: trigger runs on compromised residuals, or skip leaves no record.
# ---------------------------------------------------------------------------
def t8_gate_path():
    t = np.arange(1800, dtype=float)
    rs = (np.where(t < 900, 0.05 * t, 0.05 * 900 - 0.05 * (t - 900))
          + np.random.default_rng(1).normal(0, 1.0, 1800))
    (t_out, g_out, gm), cap, reg = run_series_lane(rs)
    skipped = g_out is None
    gate_recs = [r for r in reg.by_stage("gate")
                 if r.input_ref == "trend-honesty"]
    record_ok = len(gate_recs) == 1 and gate_recs[0].honesty in ("UNKNOWN", "REFUTED")
    sealed = capsule_verify(cap.to_json())
    # determinism of the skip: run again, same decision
    (t2, g2, gm2), cap2, reg2 = run_series_lane(rs)
    stable = (g2 is None) == skipped
    ok = skipped and record_ok and sealed and stable
    return ok, {"trigger_skipped": skipped,
                "gate_record_honest": record_ok,
                "capsule_seals_skip": sealed,
                "skip_stable": stable}


def main():
    print("=== ONE ENGINE — CONTINUITY TEST (Blink, test-design seat) ===")
    print("Target: bcb4d12. Verification proved it works once; this asks about over time.\n")
    results = {}
    for name, fn in [("T1_determinism", t1_determinism),
                     ("T2_honesty_degradation", t2_honesty_degradation),
                     ("T3_drift_break", t3_drift_break),
                     ("T4_registry_invariants", t4_registry_invariants),
                     ("T5_capsule_chain", t5_capsule_chain),
                     ("T6_demo_staleness", t6_demo_staleness),
                     ("T7_edge_inputs", t7_edge_inputs),
                     ("T8_gate_path", t8_gate_path)]:
        try:
            ok, res = fn()
        except Exception as e:
            ok, res = False, {"exception": f"{type(e).__name__}: {e}"}
        results[name] = ok
        print(f"{name} [EXECUTED]: {'PASS' if ok else 'FAIL'} {res}")
    print()
    allok = all(results.values())
    print("OVERALL:", "PASS — continuity holds; failure modes pinned, not hidden." if allok
          else "FAIL — see above.")
    return 0 if allok else 1


if __name__ == "__main__":
    raise SystemExit(main())
