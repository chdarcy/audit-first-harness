#!/usr/bin/env python3
"""Offline unit tests for scripts/check_equivalence.py + the shared equivalence-evidence
validator (scripts/validate_mapping.equivalence_evidence_error). Pure functions only — no Lean.

Run directly (no pytest):  python scripts/test_check_equivalence.py
Exit code 0 if every assertion passes, 1 otherwise.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_equivalence as ce  # noqa: E402
import validate_mapping as vm   # noqa: E402
import check_axioms as ca       # noqa: E402

GOOD_EQUIV = {"kind": "provable_equiv", "lemma": "AuditHarness.foo_iff",
              "module": "AuditHarness.Foo", "notes": "x"}

_failures: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(f"  [{'ok  ' if cond else 'FAIL'}] {name}" + (f" -- {detail}" if (detail and not cond) else ""))
    if not cond:
        _failures.append(name)


def test_evidence_complete_ok() -> None:
    check("evidence: complete -> None", vm.equivalence_evidence_error(GOOD_EQUIV) is None)


def test_evidence_missing_object() -> None:
    check("evidence: null -> error", bool(vm.equivalence_evidence_error(None)))
    check("evidence: non-dict -> error", bool(vm.equivalence_evidence_error("x")))


def test_evidence_wrong_kind() -> None:
    err = vm.equivalence_evidence_error({**GOOD_EQUIV, "kind": "informal_equiv"})
    check("evidence: wrong kind -> error cites kind", err is not None and "kind" in err, err)


def test_evidence_missing_lemma_module() -> None:
    err = vm.equivalence_evidence_error({"kind": "provable_equiv"})
    check("evidence: missing lemma+module -> error",
          err is not None and "lemma" in err and "module" in err, err)


def test_audit_pass_not_required() -> None:
    rec = ce.audit_target("T", {"verdict": "PASS", "equivalence": None}, ["propext"])
    check("audit: PASS -> NOT_REQUIRED", rec["status"] == "NOT_REQUIRED", rec["status"])


def test_audit_pass_equiv_not_required() -> None:
    rec = ce.audit_target("T", {"verdict": "PASS_EQUIV", "equivalence": {"direction": "x"}},
                          ["propext"])
    check("audit: PASS_EQUIV -> NOT_REQUIRED (no built lemma required)",
          rec["status"] == "NOT_REQUIRED", rec["status"])


def test_audit_provable_missing_evidence_fails() -> None:
    # No Lean is invoked: missing evidence is caught structurally before any lemma check.
    rec = ce.audit_target("T", {"verdict": "PASS_PROVABLE_EQUIV", "equivalence": None}, ["propext"])
    check("audit: PASS_PROVABLE_EQUIV w/o evidence -> FAIL", rec["status"] == "FAIL", rec["status"])
    check("audit: detail cites missing evidence",
          "missing equivalence evidence" in rec["detail"], rec["detail"])


def test_axiom_reuse_catches_sorry() -> None:
    # check_equivalence reuses the axiom audit; a lemma depending on sorryAx must classify FAIL.
    status, unexpected = ca.classify({"propext", "sorryAx"},
                                     ["propext", "Quot.sound", "Classical.choice"])
    check("reuse: sorryAx -> FAIL", status == "FAIL" and "sorryAx" in unexpected, str(unexpected))


def main() -> int:
    tests = [
        test_evidence_complete_ok,
        test_evidence_missing_object,
        test_evidence_wrong_kind,
        test_evidence_missing_lemma_module,
        test_audit_pass_not_required,
        test_audit_pass_equiv_not_required,
        test_audit_provable_missing_evidence_fails,
        test_axiom_reuse_catches_sorry,
    ]
    for t in tests:
        print(t.__name__)
        t()
    print()
    if _failures:
        print(f"FAIL: {len(_failures)} assertion(s) failed: {_failures}")
        return 1
    print("PASS: all check_equivalence assertions passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
