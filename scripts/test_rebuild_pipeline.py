#!/usr/bin/env python3
"""Offline unit tests for the --target plumbing in scripts/rebuild_pipeline.py.

Pure-function tests over target resolution, target selection, and report rendering. No
subprocess, no Lean, no Comparator, no model/API. Run directly (no pytest):

    python scripts/test_rebuild_pipeline.py

Exit code 0 if every assertion passes, 1 otherwise.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rebuild_pipeline as rp  # noqa: E402

AVAILABLE = {"PutCallParity": {}, "TwoAssetMinVar": {}}

_failures: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(f"  [{'ok  ' if cond else 'FAIL'}] {name}" + (f" -- {detail}" if (detail and not cond) else ""))
    if not cond:
        _failures.append(name)


def test_resolve_unknown_target() -> None:
    target, err = rp.resolve_target("Nope", AVAILABLE)
    check("unknown: target is None", target is None)
    check("unknown: error returned", bool(err))
    check("unknown: error lists available targets",
          err is not None and "PutCallParity" in err and "TwoAssetMinVar" in err, err)


def test_resolve_none_means_all() -> None:
    target, err = rp.resolve_target(None, AVAILABLE)
    check("no-target: target None", target is None)
    check("no-target: no error", err is None)


def test_resolve_valid_target() -> None:
    target, err = rp.resolve_target("PutCallParity", AVAILABLE)
    check("valid: returns the target", target == "PutCallParity", str(target))
    check("valid: no error", err is None)


def test_select_targets_all() -> None:
    sel = rp.select_targets(AVAILABLE, None)
    check("select-all: keeps all targets", set(sel) == set(AVAILABLE), str(set(sel)))


def test_select_targets_one() -> None:
    sel = rp.select_targets(AVAILABLE, "PutCallParity")
    check("select-one: only the selected target", list(sel) == ["PutCallParity"], str(list(sel)))


def _stages() -> list:
    a = rp.Stage("card_and_mapping").record(rp.PASS, "ledger consistent", "python validate_mapping.py")
    b = rp.Stage("judge_packages").record(rp.PASS, "6 packages", "python run_mutants.py --dry-run")
    c = rp.Stage("build").record(rp.SKIPPED, "gated")
    d = rp.Stage("no_sorry").record(rp.PASS, "no sorry", "python check_sorries.py")
    e = rp.Stage("comparator").record(rp.SKIPPED, "gated")
    return [a, b, c, d, e]


def test_report_scope_all() -> None:
    md = rp.render_report(_stages(), "2026-01-01T00:00:00Z", rp.PASS, None)
    check("report-all: scope says ALL targets", "**Target scope:** ALL targets" in md)
    check("report-all: has stage table header", "| # | stage | status | detail |" in md)


def test_report_scope_target() -> None:
    md = rp.render_report(_stages(), "2026-01-01T00:00:00Z", rp.PASS, "PutCallParity")
    check("report-target: scope names the target",
          "**Target scope:** `PutCallParity` (target-scoped run)" in md, )


def test_report_notes_and_commands() -> None:
    md = rp.render_report(_stages(), "2026-01-01T00:00:00Z", rp.PASS, "PutCallParity")
    check("report: whole-library note present", "whole-library" in md)
    check("report: comparator-only-scoped note present",
          "Only the `comparator` stage is target-scoped" in md)
    check("report: gate_decision note present", "scripts/gate_decision.py --target" in md)
    check("report: commands section present", "**Commands run:**" in md)
    check("report: a command is listed", "`python validate_mapping.py`" in md)


# --------------------------------------------------------------------------- writeback (milestone 3)
MAPPING_FIXTURE = '''version: "0.1"

targets:

  PutCallParity:
    verdict: PASS
    equivalence: null
    # Set by a human after a Comparator run.
    #   NOT_RUN | PASSED_REAL_LANDRUN | FAILED_COMPARATOR
    comparator_status: NOT_RUN
    state: HUMAN_APPROVED
    human_approved: true

  TwoAssetMinVar:
    verdict: PASS
    comparator_status: NOT_RUN
    state: HUMAN_APPROVED
'''


def test_writeback_precondition_no_target() -> None:
    err = rp.writeback_precondition_error(True, None, True)
    check("wb-no-target: errors and cites --target", bool(err) and "--target" in err, err)


def test_writeback_precondition_no_comparator() -> None:
    err = rp.writeback_precondition_error(True, "PutCallParity", False)
    check("wb-no-comparator: errors and cites --with-comparator",
          bool(err) and "--with-comparator" in err, err)


def test_writeback_precondition_ok() -> None:
    check("wb-ok: no error",
          rp.writeback_precondition_error(True, "PutCallParity", True) is None)


def test_writeback_not_requested() -> None:
    check("wb-off: no error when flag omitted",
          rp.writeback_precondition_error(False, None, False) is None)


def test_derive_pass_unknown_abi_best_effort() -> None:
    # Conservative: a bare PASS with no ABI hint must NOT claim a full sandbox.
    st, reason = rp.derive_comparator_status(rp.PASS, landrun_path="/x/landrun", abi=None)
    check("derive pass+unknown-abi: PASSED_REAL_LANDRUN_BEST_EFFORT",
          st == "PASSED_REAL_LANDRUN_BEST_EFFORT", str(st))
    check("derive pass+unknown-abi: reason cites --best-effort and COMPARATOR_LANDRUN_ABI",
          "best-effort" in reason and "COMPARATOR_LANDRUN_ABI" in reason, reason)


def test_derive_pass_fake() -> None:
    st, _ = rp.derive_comparator_status(rp.PASS, landrun_path="/x/fake-landrun.sh", abi=None)
    check("derive pass+fake-shim: PASSED_FAKE_LANDRUN", st == "PASSED_FAKE_LANDRUN", str(st))


def test_derive_pass_best_effort_abi3() -> None:
    st, _ = rp.derive_comparator_status(rp.PASS, landrun_path="/x/landrun", abi=3)
    check("derive pass+abi3: PASSED_REAL_LANDRUN_BEST_EFFORT",
          st == "PASSED_REAL_LANDRUN_BEST_EFFORT", str(st))


def test_derive_pass_real_abi5() -> None:
    st, _ = rp.derive_comparator_status(rp.PASS, landrun_path="/x/landrun", abi=5)
    check("derive pass+abi5: PASSED_REAL_LANDRUN", st == "PASSED_REAL_LANDRUN", str(st))


def test_derive_fail() -> None:
    st, _ = rp.derive_comparator_status(rp.FAIL)
    check("derive fail: FAILED_COMPARATOR", st == "FAILED_COMPARATOR", str(st))


def test_derive_skipped() -> None:
    st, _ = rp.derive_comparator_status(rp.SKIPPED)
    check("derive skipped: SKIPPED_COMPARATOR_TOOL_UNAVAILABLE",
          st == "SKIPPED_COMPARATOR_TOOL_UNAVAILABLE", str(st))


def test_set_text_updates_only_selected_target() -> None:
    new_text, old = rp.set_comparator_status_text(
        MAPPING_FIXTURE, "PutCallParity", "SKIPPED_COMPARATOR_TOOL_UNAVAILABLE")
    check("set-text: returns old value", old == "NOT_RUN", old)
    check("set-text: selected target updated",
          "comparator_status: SKIPPED_COMPARATOR_TOOL_UNAVAILABLE" in new_text)
    after_two = new_text.split("TwoAssetMinVar:")[1]
    check("set-text: other target untouched", "comparator_status: NOT_RUN" in after_two)


def test_set_text_preserves_comments() -> None:
    new_text, _ = rp.set_comparator_status_text(MAPPING_FIXTURE, "PutCallParity", "FAILED_COMPARATOR")
    check("set-text: prose comment preserved",
          "# Set by a human after a Comparator run." in new_text)
    check("set-text: vocabulary comment preserved",
          "NOT_RUN | PASSED_REAL_LANDRUN | FAILED_COMPARATOR" in new_text)


def test_set_text_unknown_target_raises() -> None:
    raised = False
    try:
        rp.set_comparator_status_text(MAPPING_FIXTURE, "Nope", "FAILED_COMPARATOR")
    except ValueError:
        raised = True
    check("set-text: unknown target raises ValueError", raised)


def test_report_shows_writeback() -> None:
    wb = {"requested": True, "performed": True, "target": "PutCallParity",
          "old": "NOT_RUN", "new": "PASSED_REAL_LANDRUN", "reason": "Comparator passed."}
    md = rp.render_report(_stages(), "t", rp.PASS, "PutCallParity", wb)
    check("report-wb: shows old -> new transition", "NOT_RUN → PASSED_REAL_LANDRUN" in md)
    md_none = rp.render_report(_stages(), "t", rp.PASS, "PutCallParity", None)
    check("report-wb: 'not requested' when None",
          "**Comparator-status writeback:** not requested" in md_none)


def main() -> int:
    tests = [
        test_resolve_unknown_target,
        test_resolve_none_means_all,
        test_resolve_valid_target,
        test_select_targets_all,
        test_select_targets_one,
        test_report_scope_all,
        test_report_scope_target,
        test_report_notes_and_commands,
        test_writeback_precondition_no_target,
        test_writeback_precondition_no_comparator,
        test_writeback_precondition_ok,
        test_writeback_not_requested,
        test_derive_pass_unknown_abi_best_effort,
        test_derive_pass_fake,
        test_derive_pass_best_effort_abi3,
        test_derive_pass_real_abi5,
        test_derive_fail,
        test_derive_skipped,
        test_set_text_updates_only_selected_target,
        test_set_text_preserves_comments,
        test_set_text_unknown_target_raises,
        test_report_shows_writeback,
    ]
    for t in tests:
        print(t.__name__)
        t()
    print()
    if _failures:
        print(f"FAIL: {len(_failures)} assertion(s) failed: {_failures}")
        return 1
    print("PASS: all rebuild-pipeline --target assertions passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
