#!/usr/bin/env python3
"""Offline promotion-decision gate for the audit-first harness (v0.2, milestone 1).

Turns the existing audit/reporting artifacts into one machine-readable decision:

    PROMOTE | BLOCK | REVISE | HUMAN_REVIEW

written to `docs/promotion/<Target>.yaml`.

This script is **pure and offline**:
  - it calls no model/API and runs neither Lean nor the Comparator;
  - it only *reads* existing local artifacts and *writes* under `docs/promotion/`;
  - it never mutates mappings, reviews, mutants, or judge results.

Core principle (see ARCHITECTURE.md §10, §11): **mutation recall and the consistency
false-alarm rate measure judge reliability, not theorem truth.** A missed discriminative
mutant is calibration evidence about the judge — it caps confidence and forces HUMAN_REVIEW;
it is not, by itself, an infrastructure failure nor proof that the real mapping is wrong.

Decision policy (deterministic, ordered — see ARCHITECTURE.md §11.2):
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
"""
from __future__ import annotations

import argparse
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

PROMOTE, BLOCK, REVISE, HUMAN_REVIEW = "PROMOTE", "BLOCK", "REVISE", "HUMAN_REVIEW"

# Verdict buckets (kept in sync with score_judge.py).
ACCEPT = {"PASS", "PASS_EQUIV", "PASS_PROVABLE_EQUIV"}

# Comparator statuses recorded in formal_mapping.yaml (see ARCHITECTURE.md §13.4).
COMPARATOR_REAL = {"PASSED_REAL_LANDRUN", "PASSED_REAL_LANDRUN_BEST_EFFORT"}
COMPARATOR_BEST_EFFORT = "PASSED_REAL_LANDRUN_BEST_EFFORT"
COMPARATOR_FAKE = "PASSED_FAKE_LANDRUN"
COMPARATOR_FAILED = "FAILED_COMPARATOR"

DEFAULT_THRESHOLDS = {
    "min_recall": 1.0,
    "max_far": 0.0,
    "max_malformed": 0.0,
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


def decide(sig: dict, thr: dict | None = None) -> dict:
    """Map gathered signals to a decision. `sig` uses these keys (None = unknown):

    presence: mapping_present, card_present, review_present, human_approved,
              declaration_present, scored_present, scored_path_hint
    integrity: provenance_match (True/False/None), unrecoverable_parse_errors (int)
    real row: real_row_present (bool), real_verdict (str|None)
    calibration: discriminative_recall, consistency_false_alarm_rate, malformed_yaml_rate
                 (float|None), recovered_verdict_count (int)
    formal: build_status, no_sorry_status, axiom_audit_status, comparator_pipeline
            (PASS/FAIL/SKIPPED/UNKNOWN), comparator_status (mapping field, str)
    misc: human_override (bool)
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
                   "needs review (see ARCHITECTURE.md §20.6).")

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


def read_formal_status(root: Path) -> dict:
    """build / no_sorry / comparator stage status. Prefers a structured JSON (future), then the
    markdown pipeline report. Returns each stage as PASS/FAIL/SKIPPED, or absent if unknown."""
    js = root / "docs" / "pipeline_status.json"
    if js.exists():
        try:
            doc = json.loads(js.read_text(encoding="utf-8")) or {}
            stages = doc.get("stages", doc)
            return {k: str(v).upper() for k, v in stages.items() if isinstance(v, str)}
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


def gather(target: str, root: Path = ROOT) -> dict:
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

    formal = read_formal_status(root)

    sig = {
        "target": target,
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
        "comparator_pipeline": formal.get("comparator", "UNKNOWN"),
        "comparator_status": comparator_status,
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


def build_output(target: str, decision: dict, provenance: dict) -> dict:
    return {
        "promotion_decision": {
            "target": target,
            "status": decision["status"],
            "confidence": decision["confidence"],
            "reasons": decision["reasons"],
            "allowed_next_steps": decision["allowed_next_steps"],
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
    gathered = gather(args.target)
    decision = decide(gathered["sig"], thr)
    out_doc = build_output(args.target, decision, gathered["provenance"])

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        yaml.safe_dump(out_doc, sort_keys=False, allow_unicode=True, width=100), encoding="utf-8"
    )

    pd = out_doc["promotion_decision"]
    print(f"GATE DECISION [{pd['status']}] (confidence: {pd['confidence']}) -> "
          f"{out_path.relative_to(ROOT)}")
    for r in pd["reasons"]:
        print(f"  - {r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
