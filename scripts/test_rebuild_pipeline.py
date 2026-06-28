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
