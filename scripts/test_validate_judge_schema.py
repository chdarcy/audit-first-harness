#!/usr/bin/env python3
"""Offline unit tests for scripts/validate_judge_schema.py — pure functions only (no Lean, no API).

Run directly (no pytest):  python scripts/test_validate_judge_schema.py
Exit code 0 if every assertion passes, 1 otherwise.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import validate_judge_schema as vjs  # noqa: E402


def base() -> dict:
    """A fully valid structured record; tests override one or two keys."""
    return {
        "schema_version": "0.3.0",
        "target": "GoldIrrationalSqrtTwo",
        "source_ref": "thm:gold_irrational_sqrt_two",
        "candidate_id": "real",
        "verdict": "PASS",
        "confidence": 0.95,
        "concerns": [],
        "summary": "The Lean statement faithfully represents the source claim.",
        "requires_human_review": False,
    }


def v(d: dict) -> dict:
    """Validate a dict by serialising it (exercises the JSON path like the CLI does)."""
    return vjs.validate_text(json.dumps(d))


_failures: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(f"  [{'ok  ' if cond else 'FAIL'}] {name}" + (f" -- {detail}" if (detail and not cond) else ""))
    if not cond:
        _failures.append(name)


def test_valid_pass_empty_concerns() -> None:
    r = v(base())
    check("valid PASS / empty concerns -> VALID", r["status"] == vjs.VALID, str(r))
    check("valid: errors empty", r["errors"] == [])


def test_valid_fail_one_high_concern() -> None:
    d = {**base(), "verdict": "FAIL", "confidence": 0.9, "requires_human_review": True,
         "concerns": [{"type": "conclusion_mismatch", "severity": "high",
                       "description": "Lean states a strict inequality; source is non-strict.",
                       "source_evidence": "V(w*) <= V(w)", "formal_evidence": "... < ..."}],
         "summary": "Conclusion does not match the source."}
    r = v(d)
    check("valid FAIL / one high-severity concern -> VALID", r["status"] == vjs.VALID, str(r))


def test_invalid_verdict() -> None:
    r = v({**base(), "verdict": "BANANA"})
    check("invalid verdict -> INVALID", r["status"] == vjs.INVALID, str(r))


def test_invalid_concern_type() -> None:
    d = {**base(), "verdict": "WARN",
         "concerns": [{"type": "made_up_type", "severity": "low", "description": "x"}]}
    r = v(d)
    check("invalid concern type -> INVALID", r["status"] == vjs.INVALID, str(r))


def test_invalid_severity() -> None:
    d = {**base(), "verdict": "WARN",
         "concerns": [{"type": "notation_ambiguity", "severity": "catastrophic", "description": "x"}]}
    r = v(d)
    check("invalid severity -> INVALID", r["status"] == vjs.INVALID, str(r))


def test_missing_required_field() -> None:
    d = base()
    del d["summary"]
    r = v(d)
    check("missing required field (schema record) -> INVALID", r["status"] == vjs.INVALID, str(r))
    check("missing-field error names the field",
          any("summary" in e for e in r["errors"]), str(r["errors"]))


def test_confidence_below_zero() -> None:
    r = v({**base(), "confidence": -0.1})
    check("confidence < 0 -> INVALID", r["status"] == vjs.INVALID, str(r))


def test_confidence_above_one() -> None:
    r = v({**base(), "confidence": 1.5})
    check("confidence > 1 -> INVALID", r["status"] == vjs.INVALID, str(r))


def test_confidence_bool_rejected() -> None:
    # bool is an int subclass in Python; it must not count as a valid confidence number.
    r = v({**base(), "confidence": True})
    check("confidence = true -> INVALID", r["status"] == vjs.INVALID, str(r))


def test_requires_human_review_must_be_bool() -> None:
    r = v({**base(), "requires_human_review": "yes"})
    check("requires_human_review non-bool -> INVALID", r["status"] == vjs.INVALID, str(r))


def test_malformed_json_no_verdict() -> None:
    r = vjs.validate_text('{ "target": "X", ')
    check("malformed JSON, no verdict -> INVALID", r["status"] == vjs.INVALID, str(r))


def test_malformed_json_with_verdict_line() -> None:
    r = vjs.validate_text('verdict: PASS_EQUIV\nnot json at all: {')
    check("malformed JSON w/ single verdict line -> PARTIAL_RECOVERED",
          r["status"] == vjs.PARTIAL_RECOVERED, str(r))
    check("recovered verdict == PASS_EQUIV", r["verdict"] == "PASS_EQUIV", str(r))


def test_legacy_minimal_verdict_only() -> None:
    # Valid JSON, no schema_version, but a recoverable verdict -> PARTIAL_RECOVERED.
    r = v({"verdict": "PASS"})
    check("legacy minimal {verdict} -> PARTIAL_RECOVERED", r["status"] == vjs.PARTIAL_RECOVERED, str(r))
    check("legacy: recovered flag set", r["recovered"] is True)


def test_top_level_not_object() -> None:
    check("top-level JSON list -> INVALID", vjs.validate_text("[1,2,3]")["status"] == vjs.INVALID)


def test_empty_input() -> None:
    check("empty input -> INVALID", vjs.validate_text("   ")["status"] == vjs.INVALID)


def test_unparseable_verdict_is_allowed() -> None:
    # UNPARSEABLE is a legitimate judge verdict value; a full record with it is VALID.
    r = v({**base(), "verdict": "UNPARSEABLE", "summary": "Source claim could not be located."})
    check("verdict UNPARSEABLE in full record -> VALID", r["status"] == vjs.VALID, str(r))


def main() -> int:
    tests = [
        test_valid_pass_empty_concerns,
        test_valid_fail_one_high_concern,
        test_invalid_verdict,
        test_invalid_concern_type,
        test_invalid_severity,
        test_missing_required_field,
        test_confidence_below_zero,
        test_confidence_above_one,
        test_confidence_bool_rejected,
        test_requires_human_review_must_be_bool,
        test_malformed_json_no_verdict,
        test_malformed_json_with_verdict_line,
        test_legacy_minimal_verdict_only,
        test_top_level_not_object,
        test_empty_input,
        test_unparseable_verdict_is_allowed,
    ]
    for t in tests:
        print(t.__name__)
        t()
    print()
    if _failures:
        print(f"FAIL: {len(_failures)} assertion(s) failed: {_failures}")
        return 1
    print("PASS: all validate_judge_schema assertions passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
