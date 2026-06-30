#!/usr/bin/env python3
"""Structured judge-evidence schema validator (v0.3 milestone 1a — validation only).

This is a **pure, offline** validator for a single structured judge result. It calls no model/API,
reads no answer key, and makes no promotion decision. It only answers: *is this judge output a
well-formed structured source-fidelity record?*

Non-drift rule (see PROJECT_CONTEXT.md): the judge is a **calibrated source-fidelity
reviewer, not a theorem oracle**. A `verdict: PASS` here is *source-fidelity evidence only*; it can
never override Lean build / no-sorry / axiom audit / Comparator / guarded-equivalence results. This
script validates the *shape* of that evidence; it does not act on it.

Structured judge-evidence schema (`schema_version: "0.3.0"`):

    {
      "schema_version": "0.3.0",
      "target": "GoldIrrationalSqrtTwo",
      "source_ref": "thm:gold_irrational_sqrt_two",
      "candidate_id": "real",
      "verdict": "PASS",                # one of ALLOWED_VERDICTS
      "confidence": 0.95,               # number in [0.0, 1.0]
      "concerns": [ ... ],              # list of concern objects (may be empty)
      "summary": "…",                   # string
      "requires_human_review": false    # bool
    }

Each concern object:

    {
      "type": "assumption_mismatch",    # one of ALLOWED_CONCERN_TYPES
      "severity": "low",                # one of ALLOWED_SEVERITIES
      "description": "…",               # string (required)
      "source_evidence": "…",           # string (optional)
      "formal_evidence": "…"            # string (optional)
    }

Status:
  - VALID              — a record carrying `schema_version` that satisfies the full schema.
  - PARTIAL_RECOVERED  — a legacy / minimal output (no `schema_version`) from which a single
                         unambiguous allowed `verdict` can be safely recovered; the structured
                         evidence is incomplete and should be treated as lower-confidence.
  - INVALID            — anything else (bad/missing values in a schema record, malformed JSON with
                         no recoverable verdict, etc.). Nothing is ever fabricated.

Usage:
    python scripts/validate_judge_schema.py <file.json>     # validate a file
    python scripts/validate_judge_schema.py                 # read JSON from stdin
    python scripts/validate_judge_schema.py -               # read JSON from stdin

Prints a machine-readable JSON summary. Exit 0 for VALID/PARTIAL_RECOVERED, 1 for INVALID,
2 for a usage error (bad args / unreadable file).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SCHEMA_VERSION = "0.3.0"

ALLOWED_VERDICTS = {
    "PASS", "PASS_EQUIV", "PASS_PROVABLE_EQUIV", "WARN", "FAIL", "UNPARSEABLE",
}
ALLOWED_CONCERN_TYPES = {
    "assumption_mismatch", "conclusion_mismatch", "variable_or_domain_mismatch",
    "missing_condition", "extra_condition", "weakened_statement", "strengthened_statement",
    "notation_ambiguity", "vacuity_or_triviality", "proof_irrelevance", "source_not_found",
    "other",
}
ALLOWED_SEVERITIES = {"low", "medium", "high", "critical"}

REQUIRED_FIELDS = [
    "schema_version", "target", "source_ref", "candidate_id", "verdict", "confidence",
    "concerns", "summary", "requires_human_review",
]

VALID, PARTIAL_RECOVERED, INVALID = "VALID", "PARTIAL_RECOVERED", "INVALID"

# Recover a single unambiguous verdict from legacy / minimal output (JSON-ish or YAML-ish).
# Longest alternatives first so PASS does not shadow PASS_EQUIV / PASS_PROVABLE_EQUIV.
_VERDICT_RE = re.compile(
    r'(?:"verdict"|verdict)\s*:\s*["\']?('
    + "|".join(sorted(ALLOWED_VERDICTS, key=len, reverse=True))
    + r')["\']?'
)


def _is_number(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _is_str(x) -> bool:
    return isinstance(x, str)


def recover_verdict(raw: str) -> str | None:
    """Return a single unambiguous allowed verdict found in `raw`, else None."""
    distinct = set(_VERDICT_RE.findall(raw))
    return next(iter(distinct)) if len(distinct) == 1 else None


def validate_concern(c, idx: int) -> list[str]:
    errs: list[str] = []
    if not isinstance(c, dict):
        return [f"concerns[{idx}]: not an object"]
    if c.get("type") not in ALLOWED_CONCERN_TYPES:
        errs.append(f"concerns[{idx}]: type {c.get('type')!r} not in {sorted(ALLOWED_CONCERN_TYPES)}")
    if c.get("severity") not in ALLOWED_SEVERITIES:
        errs.append(f"concerns[{idx}]: severity {c.get('severity')!r} not in {sorted(ALLOWED_SEVERITIES)}")
    if not _is_str(c.get("description")) or not c.get("description"):
        errs.append(f"concerns[{idx}]: 'description' must be a non-empty string")
    for opt in ("source_evidence", "formal_evidence"):
        if opt in c and not _is_str(c[opt]):
            errs.append(f"concerns[{idx}]: '{opt}' must be a string when present")
    return errs


def validate_full_record(obj: dict) -> list[str]:
    """Errors for a record that *claims* the structured schema (carries `schema_version`)."""
    errs: list[str] = []
    for f in REQUIRED_FIELDS:
        if f not in obj:
            errs.append(f"missing required field '{f}'")

    if "verdict" in obj and obj["verdict"] not in ALLOWED_VERDICTS:
        errs.append(f"verdict {obj['verdict']!r} not in {sorted(ALLOWED_VERDICTS)}")
    if "confidence" in obj:
        c = obj["confidence"]
        if not _is_number(c) or not (0.0 <= float(c) <= 1.0):
            errs.append("confidence must be a number in [0.0, 1.0]")
    if "requires_human_review" in obj and not isinstance(obj["requires_human_review"], bool):
        errs.append("requires_human_review must be a boolean")
    for f in ("target", "source_ref", "candidate_id"):
        if f in obj and (not _is_str(obj[f]) or not obj[f]):
            errs.append(f"'{f}' must be a non-empty string")
    if "summary" in obj and not _is_str(obj["summary"]):
        errs.append("summary must be a string")
    if "schema_version" in obj and not _is_str(obj["schema_version"]):
        errs.append("schema_version must be a string")
    if "concerns" in obj:
        if not isinstance(obj["concerns"], list):
            errs.append("concerns must be a list")
        else:
            for i, c in enumerate(obj["concerns"]):
                errs.extend(validate_concern(c, i))
    return errs


def classify_record(obj: dict) -> dict:
    """Classify an already-parsed JSON object."""
    verdict = obj.get("verdict") if isinstance(obj.get("verdict"), str) else None
    if "schema_version" in obj:
        # Claims to be a full structured v0.3 record: validate strictly.
        errs = validate_full_record(obj)
        status = VALID if not errs else INVALID
        return {"status": status, "verdict": verdict if verdict in ALLOWED_VERDICTS else None,
                "recovered": False, "errors": errs}
    # No schema_version: legacy / minimal output. Recover the verdict only.
    if verdict in ALLOWED_VERDICTS:
        return {"status": PARTIAL_RECOVERED, "verdict": verdict, "recovered": True,
                "errors": ["no 'schema_version'; recovered verdict only from legacy/minimal output"]}
    return {"status": INVALID, "verdict": None, "recovered": False,
            "errors": ["no 'schema_version' and no recoverable allowed verdict"]}


def validate_text(raw: str) -> dict:
    """Validate a raw string (a JSON document, or legacy/minimal output)."""
    if not raw or not raw.strip():
        return {"status": INVALID, "verdict": None, "recovered": False,
                "errors": ["empty input"]}
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError as exc:
        # Not JSON: salvage only a single unambiguous verdict line, fabricating nothing else.
        rv = recover_verdict(raw)
        if rv is not None:
            return {"status": PARTIAL_RECOVERED, "verdict": rv, "recovered": True,
                    "errors": [f"malformed JSON ({exc.msg}); recovered verdict from a verdict line"]}
        return {"status": INVALID, "verdict": None, "recovered": False,
                "errors": [f"malformed JSON ({exc.msg}) and no recoverable verdict"]}
    if not isinstance(obj, dict):
        return {"status": INVALID, "verdict": None, "recovered": False,
                "errors": [f"top-level JSON must be an object, got {type(obj).__name__}"]}
    return classify_record(obj)


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate one structured judge-evidence record "
                                             "(pure, offline; calls no model/API).")
    ap.add_argument("path", nargs="?", default="-",
                    help="path to a JSON file, or '-' / omitted to read stdin")
    args = ap.parse_args()

    if args.path == "-":
        raw = sys.stdin.read()
    else:
        p = Path(args.path)
        if not p.exists():
            sys.stderr.write(f"ERROR: file not found: {args.path}\n")
            return 2
        raw = p.read_text(encoding="utf-8")

    result = validate_text(raw)
    result["expected_schema_version"] = SCHEMA_VERSION
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] in (VALID, PARTIAL_RECOVERED) else 1


if __name__ == "__main__":
    sys.exit(main())
