#!/usr/bin/env python3
"""Offline structured-judge workflow runner (v0.3 milestone 2b).

Chains the v0.3 structured-judge pieces over **already-existing** judge results, with **no
model/API call** and **no API key**:

    docs/judge_results/<target>.yaml              (existing blinded judge results)
      -> export_structured_judge_results          (structured v0.3 JSON records)
      -> validate_judge_schema                     (schema check of every record)
      -> score_judge.score_structured_records      (reliability summary)
      -> [--with-gate] gate_decision               (conservative promotion cap, §11.5)

It only *transforms and evaluates* existing artifacts; it does **not** run the judge. Live judging
stays opt-in in `run_judge.py --execute-api`. The structured records are **source-fidelity
evidence, not theorem truth** (PROJECT_CONTEXT.md): via the existing conservative gate they may only
cap promotion to HUMAN_REVIEW (§11.5); they never override the Lean build, no-sorry, axiom audit,
Comparator, or guarded-equivalence results.

Reuses the existing scripts' functions directly (no shelling out, no duplicated logic):
  export_structured_judge_results.convert_results / validate_records / resolve_source_ref
  score_judge.build_structured_answer_key / score_structured_records
  gate_decision.gather / decide / build_output

Deterministic outputs (under --out-dir, default docs/judge_results/):
  <target>_structured.json          the exported records ({"results": [...]})
  <target>_structured_score.json    the reliability summary
  <promotion-dir>/<target>.yaml     the promotion decision (only with --with-gate)
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

# Reuse the existing structured-judge scripts by import (never via the model/API).
sys.path.insert(0, str(Path(__file__).resolve().parent))
import export_structured_judge_results as ex  # noqa: E402
import score_judge as sj  # noqa: E402
import gate_decision as gd  # noqa: E402
import validate_judge_schema as vjs  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = ROOT / "docs" / "judge_results"
PROMOTION_DIR = ROOT / "docs" / "promotion"

NOTE_EVIDENCE = ("Source-fidelity evidence only; not theorem truth and not a promotion decision "
                 "(PROJECT_CONTEXT.md). No model/API was called.")
NOTE_RELIABILITY = ("judge-reliability metrics only; not theorem truth and not a promotion decision "
                    "(PROJECT_CONTEXT.md).")


class WorkflowError(Exception):
    """A clean, expected workflow failure (missing input, refused overwrite, etc.)."""


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _check_writable(path: Path, force: bool) -> None:
    if path.exists() and not force:
        raise WorkflowError(f"{path} already exists; pass --force to overwrite")


def _write_json(path: Path, force: bool, doc) -> None:
    _check_writable(path, force)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_yaml(path: Path, force: bool, doc) -> None:
    _check_writable(path, force)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=100),
                    encoding="utf-8")


def run_workflow(*, target: str, results_path: Path, manifest_path: Path, mapping_path: Path,
                 source_ref: str | None, mutants_dir: Path, out_dir: Path, promotion_dir: Path,
                 with_gate: bool, plan_only: bool, allow_missing: bool, force: bool,
                 root: Path) -> dict:
    """Run (or plan) the structured-judge workflow. Returns a machine-readable summary dict.
    Writes nothing when `plan_only` is True. Never calls a model/API."""
    out_dir, promotion_dir, root = Path(out_dir), Path(promotion_dir), Path(root)
    structured_path = out_dir / f"{target}_structured.json"
    score_path = out_dir / f"{target}_structured_score.json"
    promotion_path = promotion_dir / f"{target}.yaml"

    summary: dict = {
        "target": target,
        "plan_only": plan_only,
        "with_gate": with_gate,
        "paths": {
            "results_in": str(results_path),
            "structured": str(structured_path),
            "score": str(score_path),
            "promotion": str(promotion_path) if with_gate else None,
        },
        "steps": {},
        "ok": True,
    }

    if not Path(results_path).exists():
        if allow_missing:
            summary["steps"] = {"export": {"status": "skipped_missing_results"}}
            summary["note"] = f"no judge results at {results_path}; skipped (--allow-missing)"
            return summary
        summary["ok"] = False
        summary["error"] = (f"no judge results at {results_path}; run the judge / import manual "
                            "replies first, or pass --allow-missing to skip")
        return summary

    if plan_only:
        summary["steps"] = {
            "export": {"status": "planned", "path": str(structured_path)},
            "score": {"status": "planned", "path": str(score_path)},
            "gate": ({"status": "planned", "path": str(promotion_path)} if with_gate
                     else {"status": "skipped"}),
        }
        return summary

    try:
        # ---- export ---------------------------------------------------------
        results_doc = ex._load_yaml(Path(results_path)) or {}
        manifest = ex._load_yaml(Path(manifest_path))
        if not isinstance(manifest, dict) or not manifest.get("variants"):
            raise WorkflowError(f"answer key {manifest_path} missing or has no 'variants'")
        sref = source_ref or ex.resolve_source_ref(ex._load_yaml(Path(mapping_path)), target)
        if not sref:
            raise WorkflowError(f"could not resolve a source_ref for {target!r}; pass --source-ref")
        records, errors = ex.convert_results(results_doc, manifest, sref, target)
        if not records:
            raise WorkflowError(f"no structured records produced for {target} "
                                f"(un-blinding errors: {errors})")
        report = ex.validate_records(records)
        _write_json(structured_path, force, {
            "schema_version": ex.SCHEMA_VERSION, "target": target, "exported_utc": _utc(),
            "note": NOTE_EVIDENCE, "results": records})
        c = report["counts"]
        summary["steps"]["export"] = {
            "status": "ok", "records": len(records),
            "valid": c.get(vjs.VALID, 0), "partial_recovered": c.get(vjs.PARTIAL_RECOVERED, 0),
            "invalid": c.get(vjs.INVALID, 0), "unblind_errors": errors,
            "path": str(structured_path),
        }

        # ---- score ----------------------------------------------------------
        answer_key = sj.build_structured_answer_key(Path(mutants_dir))
        score_summary = sj.score_structured_records(records, answer_key)
        score_summary["scored_utc"] = _utc()
        score_summary["note"] = NOTE_RELIABILITY
        _write_json(score_path, force, score_summary)
        tot, rel = score_summary["totals"], score_summary["reliability"]
        summary["steps"]["score"] = {
            "status": "ok", "total": tot["total"],
            "schema_valid_rate": tot["schema_valid_rate"],
            "invalid_rate": tot["invalid_rate"], "unparseable_rate": tot["unparseable_rate"],
            "discriminative_recall": rel["discriminative_recall"],
            "false_acceptance_rate_discriminative": rel["false_acceptance_rate_discriminative"],
            "real_accept_rate": rel["real_accept_rate"],
            "high_critical_concern_count": score_summary["high_critical_concern_count"],
            "path": str(score_path),
        }

        # ---- gate (optional) ------------------------------------------------
        if with_gate:
            gathered = gd.gather(target, root=root, judge_metrics_path=str(score_path))
            decision = gd.decide(gathered["sig"])
            out_doc = gd.build_output(target, decision, gathered["provenance"])
            _write_yaml(promotion_path, force, out_doc)
            pd = out_doc["promotion_decision"]
            cap = pd.get("judge_metric_cap")
            summary["steps"]["gate"] = {
                "status": pd["status"], "confidence": pd["confidence"],
                "judge_metrics_status": pd.get("judge_metrics_status"),
                "capped_to_human_review": bool(cap and cap.get("applied")),
                "path": str(promotion_path),
            }
        else:
            summary["steps"]["gate"] = {"status": "skipped"}

    except WorkflowError as exc:
        summary["ok"] = False
        summary["error"] = str(exc)

    return summary


def _print_summary(s: dict) -> None:
    suffix = " (plan-only)" if s.get("plan_only") else ""
    print(f"STRUCTURED_JUDGE_WORKFLOW: {s['target']}{suffix}")
    if not s.get("ok", True):
        print(f"  ERROR: {s.get('error')}")
        return
    steps = s.get("steps", {})
    exp = steps.get("export", {})
    if exp.get("status") == "ok":
        print(f"  export: VALID={exp['valid']} INVALID={exp['invalid']} -> {exp['path']}")
    elif exp.get("status") == "planned":
        print(f"  export: planned -> {exp['path']}")
    elif exp.get("status") == "skipped_missing_results":
        print(f"  export: skipped (no judge results)")
    sc = steps.get("score", {})
    if sc.get("status") == "ok":
        print(f"  score: total={sc['total']} schema_valid_rate={sc['schema_valid_rate']} "
              f"discriminative_recall={sc['discriminative_recall']} -> {sc['path']}")
    elif sc.get("status") == "planned":
        print(f"  score: planned -> {sc['path']}")
    g = steps.get("gate", {})
    if g.get("status") == "skipped":
        print("  gate: skipped (pass --with-gate to run the promotion gate)")
    elif g.get("status") == "planned":
        print(f"  gate: planned -> {g['path']}")
    elif g:
        capped = " [judge metrics capped to HUMAN_REVIEW]" if g.get("capped_to_human_review") else ""
        print(f"  gate: {g['status']} (judge_metrics_status={g.get('judge_metrics_status')})"
              f"{capped} -> {g['path']}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Offline structured-judge workflow runner "
                                             "(pure; calls no model/API).")
    ap.add_argument("--target", required=True, help="mapping target, e.g. GoldIrrationalSqrtTwo")
    ap.add_argument("--results", help="existing judge results YAML "
                                      "(default docs/judge_results/<T>.yaml)")
    ap.add_argument("--manifest", help="answer key (default docs/judge_inputs_dryrun/_manifest.yaml)")
    ap.add_argument("--mapping", help="formal_mapping.yaml (for source_ref)")
    ap.add_argument("--source-ref", help="override the source_ref instead of reading the mapping")
    ap.add_argument("--mutants-dir", help="answer-key mutants dir (default docs/mutants)")
    ap.add_argument("--out-dir", help="dir for structured + score JSON (default docs/judge_results)")
    ap.add_argument("--promotion-dir", help="dir for the gate decision (default docs/promotion)")
    ap.add_argument("--root", help="repo root for the gate's formal-status reads (testing override)")
    ap.add_argument("--with-gate", action="store_true",
                    help="also run the conservative promotion gate over the score summary")
    ap.add_argument("--plan-only", "--dry-run", action="store_true", dest="plan_only",
                    help="print the planned paths/steps and write nothing")
    ap.add_argument("--allow-missing", action="store_true",
                    help="skip (exit 0) instead of failing when there are no judge results")
    ap.add_argument("--force", action="store_true", help="overwrite existing output files")
    args = ap.parse_args()

    results_path = Path(args.results) if args.results else RESULTS_DIR / f"{args.target}.yaml"
    summary = run_workflow(
        target=args.target,
        results_path=results_path,
        manifest_path=Path(args.manifest) if args.manifest else ex.MANIFEST,
        mapping_path=Path(args.mapping) if args.mapping else ex.FORMAL_MAPPING,
        source_ref=args.source_ref,
        mutants_dir=Path(args.mutants_dir) if args.mutants_dir else sj.MUTANTS_DIR,
        out_dir=Path(args.out_dir) if args.out_dir else RESULTS_DIR,
        promotion_dir=Path(args.promotion_dir) if args.promotion_dir else PROMOTION_DIR,
        with_gate=args.with_gate,
        plan_only=args.plan_only,
        allow_missing=args.allow_missing,
        force=args.force,
        root=Path(args.root) if args.root else ROOT,
    )
    _print_summary(summary)
    return 0 if summary.get("ok", False) else 1


if __name__ == "__main__":
    sys.exit(main())
