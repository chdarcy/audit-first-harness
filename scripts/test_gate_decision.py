#!/usr/bin/env python3
"""Offline unit tests for scripts/gate_decision.py.

Pure-function tests over `decide()` (no file I/O, no model/API) plus a small parser test for
the markdown pipeline-report reader. Run directly (no pytest):

    python scripts/test_gate_decision.py

Exit code 0 if every assertion passes, 1 otherwise.

Covers the required cases:
  - missing target/mapping            -> BLOCK
  - missing scored judge result       -> BLOCK (with a generate-results next step)
  - real mapping FAIL                 -> REVISE
  - low discriminative recall + pass  -> HUMAN_REVIEW
  - all thresholds pass               -> PROMOTE
  - unrecoverable parse errors        -> BLOCK
  - PASSED_FAKE_LANDRUN               -> not a high-confidence PROMOTE
plus: unverified comparator -> HUMAN_REVIEW, and human override -> PROMOTE.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gate_decision as gd  # noqa: E402


def base_sig() -> dict:
    """A fully promotable signal set; individual tests override one or two keys."""
    return {
        "target": "T",
        "mapping_present": True,
        "card_present": True,
        "review_present": True,
        "human_approved": True,
        "declaration_present": True,
        "scored_present": True,
        "scored_path_hint": "docs/judge_results/T_scored.yaml",
        "provenance_match": True,
        "unrecoverable_parse_errors": 0,
        "real_row_present": True,
        "real_verdict": "PASS",
        "discriminative_recall": 1.0,
        "consistency_false_alarm_rate": 0.0,
        "malformed_yaml_rate": 0.0,
        "recovered_verdict_count": 0,
        "build_status": "PASS",
        "no_sorry_status": "PASS",
        "axiom_audit_status": "PASS",
        "equivalence_check_status": "PASS",
        "comparator_pipeline": "PASS",
        "comparator_status": "PASSED_REAL_LANDRUN",
        "mapping_verdict": "PASS",
        "human_override": False,
    }


_failures: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(f"  [{'ok  ' if cond else 'FAIL'}] {name}" + (f" -- {detail}" if (detail and not cond) else ""))
    if not cond:
        _failures.append(name)


def test_missing_mapping_blocks() -> None:
    d = gd.decide({**base_sig(), "mapping_present": False})
    check("missing-mapping: BLOCK", d["status"] == gd.BLOCK, d["status"])


def test_missing_scored_blocks() -> None:
    d = gd.decide({**base_sig(), "scored_present": False, "real_row_present": False,
                   "real_verdict": None, "discriminative_recall": None})
    check("missing-scored: BLOCK", d["status"] == gd.BLOCK, d["status"])
    check("missing-scored: reason mentions scored result",
          any("scored judge result" in r.lower() for r in d["reasons"]))
    check("missing-scored: next step generate_judge_results",
          "generate_judge_results" in d["allowed_next_steps"])


def test_real_fail_revises() -> None:
    d = gd.decide({**base_sig(), "real_verdict": "FAIL"})
    check("real-FAIL: REVISE", d["status"] == gd.REVISE, d["status"])


def test_real_warn_human_review() -> None:
    d = gd.decide({**base_sig(), "real_verdict": "WARN"})
    check("real-WARN: HUMAN_REVIEW", d["status"] == gd.HUMAN_REVIEW, d["status"])


def test_low_recall_human_review() -> None:
    d = gd.decide({**base_sig(), "discriminative_recall": 0.667})
    check("low-recall: HUMAN_REVIEW (not BLOCK)", d["status"] == gd.HUMAN_REVIEW, d["status"])
    check("low-recall: reason cites recall", any("recall" in r.lower() for r in d["reasons"]))


def test_all_pass_promotes() -> None:
    d = gd.decide(base_sig())
    check("all-pass: PROMOTE", d["status"] == gd.PROMOTE, d["status"])
    check("all-pass: confidence high", d["confidence"] == "high", d["confidence"])


def test_unrecoverable_parse_blocks() -> None:
    d = gd.decide({**base_sig(), "unrecoverable_parse_errors": 1})
    check("parse-errors: BLOCK", d["status"] == gd.BLOCK, d["status"])


def test_fake_landrun_not_high_confidence_promote() -> None:
    d = gd.decide({**base_sig(), "comparator_status": "PASSED_FAKE_LANDRUN"})
    check("fake-landrun: not PROMOTE", d["status"] != gd.PROMOTE, d["status"])
    check("fake-landrun: HUMAN_REVIEW", d["status"] == gd.HUMAN_REVIEW, d["status"])


def test_unverified_comparator_human_review() -> None:
    # PutCallParity-shaped: build passed, comparator not run, recall imperfect.
    d = gd.decide({**base_sig(), "comparator_pipeline": "SKIPPED", "comparator_status": "NOT_RUN",
                   "discriminative_recall": 0.667})
    check("unverified-comparator: HUMAN_REVIEW", d["status"] == gd.HUMAN_REVIEW, d["status"])
    check("unverified-comparator: not PROMOTE", d["status"] != gd.PROMOTE)


def test_human_override_promotes_despite_caveat() -> None:
    d = gd.decide({**base_sig(), "discriminative_recall": 0.667, "human_override": True})
    check("override: PROMOTE", d["status"] == gd.PROMOTE, d["status"])
    check("override: confidence medium", d["confidence"] == "medium", d["confidence"])


def test_axiom_audit_fail_blocks() -> None:
    d = gd.decide({**base_sig(), "axiom_audit_status": "FAIL"})
    check("axiom-audit FAIL: BLOCK", d["status"] == gd.BLOCK, d["status"])


def test_axiom_audit_unverified_human_review() -> None:
    d = gd.decide({**base_sig(), "axiom_audit_status": "SKIPPED"})
    check("axiom-audit SKIPPED: not PROMOTE", d["status"] != gd.PROMOTE, d["status"])
    check("axiom-audit SKIPPED: HUMAN_REVIEW", d["status"] == gd.HUMAN_REVIEW, d["status"])


def test_equivalence_check_fail_blocks() -> None:
    d = gd.decide({**base_sig(), "equivalence_check_status": "FAIL"})
    check("equiv-check FAIL: BLOCK", d["status"] == gd.BLOCK, d["status"])


def test_judge_provable_equiv_without_check_human_review() -> None:
    # A bare judge PASS_PROVABLE_EQUIV must not promote without the equivalence check passing.
    d = gd.decide({**base_sig(), "real_verdict": "PASS_PROVABLE_EQUIV",
                   "equivalence_check_status": "SKIPPED"})
    check("PPE judge + equiv SKIPPED: not PROMOTE", d["status"] != gd.PROMOTE, d["status"])
    check("PPE judge + equiv SKIPPED: HUMAN_REVIEW", d["status"] == gd.HUMAN_REVIEW, d["status"])


def test_mapping_provable_equiv_without_check_human_review() -> None:
    d = gd.decide({**base_sig(), "mapping_verdict": "PASS_PROVABLE_EQUIV",
                   "equivalence_check_status": "SKIPPED"})
    check("PPE mapping + equiv SKIPPED: HUMAN_REVIEW", d["status"] == gd.HUMAN_REVIEW, d["status"])


def test_provable_equiv_with_check_promotes() -> None:
    d = gd.decide({**base_sig(), "real_verdict": "PASS_PROVABLE_EQUIV",
                   "mapping_verdict": "PASS_PROVABLE_EQUIV", "equivalence_check_status": "PASS"})
    check("PPE + equiv PASS: PROMOTE", d["status"] == gd.PROMOTE, d["status"])


def test_pipeline_report_parser() -> None:
    md = (
        "| # | stage | status | detail |\n"
        "|---|---|---|---|\n"
        "| 3 | `build` | ✅ PASS | Build completed successfully (829 jobs). |\n"
        "| 4 | `no_sorry` | ✅ PASS |  ok |\n"
        "| 5 | `comparator` | ⏭️ SKIPPED | SKIPPED_COMPARATOR_TOOL_UNAVAILABLE: ... |\n"
    )
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "docs").mkdir()
        (root / "docs" / "pipeline_report.md").write_text(md, encoding="utf-8")
        st = gd.read_formal_status(root)
    check("parser: build PASS", st.get("build") == "PASS", st)
    check("parser: no_sorry PASS", st.get("no_sorry") == "PASS", st)
    # The detail column also contains 'SKIPPED_...'; the status cell must still win.
    check("parser: comparator SKIPPED", st.get("comparator") == "SKIPPED", st)


def main() -> int:
    tests = [
        test_missing_mapping_blocks,
        test_missing_scored_blocks,
        test_real_fail_revises,
        test_real_warn_human_review,
        test_low_recall_human_review,
        test_all_pass_promotes,
        test_unrecoverable_parse_blocks,
        test_fake_landrun_not_high_confidence_promote,
        test_unverified_comparator_human_review,
        test_human_override_promotes_despite_caveat,
        test_axiom_audit_fail_blocks,
        test_axiom_audit_unverified_human_review,
        test_equivalence_check_fail_blocks,
        test_judge_provable_equiv_without_check_human_review,
        test_mapping_provable_equiv_without_check_human_review,
        test_provable_equiv_with_check_promotes,
        test_pipeline_report_parser,
    ]
    for t in tests:
        print(t.__name__)
        t()
    print()
    if _failures:
        print(f"FAIL: {len(_failures)} assertion(s) failed: {_failures}")
        return 1
    print("PASS: all gate-decision assertions passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
