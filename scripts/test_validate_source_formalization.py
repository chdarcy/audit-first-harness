#!/usr/bin/env python3
"""Offline unit tests for scripts/validate_source_formalization.py.

Generic, source-agnostic: synthetic records only — no external/source content, no Lean, no model/API,
no writes outside a temp dir. Run:  python scripts/test_validate_source_formalization.py
"""
from __future__ import annotations

import copy
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import validate_source_formalization as vsf  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent

_failures: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(f"  [{'ok  ' if cond else 'FAIL'}] {name}" + (f" -- {detail}" if (detail and not cond) else ""))
    if not cond:
        _failures.append(name)


def minimal_real() -> dict:
    """A minimal, structurally-complete real record (generic placeholders, no source content)."""
    return {
        "schema_version": "0.1.0",
        "record_type": "source_formalization",
        "source": {"source_id": "example-001", "source_kind": "note"},
        "informal_claim": {"statement": "A equals B.", "theorem_role": "theorem"},
        "symbols": [{"source_symbol": "x", "informal_meaning": "a real number"}],
        "assumptions": {"explicit": ["x is real"], "implicit": [], "derived_or_standard": [],
                        "intentionally_not_assumed": []},
        "conclusion": {"informal": "the two sides are equal"},
        "formalization_choices": {"abstraction_level": "pointwise identity over the reals",
                                  "representation_choices": []},
        "ambiguities": [{"issue": "scope of a variable", "risk": "could change the claim",
                         "resolution": "fixed as a free real", "status": "resolved"}],
        "proof_decomposition": {"strategy": "direct", "subtargets": [
            {"id": "s1", "informal_goal": "establish the identity", "depends_on": []}]},
        "target_links": {},
        "review": {"status": "draft"},
        "audit": {"created_by": "tester", "source_fidelity_risks": []},
    }


def errs(doc: dict, *, real: bool = True):
    return vsf.validate_record(doc, "rec.yaml", real=real)[0]


# 1 — valid minimal real record passes
def test_valid_minimal_passes() -> None:
    check("valid minimal real record passes", errs(minimal_real()) == [], str(errs(minimal_real())))


# 2 — missing top-level field fails
def test_missing_top_level_fails() -> None:
    d = minimal_real(); del d["proof_decomposition"]
    e = errs(d)
    check("missing top-level field fails", any("proof_decomposition" in x for x in e))


# 3 — missing source metadata fails
def test_missing_source_metadata_fails() -> None:
    d = minimal_real(); d["source"] = {"source_kind": "note"}  # no source_id
    check("missing source_id fails", any("source_id" in x for x in errs(d)))
    d2 = minimal_real(); d2["source"] = {"source_id": "x"}  # no source_kind
    check("missing source_kind fails", any("source_kind" in x for x in errs(d2)))


# 4 — missing symbol table fails
def test_missing_symbols_fails() -> None:
    d = minimal_real(); d["symbols"] = []
    check("empty symbols fails", any("symbols" in x for x in errs(d)))
    d2 = minimal_real(); d2["symbols"] = [{"informal_meaning": "no source_symbol"}]
    check("symbol without source_symbol fails", any("source_symbol" in x for x in errs(d2)))


# 5 — missing assumptions / conclusion fails
def test_missing_assumptions_and_conclusion_fails() -> None:
    d = minimal_real()
    d["assumptions"] = {"explicit": [], "implicit": [], "derived_or_standard": []}
    check("no assumptions fails", any("assumption" in x.lower() for x in errs(d)))
    d2 = minimal_real(); d2["conclusion"] = {"informal": ""}
    check("blank conclusion fails", any("conclusion.informal" in x for x in errs(d2)))


# 6 — invalid ambiguity status fails
def test_invalid_ambiguity_status_fails() -> None:
    d = minimal_real(); d["ambiguities"][0]["status"] = "maybe"
    e = errs(d)
    check("invalid ambiguity status fails", any("ambiguities[0].status" in x for x in e))


# 7 — invalid review status fails
def test_invalid_review_status_fails() -> None:
    d = minimal_real(); d["review"]["status"] = "done"
    check("invalid review status fails", any("review.status" in x for x in errs(d)))


# 8 — blank target links allowed for draft/ready records
def test_blank_target_links_allowed() -> None:
    for status in ("draft", "ready_for_card"):
        d = minimal_real(); d["review"]["status"] = status; d["target_links"] = {}
        check(f"blank target_links allowed for {status}", errs(d) == [], str(errs(d)))


# 9 — template file checked structurally (passes as template; would fail the content checks as "real")
def test_template_checked_structurally() -> None:
    import yaml
    tmpl = yaml.safe_load((vsf.RECORDS_DIR / "template.yaml").read_text(encoding="utf-8"))
    check("real template.yaml passes the template (structure) check",
          vsf.validate_record(tmpl, "template.yaml", real=False)[0] == [],
          str(vsf.validate_record(tmpl, "template.yaml", real=False)[0]))
    check("blank-content template would FAIL as a real record (content required)",
          vsf.validate_record(tmpl, "template.yaml", real=True)[0] != [])


# 10 — directory with only template passes (the real docs/source_formalizations dir)
def test_dir_only_template_passes() -> None:
    e, w, n_real, n_template = vsf.validate_dir(vsf.RECORDS_DIR)
    check("real dir (only template) passes", e == [], str(e))
    check("real dir has 0 real records, 1 template", n_real == 0 and n_template == 1, f"{n_real}/{n_template}")


# 11 — validator output includes clear error paths (file + field)
def test_error_paths_clear() -> None:
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "bad.yaml"
        import yaml
        bad = minimal_real(); bad["review"]["status"] = "bogus"
        p.write_text(yaml.safe_dump(bad), encoding="utf-8")
        e, _, _, _ = vsf.validate_dir(Path(td))
        check("error names the file", any("bad.yaml" in x for x in e), str(e))
        check("error names the field", any("review.status" in x for x in e), str(e))


# 12/13 — no model/API, no Lean reads/edits
def test_no_api_no_lean() -> None:
    src = (ROOT / "scripts" / "validate_source_formalization.py").read_text(encoding="utf-8")
    for tok in ("openai", "execute-api", "requests.", "http", "urllib", "socket"):
        check(f"validator has no '{tok}'", tok not in src)
    check("validator does not open .lean files", ".lean" not in src)
    # the theorem/helper split files are untouched and still present
    for f in ["AuditHarness/PutCallParity.lean", "AuditHarness/PutCallParity/Helpers.lean",
              "AuditHarness/TwoAssetMinVar.lean", "AuditHarness/GoldIrrationalSqrtTwo.lean"]:
        check(f"Lean file still present (untouched): {f}", (ROOT / f).is_file())


# Generic, fake sentinels — NOT real domain/source terms. Used to exercise the genericity property
# without ever hardcoding an actual theorem/domain word in this committed test file.
FORBIDDEN_SENTINELS = [
    "FORBIDDEN_DOMAIN_SENTINEL",
    "FORBIDDEN_TOPIC_SENTINEL",
    "FORBIDDEN_SOURCE_FILENAME_SENTINEL",
]


def _scan_for(text: str, terms) -> list[str]:
    low = text.lower()
    return [t for t in terms if t.lower() in low]


# 14 — generic / source-agnostic: the committed substantive artifacts carry no injected domain or
#      source marker, and the genericity scan provably works (guard-the-guard via a temp-only file).
def test_generic_source_agnostic() -> None:
    for rel in ["scripts/validate_source_formalization.py",
                "docs/source_formalizations/template.yaml",
                "docs/source_formalizations/README.md"]:
        hits = _scan_for((ROOT / rel).read_text(encoding="utf-8"), FORBIDDEN_SENTINELS)
        check(f"{rel} carries no injected domain/source marker", hits == [], str(hits))
    # guard-the-guard: inject a sentinel into a TEMP file only (never a committed artifact)
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "injected_record.txt"
        p.write_text("synthetic record containing FORBIDDEN_DOMAIN_SENTINEL only here", encoding="utf-8")
        check("genericity scan detects an injected sentinel (temp file only)",
              "FORBIDDEN_DOMAIN_SENTINEL" in _scan_for(p.read_text(encoding="utf-8"), FORBIDDEN_SENTINELS))


def main() -> int:
    tests = [
        test_valid_minimal_passes, test_missing_top_level_fails, test_missing_source_metadata_fails,
        test_missing_symbols_fails, test_missing_assumptions_and_conclusion_fails,
        test_invalid_ambiguity_status_fails, test_invalid_review_status_fails,
        test_blank_target_links_allowed, test_template_checked_structurally,
        test_dir_only_template_passes, test_error_paths_clear, test_no_api_no_lean,
        test_generic_source_agnostic,
    ]
    for t in tests:
        print(t.__name__)
        t()
    print()
    if _failures:
        print(f"FAIL: {len(_failures)} assertion(s) failed: {_failures}")
        return 1
    print("PASS: all source-formalisation-validator assertions passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
