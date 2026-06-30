#!/usr/bin/env python3
"""Offline promotion-decision gate for the audit-first harness (v0.2, milestone 1).

Turns the existing audit/reporting artifacts into one machine-readable decision:

    PROMOTE | BLOCK | REVISE | HUMAN_REVIEW

written to `docs/promotion/<Target>.yaml`.

This script is **pure and offline**:
  - it calls no model/API and runs neither Lean nor the Comparator;
  - it only *reads* existing local artifacts and *writes* under `docs/promotion/`;
  - it never mutates mappings, reviews, mutants, or judge results.

Core principle (see PROJECT_CONTEXT.md): **mutation recall and the consistency
false-alarm rate measure judge reliability, not theorem truth.** A missed discriminative
mutant is calibration evidence about the judge — it caps confidence and forces HUMAN_REVIEW;
it is not, by itself, an infrastructure failure nor proof that the real mapping is wrong.

Decision policy (deterministic, ordered — see PROJECT_CONTEXT.md):
  1. hard formal/integrity failure            -> BLOCK
  2. real-mapping FAIL / WARN / not-accepted  -> REVISE (FAIL) or HUMAN_REVIEW (WARN/other)
  3. weak judge calibration OR unverified formal status -> HUMAN_REVIEW (confidence capped)
  4. everything verified and within thresholds -> PROMOTE

Inputs (all optional except the mapping; missing critical inputs are reported, never guessed):
  docs/formal_mapping.yaml                     target, declaration, comparator_status, approval
  docs/theorem_index.yaml                      source-card presence
  docs/fidelity_reviews/<Target>.md            frontmatter approval
  docs/judge_results/<Target>_scored.yaml      fidelity + parse-format metrics, real-row verdict
  docs/judge_inputs_dryrun/_manifest.yaml      prompt_sha256 / mutants_sha256 for provenance match
  docs/pipeline_status.json (preferred) OR docs/pipeline_report.md  build / no_sorry / comparator
  --judge-metrics <summary.json> (optional)    structured judge-scoring summary (v0.3 1c, §10.3);
                                               conservative-only: may cap an otherwise-promotable
                                               target to HUMAN_REVIEW, never BLOCK or PROMOTE
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
except ModuleNotFoundError:
    sys.stderr.write("ERROR: PyYAML is required. Install it with: python -m pip install pyyaml\n")
    sys.exit(2)

ROOT = Path(__file__).resolve().parent.parent

# Structured pipeline-status schema this gate understands (mirrors rebuild_pipeline.py). The
# structured status is *formal* evidence only; it never establishes source fidelity.
PIPELINE_STATUS_SCHEMA = "pipeline_status.v0.1"
REQUIRED_FORMAL_STAGES = {"build", "no_sorry", "axiom_audit", "equivalence_check", "comparator"}

PROMOTE, BLOCK, REVISE, HUMAN_REVIEW = "PROMOTE", "BLOCK", "REVISE", "HUMAN_REVIEW"

# Verdict buckets (kept in sync with score_judge.py).
ACCEPT = {"PASS", "PASS_EQUIV", "PASS_PROVABLE_EQUIV"}

# Comparator statuses recorded in formal_mapping.yaml (see PROJECT_CONTEXT.md).
COMPARATOR_REAL = {"PASSED_REAL_LANDRUN", "PASSED_REAL_LANDRUN_BEST_EFFORT"}
COMPARATOR_BEST_EFFORT = "PASSED_REAL_LANDRUN_BEST_EFFORT"
COMPARATOR_FAKE = "PASSED_FAKE_LANDRUN"
COMPARATOR_FAILED = "FAILED_COMPARATOR"

DEFAULT_THRESHOLDS = {
    "min_recall": 1.0,
    "max_far": 0.0,
    "max_malformed": 0.0,
}

# Judge-metric status for the optional structured-scoring summary (v0.3 milestone 1c).
JM_NOT_RUN, JM_PRESENT, JM_INVALID = "NOT_RUN", "PRESENT", "INVALID"

# Conservative thresholds for the optional *structured* judge-scoring summary
# (scripts/score_judge.py --structured, schema v0.3 §10.3). These mirror the strict legacy
# thresholds above: any imperfection in judge reliability caps an otherwise-promotable target to
# HUMAN_REVIEW. They never BLOCK and never PROMOTE on their own (PROJECT_CONTEXT.md).
# A metric that is `None` (not measured — e.g. no consistency variants) never triggers a cap.
DEFAULT_JUDGE_METRIC_THRESHOLDS = {
    "min_schema_valid_rate": 1.0,
    "max_invalid_rate": 0.0,
    "max_unparseable_rate": 0.0,
    "min_discriminative_recall": 1.0,
    "max_false_acceptance_rate_discriminative": 0.0,
    "max_false_rejection_rate_consistency": 0.0,
    "max_high_critical_concerns": 0,
}


# ---------------------------------------------------------------------------
# Decision core (pure: no file I/O, fully unit-testable)
# ---------------------------------------------------------------------------
def _next_steps(status: str, *, missing_scored: bool = False) -> list[str]:
    if status == PROMOTE:
        return ["record_promotion"]
    if status == REVISE:
        return ["revise_statement_or_mapping", "regenerate_comparator_triple", "rejudge"]
    if status == HUMAN_REVIEW:
        return ["human_review", "rerun_with_stronger_judge", "record_human_override"]
    if missing_scored:
        return ["generate_judge_results", "rerun_scoring"]
    return ["fix_blocking_issue", "rerun_pipeline"]


def _decide_formal(sig: dict, thr: dict | None = None) -> dict:
    """Map gathered signals to a *formal* decision (rules 1-4). `sig` keys (None = unknown):

    presence: mapping_present, card_present, review_present, human_approved,
              declaration_present, scored_present, scored_path_hint
    integrity: provenance_match (True/False/None), unrecoverable_parse_errors (int)
    real row: real_row_present (bool), real_verdict (str|None)
    calibration: discriminative_recall, consistency_false_alarm_rate, malformed_yaml_rate
                 (float|None), recovered_verdict_count (int)
    formal: build_status, no_sorry_status, axiom_audit_status, equivalence_check_status,
            comparator_pipeline (PASS/FAIL/SKIPPED/UNKNOWN), comparator_status (mapping field, str)
    misc: human_override (bool), mapping_verdict (str, the recorded mapping verdict)

    The optional structured-judge-metric cap (v0.3 1c) is applied by the public `decide`
    wrapper, not here; this function is the authoritative formal core.
    """
    thr = thr or DEFAULT_THRESHOLDS
    cs = sig.get("comparator_status") or "UNKNOWN"
    comp_pipeline = sig.get("comparator_pipeline") or "UNKNOWN"
    comp_failed = comp_pipeline == "FAIL" or cs == COMPARATOR_FAILED
    comp_real = cs in COMPARATOR_REAL or comp_pipeline == "PASS"
    comp_best_effort = cs == COMPARATOR_BEST_EFFORT
    comp_fake = cs == COMPARATOR_FAKE

    # ---- Rule 1: hard formal / integrity failures -> BLOCK -------------------
    blocks: list[str] = []
    if sig.get("structured_status_error"):
        blocks.append("Structured pipeline status is unusable (formal-evidence integrity "
                      f"failure): {sig['structured_status_error']}.")
    if not sig.get("mapping_present"):
        blocks.append("Formal mapping is missing, or the target is not in formal_mapping.yaml.")
    if not sig.get("card_present"):
        blocks.append("Theorem card (source ref) is missing in theorem_index.yaml.")
    if not sig.get("review_present"):
        blocks.append("Fidelity review is missing.")
    if not sig.get("human_approved"):
        blocks.append("Human approval is missing or not granted (mapping/review human_approved).")
    if not sig.get("declaration_present"):
        blocks.append("Mapped Lean declaration is missing from the formal mapping.")
    if sig.get("build_status") == "FAIL":
        blocks.append("Lean build failed (pipeline report).")
    if sig.get("no_sorry_status") == "FAIL":
        blocks.append("No-sorry check failed (pipeline report).")
    if sig.get("axiom_audit_status") == "FAIL":
        blocks.append("Axiom audit failed: unexpected axioms or sorryAx (pipeline report).")
    if sig.get("equivalence_check_status") == "FAIL":
        blocks.append("Equivalence check failed: provable-equivalence lemma missing, unbuilt, "
                      "or using unexpected axioms (pipeline report).")
    if comp_failed:
        blocks.append(f"Comparator failed (status {cs!r}, pipeline {comp_pipeline!r}).")
    missing_scored = not sig.get("scored_present")
    if missing_scored:
        hint = sig.get("scored_path_hint") or "docs/judge_results/<Target>_scored.yaml"
        blocks.append(f"Required scored judge result is missing ({hint}).")
    elif not sig.get("real_row_present"):
        blocks.append("Scored judge result has no real-mapping row.")
    if sig.get("provenance_match") is False:
        blocks.append("Provenance mismatch: scored prompt/mutants hashes differ from _manifest.yaml.")
    if (sig.get("unrecoverable_parse_errors") or 0) > 0:
        blocks.append(
            f"Judge result has {sig['unrecoverable_parse_errors']} unrecoverable parse error(s)."
        )
    if blocks:
        return {"status": BLOCK, "confidence": "low", "reasons": blocks,
                "allowed_next_steps": _next_steps(BLOCK, missing_scored=missing_scored)}

    # ---- Rule 2: real-mapping failure -> REVISE / HUMAN_REVIEW ----------------
    rv = sig.get("real_verdict")
    if rv == "FAIL":
        return {"status": REVISE, "confidence": "low",
                "reasons": ["The judge rejected the real mapping (FAIL); the Lean statement or "
                            "mapping likely needs revision before any further work."],
                "allowed_next_steps": _next_steps(REVISE)}
    if rv == "WARN":
        return {"status": HUMAN_REVIEW, "confidence": "low",
                "reasons": ["The judge flagged the real mapping (WARN); a human must decide "
                            "whether to revise or accept the caveat."],
                "allowed_next_steps": _next_steps(HUMAN_REVIEW)}
    if rv not in ACCEPT:
        return {"status": HUMAN_REVIEW, "confidence": "low",
                "reasons": [f"The judge did not accept the real mapping (verdict {rv!r}); "
                            "needs human judgement."],
                "allowed_next_steps": _next_steps(HUMAN_REVIEW)}

    # Baseline positives shared by rules 3 and 4.
    positives = [
        "Formal mapping, theorem card, and a human-approved fidelity review are all present.",
        f"The judge accepted the real mapping (verdict {rv}).",
    ]
    if sig.get("build_status") == "PASS":
        positives.append("Lean build is recorded as passing.")
    if comp_real and not comp_best_effort:
        positives.append("Comparator passed with a real landrun sandbox.")

    # ---- Rule 3: weak calibration OR unverified formal status -> HUMAN_REVIEW --
    cal: list[str] = []
    recall = sig.get("discriminative_recall")
    far = sig.get("consistency_false_alarm_rate")
    malformed = sig.get("malformed_yaml_rate")
    if recall is not None and recall < thr["min_recall"]:
        cal.append(f"Discriminative recall {recall} is below the threshold {thr['min_recall']}; "
                   "the judge missed planted defect(s), so unattended promotion is not allowed.")
    if far is not None and far > thr["max_far"]:
        cal.append(f"Consistency false-alarm rate {far} exceeds the threshold {thr['max_far']}.")
    if malformed is not None and malformed > thr["max_malformed"]:
        cal.append(f"Malformed-YAML rate {malformed} exceeds the threshold {thr['max_malformed']}.")
    if (sig.get("recovered_verdict_count") or 0) > 0:
        cal.append(f"{sig['recovered_verdict_count']} judge verdict(s) were recovered from "
                   "malformed YAML; lower confidence.")
    if comp_fake:
        cal.append("Comparator passed only with PASSED_FAKE_LANDRUN (no real sandbox); "
                   "this is not a high-confidence pass.")
    if rv == "PASS_EQUIV":
        cal.append("The real mapping was judged PASS_EQUIV without a built equivalence lemma; "
                   "needs review (see PROJECT_CONTEXT.md).")
    if ((rv == "PASS_PROVABLE_EQUIV" or sig.get("mapping_verdict") == "PASS_PROVABLE_EQUIV")
            and sig.get("equivalence_check_status") != "PASS"):
        cal.append("PASS_PROVABLE_EQUIV is claimed but the equivalence check is not a recorded "
                   "PASS; a bare 'provably equivalent' claim is not evidence (run the pipeline "
                   "with --with-equivalence-check).")

    unknown: list[str] = []
    if sig.get("build_status") != "PASS":
        unknown.append(f"Lean build status is {sig.get('build_status') or 'UNKNOWN'!r} (not a "
                       "recorded PASS); the formal proof is not verified for unattended promotion.")
    if sig.get("no_sorry_status") != "PASS":
        unknown.append(f"No-sorry status is {sig.get('no_sorry_status') or 'UNKNOWN'!r} "
                       "(not a recorded PASS).")
    if sig.get("axiom_audit_status") != "PASS":
        unknown.append(f"Axiom-audit status is {sig.get('axiom_audit_status') or 'UNKNOWN'!r} "
                       "(not a recorded PASS).")
    if not comp_real and not comp_fake:
        unknown.append(f"Comparator is not verified (status {cs!r}, pipeline {comp_pipeline!r}).")
    if sig.get("provenance_match") is None:
        unknown.append("Provenance could not be verified (_manifest.yaml missing or incomplete).")

    if cal or unknown:
        reasons = positives + cal + unknown
        if not sig.get("human_override"):
            reasons.append("These signals cap confidence and require human review; they do not, "
                           "by themselves, prove the theorem mapping is wrong.")
            return {"status": HUMAN_REVIEW, "confidence": "low", "reasons": reasons,
                    "allowed_next_steps": _next_steps(HUMAN_REVIEW)}

    # ---- Rule 4: PROMOTE -----------------------------------------------------
    reasons = list(positives)
    confidence = "high"
    if comp_best_effort:
        confidence = "medium"
        reasons.append("Comparator passed with best-effort landrun (degraded ABI); "
                       "confidence capped to medium.")
    if sig.get("human_override"):
        confidence = "medium"
        reasons.append("A human override is recorded, permitting promotion despite open caveats.")
    reasons.append("All formal checks and judge-calibration thresholds are satisfied.")
    return {"status": PROMOTE, "confidence": confidence, "reasons": reasons,
            "allowed_next_steps": _next_steps(PROMOTE)}


# ---------------------------------------------------------------------------
# Conservative structured-judge-metric cap (v0.3 milestone 1c)
#
# The optional structured-scoring summary (score_judge.py --structured, §10.3) is a *global*
# judge-reliability signal. Per PROJECT_CONTEXT.md it may only **cap an otherwise-
# promotable target to HUMAN_REVIEW**: it never produces BLOCK, never PROMOTE, and never upgrades a
# non-PROMOTE formal decision. A `None` metric (not measured) never triggers a cap. The judge is a
# calibrated source-fidelity reviewer, not a theorem oracle.
# ---------------------------------------------------------------------------
_JM_DISCLAIMER = (
    "These structured judge metrics cap promotion to HUMAN_REVIEW; they are source-fidelity "
    "reliability evidence, not proof about the theorem (the judge is not a theorem oracle)."
)


def extract_target_metrics(summary: dict, target: str | None) -> dict:
    """Pull the cap-relevant metrics out of a structured-scoring summary, preferring the
    per-target node (`summary['per_target'][target]`) and falling back to the top-level summary."""
    node = summary
    per_target = summary.get("per_target") if isinstance(summary, dict) else None
    if isinstance(per_target, dict) and target in per_target and isinstance(per_target[target], dict):
        node = per_target[target]
    totals = node.get("totals") or {}
    rel = node.get("reliability") or {}
    return {
        "schema_valid_rate": totals.get("schema_valid_rate"),
        "invalid_rate": totals.get("invalid_rate"),
        "unparseable_rate": totals.get("unparseable_rate"),
        "discriminative_recall": rel.get("discriminative_recall"),
        "false_acceptance_rate_discriminative": rel.get("false_acceptance_rate_discriminative"),
        "false_rejection_rate_consistency": rel.get("false_rejection_rate_consistency"),
        "high_critical_concern_count": node.get("high_critical_concern_count"),
    }


def judge_metric_caps(target: str | None, status: str, summary, jm_thr: dict) -> list[str]:
    """Reasons (possibly empty) why structured judge metrics should cap promotion to review."""
    if status == JM_INVALID:
        return ["Structured judge metrics were supplied but are invalid/unparseable; a human must "
                "review (the metrics cannot be relied upon)."]
    if status != JM_PRESENT or not isinstance(summary, dict):
        return []
    m = extract_target_metrics(summary, target)
    reasons: list[str] = []
    svr = m["schema_valid_rate"]
    if svr is not None and svr < jm_thr["min_schema_valid_rate"]:
        reasons.append(f"Structured judge schema_valid_rate {svr} is below "
                       f"{jm_thr['min_schema_valid_rate']}; some judge records were not well-formed.")
    ir = m["invalid_rate"]
    if ir is not None and ir > jm_thr["max_invalid_rate"]:
        reasons.append(f"Structured judge invalid_rate {ir} exceeds {jm_thr['max_invalid_rate']}.")
    ur = m["unparseable_rate"]
    if ur is not None and ur > jm_thr["max_unparseable_rate"]:
        reasons.append(f"Structured judge unparseable_rate {ur} exceeds "
                       f"{jm_thr['max_unparseable_rate']}.")
    rec = m["discriminative_recall"]
    if rec is not None and rec < jm_thr["min_discriminative_recall"]:
        reasons.append(f"Structured discriminative_recall {rec} is below "
                       f"{jm_thr['min_discriminative_recall']}; the judge missed planted defect(s).")
    fa = m["false_acceptance_rate_discriminative"]
    if fa is not None and fa > jm_thr["max_false_acceptance_rate_discriminative"]:
        reasons.append(f"Structured false_acceptance_rate_discriminative {fa} exceeds "
                       f"{jm_thr['max_false_acceptance_rate_discriminative']}; the judge accepted a "
                       "discriminative mutant.")
    fr = m["false_rejection_rate_consistency"]
    if fr is not None and fr > jm_thr["max_false_rejection_rate_consistency"]:
        reasons.append(f"Structured false_rejection_rate_consistency {fr} exceeds "
                       f"{jm_thr['max_false_rejection_rate_consistency']}; the judge rejected a "
                       "meaning-preserving variant.")
    hc = m["high_critical_concern_count"]
    if hc is not None and hc > jm_thr["max_high_critical_concerns"]:
        reasons.append(f"Structured judge raised {hc} high/critical fidelity concern(s) for "
                       f"{target}; a human must review whether the mapping needs revision.")
    return reasons


def decide(sig: dict, thr: dict | None = None, jm_thr: dict | None = None) -> dict:
    """Public decision: the authoritative formal decision (`_decide_formal`), then an optional,
    conservative structured-judge-metric cap (v0.3 1c).

    Reads two extra `sig` keys (both optional; default behaviour is unchanged when absent):
      judge_metrics_status: NOT_RUN | PRESENT | INVALID   (default NOT_RUN)
      judge_metrics:        the structured-scoring summary dict, or None

    The cap can only turn a PROMOTE into HUMAN_REVIEW; it never BLOCKs, never PROMOTEs, and never
    upgrades a non-PROMOTE decision."""
    jm_thr = jm_thr or DEFAULT_JUDGE_METRIC_THRESHOLDS
    base = _decide_formal(sig, thr)

    jms = sig.get("judge_metrics_status") or JM_NOT_RUN
    cap_reasons = judge_metric_caps(sig.get("target"), jms, sig.get("judge_metrics"), jm_thr)

    result = dict(base)
    capped = base["status"] == PROMOTE and bool(cap_reasons)
    if capped:
        result["status"] = HUMAN_REVIEW
        result["confidence"] = "low"
        result["reasons"] = list(base["reasons"]) + cap_reasons + [_JM_DISCLAIMER]
        result["allowed_next_steps"] = _next_steps(HUMAN_REVIEW)

    result["judge_metrics_status"] = jms
    result["judge_metric_cap"] = None if jms == JM_NOT_RUN else {
        "applied": capped,
        "capped_from": base["status"],
        "capped_to": result["status"],
        "reasons": cap_reasons,
    }
    return result


# ---------------------------------------------------------------------------
# I/O gathering layer
# ---------------------------------------------------------------------------
def _load_yaml(path: Path):
    if not path.exists():
        return None
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _load_frontmatter(path: Path) -> dict | None:
    if not path.exists():
        return None
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        return None
    return yaml.safe_load("\n".join(lines[1:end])) or {}


def _stage_status_value(v) -> str | None:
    """Normalise a stage value to PASS/FAIL/SKIPPED — accepts a bare string or a
    {"status": ...} object (the pipeline_status.v0.1 nested shape)."""
    if isinstance(v, str):
        return v.upper()
    if isinstance(v, dict) and isinstance(v.get("status"), str):
        return v["status"].upper()
    return None


def _sha256_file(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def read_structured_status(path: str, target: str, root: Path) -> tuple[dict, str | None]:
    """Validate an explicit structured pipeline-status file and return (formal_stages, error).

    On any integrity problem (missing/unreadable, wrong schema, target mismatch, missing required
    stage, or a **stale** input fingerprint) it returns ({}, reason) — the caller fails closed
    (BLOCK). On success it returns the flattened {stage: PASS/FAIL/SKIPPED} dict and None.

    Freshness is by content: every `input_fingerprints` entry must still match a re-hash of the
    file at that repo-relative path under `root` (not timestamps)."""
    p = Path(path)
    if not p.exists():
        return {}, f"structured pipeline status not found: {path}"
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {}, f"structured pipeline status is not valid JSON ({exc})"
    if not isinstance(doc, dict):
        return {}, "structured pipeline status is not a JSON object"
    if doc.get("schema_version") != PIPELINE_STATUS_SCHEMA:
        return {}, f"unknown pipeline-status schema_version {doc.get('schema_version')!r}"
    if doc.get("target") != target:
        return {}, (f"pipeline status is for target {doc.get('target')!r}, not {target!r} "
                    "(target-scoped formal evidence is required)")
    stages = doc.get("stages")
    if not isinstance(stages, dict):
        return {}, "structured pipeline status has no 'stages' object"
    missing = sorted(REQUIRED_FORMAL_STAGES - set(stages))
    if missing:
        return {}, f"structured pipeline status is missing required stages: {missing}"
    fps = doc.get("input_fingerprints")
    if not isinstance(fps, dict) or not fps:
        return {}, "structured pipeline status has no input_fingerprints"
    stale = []
    for rel, recorded in fps.items():
        current = _sha256_file(root / rel)
        if current is None or f"sha256:{current}" != recorded:
            stale.append(rel)
    if stale:
        return {}, f"structured pipeline status is stale; input fingerprint mismatch for {sorted(stale)}"
    formal = {name: _stage_status_value(node) for name, node in stages.items()
              if _stage_status_value(node) is not None}
    return formal, None


def read_formal_status(root: Path) -> dict:
    """build / no_sorry / comparator stage status. Prefers a structured JSON (auto, if present),
    then the markdown pipeline report. Returns each stage as PASS/FAIL/SKIPPED, or absent if
    unknown. This is the *unvalidated* fallback; the explicit, fingerprint-checked path is
    `read_structured_status` via --pipeline-status."""
    js = root / "docs" / "pipeline_status.json"
    if js.exists():
        try:
            doc = json.loads(js.read_text(encoding="utf-8")) or {}
            stages = doc.get("stages", doc)
            out = {k: _stage_status_value(v) for k, v in stages.items()
                   if _stage_status_value(v) is not None}
            if out:
                return out
        except (json.JSONDecodeError, AttributeError):
            pass
    md = root / "docs" / "pipeline_report.md"
    out: dict[str, str] = {}
    if not md.exists():
        return out
    for line in md.read_text(encoding="utf-8").splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 3:
            continue
        stage = cells[1].strip("`").strip()
        for st in ("PASS", "FAIL", "SKIPPED"):
            if st in cells[2]:
                out[stage] = st
                break
    return out


def load_judge_metrics(path: str | None) -> tuple[str, dict | None]:
    """Load an optional structured-scoring summary (v0.3 1c). Returns (status, summary):
      - no path                                  -> (NOT_RUN, None)   [default; behaviour unchanged]
      - a readable JSON dict that looks like a summary -> (PRESENT, summary)
      - anything else (unreadable / bad JSON / not a summary) -> (INVALID, None)."""
    if not path:
        return JM_NOT_RUN, None
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return JM_INVALID, None
    if isinstance(raw, dict) and any(k in raw for k in ("totals", "reliability", "per_target")):
        return JM_PRESENT, raw
    return JM_INVALID, None


def gather(target: str, root: Path = ROOT, judge_metrics_path: str | None = None,
           pipeline_status_path: str | None = None) -> dict:
    """Read all artifacts and build the signals + provenance dicts for `decide`."""
    mapping_doc = _load_yaml(root / "docs" / "formal_mapping.yaml") or {}
    targets = (mapping_doc.get("targets") or {}) if isinstance(mapping_doc, dict) else {}
    tmap = targets.get(target) or {}
    mapping_present = bool(tmap)

    # Source card: every source_ref must resolve in theorem_index.yaml.
    index_doc = _load_yaml(root / "docs" / "theorem_index.yaml") or {}
    entries = (index_doc.get("entries") or {}) if isinstance(index_doc, dict) else {}
    refs = tmap.get("source_refs") or []
    card_present = bool(refs) and all(r in entries for r in refs)

    # Fidelity review frontmatter.
    review_rel = tmap.get("review") or f"docs/fidelity_reviews/{target}.md"
    fm = _load_frontmatter(root / review_rel)
    review_present = fm is not None
    human_approved = bool(tmap.get("human_approved")) and bool((fm or {}).get("human_approved"))

    declaration_present = bool((tmap.get("lean") or {}).get("declaration"))
    comparator_status = tmap.get("comparator_status") or "UNKNOWN"

    # Scored judge result.
    scored_path = root / "docs" / "judge_results" / f"{target}_scored.yaml"
    scored = _load_yaml(scored_path)
    scored_present = isinstance(scored, dict)
    metrics = (scored or {}).get("metrics") or {}
    pf = metrics.get("parse_format") or {}
    real_row = None
    for r in (scored or {}).get("per_variant") or []:
        if r.get("class") == "real":
            real_row = r
            break

    # Provenance match against the dry-run manifest.
    manifest = _load_yaml(root / "docs" / "judge_inputs_dryrun" / "_manifest.yaml")
    provenance_match = None
    if scored_present and isinstance(manifest, dict):
        provenance_match = (
            scored.get("prompt_sha256") == manifest.get("prompt_sha256")
            and scored.get("mutants_sha256") == manifest.get("mutants_sha256")
        )

    # Formal-stage status. With an explicit --pipeline-status, use the validated, fingerprint-checked
    # structured artifact and fail closed on any integrity problem; otherwise fall back to the
    # (unvalidated) markdown/auto-JSON reader for backward compatibility.
    structured_status_error = None
    if pipeline_status_path:
        formal, structured_status_error = read_structured_status(pipeline_status_path, target, root)
    else:
        formal = read_formal_status(root)

    # Optional structured judge-scoring summary (v0.3 1c). Absent -> NOT_RUN (no effect).
    jm_status, jm_summary = load_judge_metrics(judge_metrics_path)

    sig = {
        "target": target,
        "structured_status_error": structured_status_error,
        "judge_metrics_status": jm_status,
        "judge_metrics": jm_summary,
        "mapping_present": mapping_present,
        "card_present": card_present,
        "review_present": review_present,
        "human_approved": human_approved,
        "declaration_present": declaration_present,
        "scored_present": scored_present,
        "scored_path_hint": str(scored_path.relative_to(root)),
        "provenance_match": provenance_match,
        "unrecoverable_parse_errors": pf.get("unrecoverable_parse_error_count") or 0,
        "real_row_present": real_row is not None,
        "real_verdict": (real_row or {}).get("judge_verdict"),
        "discriminative_recall": metrics.get("discriminative_recall"),
        "consistency_false_alarm_rate": metrics.get("consistency_false_alarm_rate"),
        "malformed_yaml_rate": pf.get("malformed_yaml_rate"),
        "recovered_verdict_count": pf.get("recovered_verdict_count") or 0,
        "build_status": formal.get("build", "UNKNOWN"),
        "no_sorry_status": formal.get("no_sorry", "UNKNOWN"),
        "axiom_audit_status": formal.get("axiom_audit", "UNKNOWN"),
        "equivalence_check_status": formal.get("equivalence_check", "UNKNOWN"),
        "comparator_pipeline": formal.get("comparator", "UNKNOWN"),
        "comparator_status": comparator_status,
        "mapping_verdict": tmap.get("verdict"),
        "human_override": bool(tmap.get("human_override")) or bool((fm or {}).get("human_override")),
    }
    provenance = {
        "prompt_sha256": (scored or {}).get("prompt_sha256"),
        "mutants_sha256": (scored or {}).get("mutants_sha256"),
        "scored_utc": (scored or {}).get("scored_utc"),
        "comparator_status": comparator_status,
        "landrun_abi": "unknown",
    }
    return {"sig": sig, "provenance": provenance}


def display_path(path: Path) -> str:
    """Repo-relative display string when possible, else the path as-is. Never raises — `--output`
    is a testing override that may legitimately point outside the repo."""
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def build_output(target: str, decision: dict, provenance: dict) -> dict:
    return {
        "promotion_decision": {
            "target": target,
            "status": decision["status"],
            "confidence": decision["confidence"],
            "reasons": decision["reasons"],
            "allowed_next_steps": decision["allowed_next_steps"],
            "judge_metrics_status": decision.get("judge_metrics_status", JM_NOT_RUN),
            "judge_metric_cap": decision.get("judge_metric_cap"),
            "provenance": provenance,
            "decided_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Offline promotion-decision gate (writes "
                                             "docs/promotion/<Target>.yaml).")
    ap.add_argument("--target", required=True, help="mapping target, e.g. PutCallParity")
    ap.add_argument("--output", help="override output path (default docs/promotion/<Target>.yaml)")
    ap.add_argument("--force", action="store_true", help="overwrite an existing decision file")
    ap.add_argument("--min-discriminative-recall", type=float,
                    default=DEFAULT_THRESHOLDS["min_recall"])
    ap.add_argument("--max-consistency-far", type=float, default=DEFAULT_THRESHOLDS["max_far"])
    ap.add_argument("--max-malformed-yaml-rate", type=float,
                    default=DEFAULT_THRESHOLDS["max_malformed"])
    ap.add_argument("--judge-metrics", metavar="PATH",
                    help="optional structured judge-scoring summary JSON (score_judge.py "
                         "--structured); conservative-only: it may cap an otherwise-promotable "
                         "target to HUMAN_REVIEW, never BLOCK or PROMOTE (PROJECT_CONTEXT.md)")
    ap.add_argument("--pipeline-status", metavar="PATH",
                    help="explicit structured pipeline_status.json (rebuild_pipeline.py "
                         "--pipeline-status-out). Preferred over the markdown report: it is "
                         "validated (schema, target, required stages) and fingerprint-checked for "
                         "freshness, and the gate fails closed (BLOCK) on any mismatch.")
    args = ap.parse_args()

    out_path = Path(args.output) if args.output else ROOT / "docs" / "promotion" / f"{args.target}.yaml"
    if out_path.exists() and not args.force:
        sys.stderr.write(f"ERROR: {out_path} already exists; pass --force to overwrite\n")
        return 2

    thr = {
        "min_recall": args.min_discriminative_recall,
        "max_far": args.max_consistency_far,
        "max_malformed": args.max_malformed_yaml_rate,
    }
    gathered = gather(args.target, judge_metrics_path=args.judge_metrics,
                      pipeline_status_path=args.pipeline_status)
    decision = decide(gathered["sig"], thr)
    out_doc = build_output(args.target, decision, gathered["provenance"])

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        yaml.safe_dump(out_doc, sort_keys=False, allow_unicode=True, width=100), encoding="utf-8"
    )

    pd = out_doc["promotion_decision"]
    print(f"GATE DECISION [{pd['status']}] (confidence: {pd['confidence']}) -> "
          f"{display_path(out_path)}")
    cap = pd.get("judge_metric_cap")
    if pd.get("judge_metrics_status", JM_NOT_RUN) != JM_NOT_RUN:
        capped = bool(cap and cap.get("applied"))
        print(f"  judge_metrics_status: {pd['judge_metrics_status']} "
              f"(capped to HUMAN_REVIEW: {capped})")
    for r in pd["reasons"]:
        print(f"  - {r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
