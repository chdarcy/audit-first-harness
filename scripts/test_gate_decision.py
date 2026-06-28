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


def summary(target: str = "T", *, totals=None, reliability=None, high_critical: int = 0) -> dict:
    """A structured-scoring summary (v0.3 1b shape) with a per-target node; defaults are perfect."""
    node = {
        "totals": {"schema_valid_rate": 1.0, "invalid_rate": 0.0, "unparseable_rate": 0.0,
                   **(totals or {})},
        "reliability": {"discriminative_recall": 1.0, "false_acceptance_rate_discriminative": 0.0,
                        "false_rejection_rate_consistency": 0.0, "consistency_accept_rate": 1.0,
                        "real_accept_rate": 1.0, **(reliability or {})},
        "high_critical_concern_count": high_critical,
    }
    return {**node, "per_target": {target: node}}


def with_metrics(status: str = gd.JM_PRESENT, summ: dict | None = None, **over) -> dict:
    s = {**base_sig(), "judge_metrics_status": status,
         "judge_metrics": summ if summ is not None else summary()}
    s.update(over)
    return s


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


# ---- v0.3 milestone 1c: conservative structured-judge-metric caps -----------

def test_metrics_absent_default_unchanged() -> None:
    # base_sig carries no judge_metrics_status key at all -> behaviour identical to today.
    d = gd.decide(base_sig())
    check("metrics absent: PROMOTE (unchanged)", d["status"] == gd.PROMOTE, d["status"])
    check("metrics absent: status NOT_RUN", d["judge_metrics_status"] == gd.JM_NOT_RUN)
    check("metrics absent: no cap object", d["judge_metric_cap"] is None)


def test_explicit_not_run_no_block() -> None:
    d = gd.decide(with_metrics(status=gd.JM_NOT_RUN, summ=None))
    check("NOT_RUN: PROMOTE (no block)", d["status"] == gd.PROMOTE, d["status"])


def test_perfect_metrics_still_promote() -> None:
    d = gd.decide(with_metrics())
    check("perfect metrics: PROMOTE", d["status"] == gd.PROMOTE, d["status"])
    check("perfect metrics: cap not applied", d["judge_metric_cap"]["applied"] is False)


def test_formal_fail_blocks_despite_perfect_metrics() -> None:
    d = gd.decide(with_metrics(build_status="FAIL"))
    check("build FAIL + perfect metrics: BLOCK", d["status"] == gd.BLOCK, d["status"])
    check("build FAIL: cap not applied", d["judge_metric_cap"]["applied"] is False)


def test_metrics_never_upgrade_block() -> None:
    d = gd.decide(with_metrics(mapping_present=False))
    check("missing mapping + perfect metrics: still BLOCK", d["status"] == gd.BLOCK, d["status"])
    check("metrics never upgrade to PROMOTE", d["status"] != gd.PROMOTE)


def test_bad_recall_caps_human_review() -> None:
    d = gd.decide(with_metrics(summ=summary(reliability={"discriminative_recall": 0.5})))
    check("bad structured recall: HUMAN_REVIEW", d["status"] == gd.HUMAN_REVIEW, d["status"])
    check("cap reason cites recall",
          any("recall" in r.lower() for r in d["judge_metric_cap"]["reasons"]))


def test_false_acceptance_caps_human_review() -> None:
    d = gd.decide(with_metrics(
        summ=summary(reliability={"false_acceptance_rate_discriminative": 0.5})))
    check("false acceptance on discriminative: HUMAN_REVIEW", d["status"] == gd.HUMAN_REVIEW, d["status"])


def test_invalid_schema_metrics_caps_human_review() -> None:
    d = gd.decide(with_metrics(
        summ=summary(totals={"schema_valid_rate": 0.8, "invalid_rate": 0.2})))
    check("invalid schema metrics: HUMAN_REVIEW", d["status"] == gd.HUMAN_REVIEW, d["status"])


def test_invalid_status_caps_human_review() -> None:
    d = gd.decide(with_metrics(status=gd.JM_INVALID, summ=None))
    check("INVALID metrics status: HUMAN_REVIEW", d["status"] == gd.HUMAN_REVIEW, d["status"])
    check("INVALID metrics: cap applied", d["judge_metric_cap"]["applied"] is True)


def test_high_critical_concern_caps_human_review() -> None:
    d = gd.decide(with_metrics(summ=summary(high_critical=2)))
    check("high/critical concerns: HUMAN_REVIEW", d["status"] == gd.HUMAN_REVIEW, d["status"])
    check("cap reason cites concerns",
          any("concern" in r.lower() for r in d["judge_metric_cap"]["reasons"]))


def test_cap_reason_recorded() -> None:
    d = gd.decide(with_metrics(summ=summary(reliability={"discriminative_recall": 0.5})))
    cap = d["judge_metric_cap"]
    check("cap applied True", cap["applied"] is True)
    check("cap from PROMOTE", cap["capped_from"] == gd.PROMOTE)
    check("cap to HUMAN_REVIEW", cap["capped_to"] == gd.HUMAN_REVIEW)
    check("cap reasons non-empty", len(cap["reasons"]) >= 1)
    check("disclaimer present (judge != oracle)",
          any("oracle" in r.lower() for r in d["reasons"]))


def test_per_target_metrics_preferred() -> None:
    # top-level recall perfect, but the per-target node for T is bad -> per-target wins -> cap.
    # (build the two nodes independently so they share no nested dicts.)
    perfect_node = {
        "totals": {"schema_valid_rate": 1.0, "invalid_rate": 0.0, "unparseable_rate": 0.0},
        "reliability": {"discriminative_recall": 1.0, "false_acceptance_rate_discriminative": 0.0,
                        "false_rejection_rate_consistency": 0.0},
        "high_critical_concern_count": 0,
    }
    bad_node = {
        "totals": {"schema_valid_rate": 1.0, "invalid_rate": 0.0, "unparseable_rate": 0.0},
        "reliability": {"discriminative_recall": 0.5, "false_acceptance_rate_discriminative": 0.0,
                        "false_rejection_rate_consistency": 0.0},
        "high_critical_concern_count": 0,
    }
    summ = {**perfect_node, "per_target": {"T": bad_node}}  # top-level perfect, per-target bad
    d = gd.decide(with_metrics(summ=summ))
    check("per-target node preferred over top level", d["status"] == gd.HUMAN_REVIEW, d["status"])


def test_none_metric_does_not_cap() -> None:
    # consistency rates are None (e.g. no consistency variants judged) -> must not trigger a cap.
    summ = summary(reliability={"false_rejection_rate_consistency": None,
                                "consistency_accept_rate": None})
    d = gd.decide(with_metrics(summ=summ))
    check("None metric does not cap: PROMOTE", d["status"] == gd.PROMOTE, d["status"])


def test_metrics_do_not_upgrade_real_fail() -> None:
    # base is REVISE (real FAIL); perfect metrics must not upgrade it to PROMOTE.
    d = gd.decide(with_metrics(real_verdict="FAIL"))
    check("real FAIL + perfect metrics: still REVISE", d["status"] == gd.REVISE, d["status"])


def test_display_path_outside_root_does_not_raise() -> None:
    # --output is a testing override and may point outside the repo; formatting must not raise.
    outside = Path(tempfile.gettempdir()) / "definitely-not-in-repo" / "gate_out.yaml"
    try:
        s_out = gd.display_path(outside)
        raised = False
    except Exception:  # noqa: BLE001
        s_out = ""
        raised = True
    check("display_path(outside ROOT): no raise", not raised)
    check("display_path(outside ROOT): returns the path as-is", s_out == str(outside), s_out)
    # A path inside ROOT is still shown repo-relative.
    inside = gd.ROOT / "docs" / "promotion" / "T.yaml"
    check("display_path(inside ROOT): repo-relative",
          gd.display_path(inside) == str(Path("docs") / "promotion" / "T.yaml"),
          gd.display_path(inside))


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
        test_metrics_absent_default_unchanged,
        test_explicit_not_run_no_block,
        test_perfect_metrics_still_promote,
        test_formal_fail_blocks_despite_perfect_metrics,
        test_metrics_never_upgrade_block,
        test_bad_recall_caps_human_review,
        test_false_acceptance_caps_human_review,
        test_invalid_schema_metrics_caps_human_review,
        test_invalid_status_caps_human_review,
        test_high_critical_concern_caps_human_review,
        test_cap_reason_recorded,
        test_per_target_metrics_preferred,
        test_none_metric_does_not_cap,
        test_metrics_do_not_upgrade_real_fail,
        test_display_path_outside_root_does_not_raise,
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
