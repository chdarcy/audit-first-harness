#!/usr/bin/env python3
"""Offline unit tests for scripts/check_axioms.py — pure parser/classifier only (no Lean).

Run directly (no pytest):  python scripts/test_check_axioms.py
Exit code 0 if every assertion passes, 1 otherwise.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_axioms as ca  # noqa: E402

MAPPING = {
    "permitted_axioms": ["propext", "Quot.sound", "Classical.choice"],
    "targets": {
        "PutCallParity": {"lean": {"module": "AuditHarness.PutCallParity",
                                   "declaration": "put_call_payoff_parity",
                                   "fully_qualified": "AuditHarness.put_call_payoff_parity"}},
        "NoFqn": {"lean": {"module": "AuditHarness.Foo", "declaration": "foo"}},
    },
}

_failures: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(f"  [{'ok  ' if cond else 'FAIL'}] {name}" + (f" -- {detail}" if (detail and not cond) else ""))
    if not cond:
        _failures.append(name)


def test_permitted_axioms_parse() -> None:
    check("permitted: from mapping", ca.permitted_axioms(MAPPING) ==
          ["propext", "Quot.sound", "Classical.choice"])
    check("permitted: default when absent", ca.permitted_axioms({}) == ca.DEFAULT_PERMITTED)


def test_resolve_targets() -> None:
    names, err = ca.resolve_targets(MAPPING, None)
    check("resolve: all targets", set(names) == {"PutCallParity", "NoFqn"} and err is None)
    names, err = ca.resolve_targets(MAPPING, "PutCallParity")
    check("resolve: one target", names == ["PutCallParity"] and err is None)
    names, err = ca.resolve_targets(MAPPING, "Nope")
    check("resolve: unknown fails and lists available",
          names == [] and err is not None and "PutCallParity" in err, err)


def test_target_lean_prefers_fqn() -> None:
    module, fqn, err = ca.target_lean(MAPPING["targets"]["PutCallParity"])
    check("target_lean: returns module+fqn",
          module == "AuditHarness.PutCallParity"
          and fqn == "AuditHarness.put_call_payoff_parity" and err is None)
    module, fqn, err = ca.target_lean(MAPPING["targets"]["NoFqn"])
    check("target_lean: missing fqn errors (no guess)", fqn is None and bool(err), err)


def test_parse_permitted_only() -> None:
    out = "'AuditHarness.put_call_payoff_parity' depends on axioms: [propext, Classical.choice, Quot.sound]"
    axioms, err = ca.parse_axioms(out)
    check("parse: permitted set", axioms == {"propext", "Classical.choice", "Quot.sound"}
          and err is None, str(axioms))


def test_parse_no_axioms() -> None:
    axioms, err = ca.parse_axioms("'Nat.succ' does not depend on any axioms")
    check("parse: empty set for no-axioms", axioms == set() and err is None)


def test_parse_sorry() -> None:
    axioms, err = ca.parse_axioms("'foo' depends on axioms: [propext, sorryAx]")
    check("parse: sorryAx captured", axioms == {"propext", "sorryAx"} and err is None, str(axioms))


def test_parse_multiline() -> None:
    out = "'x' depends on axioms: [propext,\n Classical.choice,\n Quot.sound]"
    axioms, _ = ca.parse_axioms(out)
    check("parse: handles wrapped list",
          axioms == {"propext", "Classical.choice", "Quot.sound"}, str(axioms))


def test_parse_unknown_format_errors() -> None:
    axioms, err = ca.parse_axioms("error: unknown identifier 'Foo.bar'")
    check("parse: unrecognised output -> error (no silent pass)", axioms is None and bool(err), err)
    axioms, err = ca.parse_axioms("")
    check("parse: empty output -> error", axioms is None and bool(err))


def test_classify_pass() -> None:
    status, unexpected = ca.classify({"propext", "Quot.sound"},
                                     ["propext", "Quot.sound", "Classical.choice"])
    check("classify: subset -> PASS", status == "PASS" and unexpected == [])


def test_classify_unexpected_fails() -> None:
    status, unexpected = ca.classify({"propext", "Foo.ax"},
                                     ["propext", "Quot.sound", "Classical.choice"])
    check("classify: unexpected -> FAIL", status == "FAIL" and unexpected == ["Foo.ax"], str(unexpected))


def test_classify_sorry_fails() -> None:
    status, unexpected = ca.classify({"sorryAx"}, ["propext", "Quot.sound", "Classical.choice"])
    check("classify: sorryAx -> FAIL", status == "FAIL" and unexpected == ["sorryAx"])


def main() -> int:
    tests = [
        test_permitted_axioms_parse,
        test_resolve_targets,
        test_target_lean_prefers_fqn,
        test_parse_permitted_only,
        test_parse_no_axioms,
        test_parse_sorry,
        test_parse_multiline,
        test_parse_unknown_format_errors,
        test_classify_pass,
        test_classify_unexpected_fails,
        test_classify_sorry_fails,
    ]
    for t in tests:
        print(t.__name__)
        t()
    print()
    if _failures:
        print(f"FAIL: {len(_failures)} assertion(s) failed: {_failures}")
        return 1
    print("PASS: all check_axioms assertions passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
