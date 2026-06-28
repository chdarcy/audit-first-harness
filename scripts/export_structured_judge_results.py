#!/usr/bin/env python3
"""Export structured v0.3 judge-result JSON records (v0.3 milestone 2a).

A **pure, offline** converter on the *scoring* side of the answer-key boundary. It joins blinded
judge results (`docs/judge_results/<target>.yaml`, keyed by `blind_id`) to the local answer key
(`docs/judge_inputs_dryrun/_manifest.yaml`, `blind_id -> target / variant_id`) and the source
mapping (`docs/formal_mapping.yaml`, `target -> source_refs`) to emit structured records
(`schema_version: "0.3.0"`) that are compatible with:

    scripts/validate_judge_schema.py
    scripts/score_judge.py --structured
    scripts/gate_decision.py --judge-metrics

It calls **no model/API** and needs **no API key**. Live judging stays opt-in in
`run_judge.py --execute-api`; this script only converts already-collected replies (a manual import,
an API run, or a fixture). Because un-blinding requires the answer key, this lives here and **not**
in `run_judge.py` / `import_manual_judge_results.py`, which must never read `_manifest.yaml`
(see ARCHITECTURE.md §9, §10.4).

Non-drift rule (ARCHITECTURE.md §0): the judge is a calibrated source-fidelity reviewer, **not a
theorem oracle**. These records are source-fidelity evidence only; they never override the Lean
build / no-sorry / axiom audit / Comparator / guarded-equivalence results.

Documented field mapping (no fabrication of content — only documented, conservative defaults):
  verdict      PASS / PASS_EQUIV / PASS_PROVABLE_EQUIV / WARN / FAIL kept as-is; OUT_OF_SCOPE,
               an absent verdict, or an unrecoverable parse -> UNPARSEABLE.
  confidence   judge low/medium/high -> 0.3 / 0.6 / 0.9; a numeric confidence is clamped to
               [0, 1]; UNPARSEABLE -> 0.0; a recovered-only verdict -> 0.3; otherwise the neutral
               default 0.5.
  concerns     each detected_issue -> a concern; `axis` -> concern `type` via AXIS_TO_CONCERN_TYPE
               (fallback 'other'); severity blocking/caveat/cosmetic -> high/medium/low.
  summary      the reply's `summary`/`rationale` when present, else a documented explanatory string.
  requires_human_review  True for WARN / FAIL / UNPARSEABLE, a recovered verdict, or any
               high/critical concern; else False.
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

# Reuse the structured-schema validator (milestone 1a) rather than duplicating schema logic.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import validate_judge_schema as vjs  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = ROOT / "docs" / "judge_results"
MANIFEST = ROOT / "docs" / "judge_inputs_dryrun" / "_manifest.yaml"
FORMAL_MAPPING = ROOT / "docs" / "formal_mapping.yaml"

SCHEMA_VERSION = vjs.SCHEMA_VERSION  # "0.3.0"
DIRECT_VERDICTS = {"PASS", "PASS_EQUIV", "PASS_PROVABLE_EQUIV", "WARN", "FAIL"}
UNPARSEABLE = "UNPARSEABLE"

# Documented, conservative defaults (no fabrication of judge content).
CONFIDENCE_SCALE = {"low": 0.3, "medium": 0.6, "high": 0.9}
DEFAULT_CONFIDENCE = 0.5
UNPARSEABLE_CONFIDENCE = 0.0
RECOVERED_CONFIDENCE = 0.3

# judge_v1.md detected_issues use blocking/caveat/cosmetic; structured severities pass through.
SEVERITY_MAP = {"blocking": "high", "caveat": "medium", "cosmetic": "low",
                "low": "low", "medium": "medium", "high": "high", "critical": "critical"}

# judge_v1.md rubric axes -> structured concern types (faithful translation; 'other' fallback).
AXIS_TO_CONCERN_TYPE = {
    "A_assumptions": "assumption_mismatch",
    "B_conclusion": "conclusion_mismatch",
    "C_quantifiers": "variable_or_domain_mismatch",
    "D_variables": "variable_or_domain_mismatch",
    "E_vacuity": "vacuity_or_triviality",
    "F_direction": "conclusion_mismatch",
    "G_units_form": "notation_ambiguity",
}


def fail(msg: str) -> int:
    sys.stderr.write(f"ERROR: {msg}\n")
    return 1


# ---------------------------------------------------------------------------
# Pure mapping core (fully unit-testable; no file I/O, no model/API)
# ---------------------------------------------------------------------------
def structured_verdict(judge_verdict) -> str:
    """Map a legacy judge verdict to the structured enum; anything not directly representable
    (OUT_OF_SCOPE, None, an unexpected value) becomes UNPARSEABLE."""
    return judge_verdict if judge_verdict in DIRECT_VERDICTS else UNPARSEABLE


def to_confidence(judge_output, sv: str, recovered: bool) -> float:
    if sv == UNPARSEABLE:
        return UNPARSEABLE_CONFIDENCE
    c = judge_output.get("confidence") if isinstance(judge_output, dict) else None
    if isinstance(c, str) and c.lower() in CONFIDENCE_SCALE:
        val = CONFIDENCE_SCALE[c.lower()]
    elif isinstance(c, (int, float)) and not isinstance(c, bool):
        val = float(c)
    else:
        val = RECOVERED_CONFIDENCE if recovered else DEFAULT_CONFIDENCE
    return round(max(0.0, min(1.0, val)), 4)


def issues_to_concerns(detected_issues) -> list:
    out: list = []
    if not isinstance(detected_issues, list):
        return out
    for it in detected_issues:
        if not isinstance(it, dict):
            continue
        axis = it.get("axis") or it.get("type")
        ctype = AXIS_TO_CONCERN_TYPE.get(axis) or (
            axis if axis in vjs.ALLOWED_CONCERN_TYPES else "other")
        sev = it.get("severity")
        severity = SEVERITY_MAP.get(sev) or (sev if sev in vjs.ALLOWED_SEVERITIES else "medium")
        desc = it.get("description")
        if not (isinstance(desc, str) and desc.strip()):
            desc = "(no description provided)"
        concern = {"type": ctype, "severity": severity, "description": desc}
        for opt in ("source_evidence", "formal_evidence"):
            v = it.get(opt)
            if isinstance(v, str) and v:
                concern[opt] = v
        out.append(concern)
    return out


def requires_human_review(sv: str, recovered: bool, concerns: list) -> bool:
    if sv in ("WARN", "FAIL", UNPARSEABLE):
        return True
    if recovered:
        return True
    return any(c.get("severity") in ("high", "critical") for c in concerns)


def derive_summary(judge_output, sv: str, original_verdict, recovered: bool) -> str:
    if isinstance(judge_output, dict):
        for k in ("summary", "rationale"):
            v = judge_output.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
    if sv == UNPARSEABLE:
        return (f"Original judge verdict {original_verdict!r} could not be represented as a "
                "structured accept/reject verdict; flagged for human review.")
    if recovered:
        return "Verdict recovered from a malformed judge reply; structured body unavailable."
    return ""


def build_record(result_rec: dict, candidate_id: str, target: str, source_ref: str) -> dict:
    """Build one structured v0.3 record from a single blinded judge-result record."""
    original_verdict = result_rec.get("judge_verdict")
    recovered = bool(result_rec.get("recovered_verdict"))
    judge_output = result_rec.get("judge_output")
    sv = structured_verdict(original_verdict)
    concerns = issues_to_concerns(
        judge_output.get("detected_issues") if isinstance(judge_output, dict) else None)
    record = {
        "schema_version": SCHEMA_VERSION,
        "target": target,
        "source_ref": source_ref,
        "candidate_id": candidate_id,
        "verdict": sv,
        "confidence": to_confidence(judge_output, sv, recovered),
        "concerns": concerns,
        "summary": derive_summary(judge_output, sv, original_verdict, recovered),
        "requires_human_review": requires_human_review(sv, recovered, concerns),
    }
    # Optional, non-schema provenance metadata: ignored by the validator and the scorer, kept for
    # auditability (the blind_id and the original verdict that produced this record).
    prov = {"blind_id": result_rec.get("blind_id"), "original_verdict": original_verdict,
            "recovered_verdict": recovered}
    src = result_rec.get("provenance")
    if isinstance(src, dict):
        prov["prompt_sha256"] = src.get("prompt_sha256")
        prov["mode"] = src.get("mode")
    record["provenance"] = prov
    return record


def convert_results(results_doc: dict, manifest: dict, source_ref: str,
                    target: str) -> tuple[list, list]:
    """Convert a blinded results document to structured records, un-blinding via the manifest.
    Returns (records, errors). A blind_id absent from the manifest is reported, not guessed."""
    variants = (manifest or {}).get("variants") or {}
    records: list = []
    errors: list = []
    for rec in (results_doc or {}).get("results") or []:
        bid = rec.get("blind_id")
        man = variants.get(bid)
        if not isinstance(man, dict):
            errors.append(f"{bid!r}: blind_id not found in the answer key; cannot un-blind")
            continue
        if man.get("target") != target:
            errors.append(f"{bid!r}: belongs to target {man.get('target')!r}, not {target!r}")
            continue
        candidate_id = man.get("variant_id")
        if not candidate_id:
            errors.append(f"{bid!r}: manifest entry has no variant_id")
            continue
        records.append(build_record(rec, str(candidate_id), target, source_ref))
    return records, errors


# ---------------------------------------------------------------------------
# I/O layer
# ---------------------------------------------------------------------------
def _load_yaml(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else None


def resolve_source_ref(mapping_doc, target: str) -> str | None:
    targets = (mapping_doc or {}).get("targets") or {}
    refs = (targets.get(target) or {}).get("source_refs") or []
    return refs[0] if refs else None


def validate_records(records: list) -> dict:
    """Self-check every emitted record through validate_judge_schema (no fabrication)."""
    counts = {vjs.VALID: 0, vjs.PARTIAL_RECOVERED: 0, vjs.INVALID: 0}
    invalid: list = []
    for r in records:
        status = vjs.classify_record(r)["status"]
        counts[status] = counts.get(status, 0) + 1
        if status == vjs.INVALID:
            invalid.append({"candidate_id": r.get("candidate_id"),
                            "errors": vjs.classify_record(r)["errors"]})
    return {"counts": counts, "invalid": invalid}


def main() -> int:
    ap = argparse.ArgumentParser(description="Export structured v0.3 judge-result JSON "
                                             "(pure, offline; calls no model/API).")
    ap.add_argument("--target", required=True, help="mapping target, e.g. GoldIrrationalSqrtTwo")
    ap.add_argument("--results", help="blinded results YAML (default docs/judge_results/<T>.yaml)")
    ap.add_argument("--manifest", help="answer key (default docs/judge_inputs_dryrun/_manifest.yaml)")
    ap.add_argument("--mapping", help="formal_mapping.yaml (for source_ref; testing override)")
    ap.add_argument("--source-ref", help="override the source_ref instead of reading the mapping")
    ap.add_argument("--out", help="output JSON file ({\"results\": [...]}); "
                                  "default docs/judge_results/<T>_structured.json")
    ap.add_argument("--split-dir", help="write one <candidate_id>.json per record into this dir")
    ap.add_argument("--force", action="store_true", help="overwrite an existing output file")
    args = ap.parse_args()

    results_path = Path(args.results) if args.results else RESULTS_DIR / f"{args.target}.yaml"
    manifest_path = Path(args.manifest) if args.manifest else MANIFEST
    mapping_path = Path(args.mapping) if args.mapping else FORMAL_MAPPING

    if not results_path.exists():
        print(f"No judge results found at {results_path}; nothing to export "
              f"(run the judge or import manual replies first).")
        return 0
    results_doc = _load_yaml(results_path) or {}
    manifest = _load_yaml(manifest_path)
    if not isinstance(manifest, dict) or not manifest.get("variants"):
        return fail(f"answer key {manifest_path} missing or has no 'variants'")

    source_ref = args.source_ref or resolve_source_ref(_load_yaml(mapping_path), args.target)
    if not source_ref:
        return fail(f"could not resolve a source_ref for {args.target!r}; pass --source-ref")

    records, errors = convert_results(results_doc, manifest, source_ref, args.target)
    for e in errors:
        print(f"WARNING: {e}")
    if not records:
        return fail("no structured records produced (no matching results for the target)")

    report = validate_records(records)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    if args.split_dir:
        out_dir = Path(args.split_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        for r in records:
            (out_dir / f"{r['candidate_id']}.json").write_text(
                json.dumps(r, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"STRUCTURED_EXPORT: wrote {len(records)} record(s) to {out_dir}")
    else:
        out_path = Path(args.out) if args.out else RESULTS_DIR / f"{args.target}_structured.json"
        if out_path.exists() and not args.force:
            return fail(f"{out_path} already exists; pass --force to overwrite")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        doc = {"schema_version": SCHEMA_VERSION, "target": args.target, "exported_utc": now,
               "note": "Source-fidelity evidence only; not theorem truth and not a promotion "
                       "decision (ARCHITECTURE.md §10.4). No model/API was called.",
               "results": records}
        out_path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"STRUCTURED_EXPORT: wrote {len(records)} record(s) to {out_path}")

    c = report["counts"]
    print(f"  schema check: VALID={c.get(vjs.VALID, 0)} "
          f"PARTIAL_RECOVERED={c.get(vjs.PARTIAL_RECOVERED, 0)} INVALID={c.get(vjs.INVALID, 0)}")
    if report["invalid"]:
        print(f"  WARNING: {len(report['invalid'])} record(s) did not validate: {report['invalid']}")
    print(f"  Next: python scripts/score_judge.py --structured <output> "
          f"(then gate_decision.py --judge-metrics)")
    return 0 if not report["invalid"] else 1


if __name__ == "__main__":
    sys.exit(main())
