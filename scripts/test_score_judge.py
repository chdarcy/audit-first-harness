#!/usr/bin/env python3
"""Offline unit tests for the structured judge-scoring path of scripts/score_judge.py.

Pure functions only — no Lean, no API, no model. Fixtures are inline synthetic structured
judge records (schema_version 0.3.0). Run directly:  python scripts/test_score_judge.py
Exit 0 if every assertion passes, 1 otherwise.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import score_judge as sj  # noqa: E402

MUTANTS_DIR = Path(__file__).resolve().parent.parent / "docs" / "mutants"

# Synthetic answer key: {target: {candidate_id: class}}.
KEY = {
    "GoldIrrationalSqrtTwo": {"real": "real", "GIST-D3": "discriminative",
                              "GIST-D5": "discriminative", "GIST-C1": "consistency"},
    "TwoAssetMinVar": {"real": "real", "TAM-D1": "discriminative"},
}

_failures: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(f"  [{'ok  ' if cond else 'FAIL'}] {name}" + (f" -- {detail}" if (detail and not cond) else ""))
    if not cond:
        _failures.append(name)


def rec(target, candidate_id, verdict, *, concerns=None, schema_version="0.3.0",
        confidence=0.9, drop=None) -> dict:
    """Build a structured record; `drop` removes a key (to force INVALID); schema_version=None
    yields a legacy/minimal record (no schema_version)."""
    r = {
        "schema_version": schema_version,
        "target": target,
        "source_ref": f"thm:{target.lower()}",
        "candidate_id": candidate_id,
        "verdict": verdict,
        "confidence": confidence,
        "concerns": concerns or [],
        "summary": "synthetic",
        "requires_human_review": False,
    }
    if schema_version is None:
        del r["schema_version"]
    if drop:
        r.pop(drop, None)
    return r


def concern(ctype="weakened_statement", severity="high"):
    return {"type": ctype, "severity": severity, "description": "d",
            "source_evidence": "s", "formal_evidence": "f"}


def test_valid_pass_on_real() -> None:
    s = sj.score_structured_records([rec("GoldIrrationalSqrtTwo", "real", "PASS")], KEY)
    check("real PASS -> real_accept_rate 1.0", s["reliability"]["real_accept_rate"] == 1.0, str(s["reliability"]))
    check("real PASS -> schema_valid_rate 1.0", s["totals"]["schema_valid_rate"] == 1.0)


def test_valid_fail_on_discriminative() -> None:
    s = sj.score_structured_records(
        [rec("GoldIrrationalSqrtTwo", "GIST-D3", "FAIL", concerns=[concern()])], KEY)
    check("discriminative FAIL -> recall 1.0", s["reliability"]["discriminative_recall"] == 1.0, str(s["reliability"]))
    check("discriminative FAIL -> false_acceptance 0.0",
          s["reliability"]["false_acceptance_rate_discriminative"] == 0.0)


def test_valid_warn_on_discriminative() -> None:
    s = sj.score_structured_records([rec("GoldIrrationalSqrtTwo", "GIST-D5", "WARN")], KEY)
    check("discriminative WARN counts as reject (recall 1.0)",
          s["reliability"]["discriminative_recall"] == 1.0, str(s["reliability"]))


def test_false_acceptance_of_discriminative() -> None:
    s = sj.score_structured_records([rec("GoldIrrationalSqrtTwo", "GIST-D3", "PASS")], KEY)
    check("discriminative PASS -> recall 0.0", s["reliability"]["discriminative_recall"] == 0.0, str(s["reliability"]))
    check("discriminative PASS -> false_acceptance 1.0",
          s["reliability"]["false_acceptance_rate_discriminative"] == 1.0)


def test_false_rejection_of_consistency() -> None:
    s = sj.score_structured_records([rec("GoldIrrationalSqrtTwo", "GIST-C1", "FAIL")], KEY)
    check("consistency FAIL -> consistency_accept_rate 0.0",
          s["reliability"]["consistency_accept_rate"] == 0.0, str(s["reliability"]))
    check("consistency FAIL -> false_rejection 1.0",
          s["reliability"]["false_rejection_rate_consistency"] == 1.0)


def test_unparseable_counted_separately() -> None:
    s = sj.score_structured_records([rec("GoldIrrationalSqrtTwo", "GIST-D3", "UNPARSEABLE")], KEY)
    check("UNPARSEABLE -> unparseable total 1", s["totals"]["unparseable"] == 1, str(s["totals"]))
    check("UNPARSEABLE -> not usable (recall None)", s["reliability"]["discriminative_recall"] is None)
    check("UNPARSEABLE schema record is still VALID", s["totals"]["schema_valid"] == 1)


def test_partial_recovered_counted_separately() -> None:
    # legacy/minimal record: no schema_version, recoverable verdict
    s = sj.score_structured_records([rec("GoldIrrationalSqrtTwo", "real", "PASS", schema_version=None)], KEY)
    check("legacy minimal -> partial_recovered 1", s["totals"]["partial_recovered"] == 1, str(s["totals"]))
    check("legacy minimal -> schema_valid 0", s["totals"]["schema_valid"] == 0)
    check("partial w/ verdict still usable (real_accept 1.0)", s["reliability"]["real_accept_rate"] == 1.0)


def test_invalid_schema_counted_separately() -> None:
    bad = rec("GoldIrrationalSqrtTwo", "GIST-D3", "FAIL", drop="summary")  # missing required field
    s = sj.score_structured_records([bad], KEY)
    check("missing field -> invalid 1", s["totals"]["invalid"] == 1, str(s["totals"]))
    check("invalid schema -> not usable (recall None)", s["reliability"]["discriminative_recall"] is None)


def test_per_target_aggregation() -> None:
    records = [
        rec("GoldIrrationalSqrtTwo", "real", "PASS"),
        rec("GoldIrrationalSqrtTwo", "GIST-D3", "FAIL"),
        rec("TwoAssetMinVar", "real", "PASS"),
        rec("TwoAssetMinVar", "TAM-D1", "PASS"),  # false acceptance
    ]
    s = sj.score_structured_records(records, KEY)
    check("per_target has both targets",
          set(s["per_target"]) == {"GoldIrrationalSqrtTwo", "TwoAssetMinVar"}, str(set(s["per_target"])))
    check("GIST target recall 1.0",
          s["per_target"]["GoldIrrationalSqrtTwo"]["reliability"]["discriminative_recall"] == 1.0)
    check("TAM target recall 0.0 (false acceptance)",
          s["per_target"]["TwoAssetMinVar"]["reliability"]["discriminative_recall"] == 0.0)
    check("global total == 4", s["totals"]["total"] == 4)


def test_high_critical_concern_counting() -> None:
    records = [
        rec("GoldIrrationalSqrtTwo", "GIST-D3", "FAIL",
            concerns=[concern(severity="high"), concern(severity="critical"), concern(severity="low")]),
        rec("GoldIrrationalSqrtTwo", "GIST-D5", "WARN", concerns=[concern(severity="medium")]),
    ]
    s = sj.score_structured_records(records, KEY)
    check("high+critical counted (2), low/medium excluded",
          s["high_critical_concern_count"] == 2, str(s["high_critical_concern_count"]))
    check("concern_types tallied",
          s["concern_types"].get("weakened_statement") == 4, str(s["concern_types"]))


def test_unknown_candidate_is_isolated() -> None:
    s = sj.score_structured_records([rec("GoldIrrationalSqrtTwo", "NOT-A-MUTANT", "PASS")], KEY)
    check("unknown candidate_id -> class 'unknown', no class rates",
          s["reliability"]["discriminative_recall"] is None
          and s["counts_by_class"].get("unknown", {}).get("n") == 1, str(s["counts_by_class"]))


def test_answer_key_from_real_mutants_files() -> None:
    # Read-only wiring check against the real docs/mutants/*.yaml.
    ak = sj.build_structured_answer_key(MUTANTS_DIR)
    check("answer key includes GoldIrrationalSqrtTwo", "GoldIrrationalSqrtTwo" in ak, str(list(ak)))
    g = ak.get("GoldIrrationalSqrtTwo", {})
    check("real -> 'real'", g.get("real") == "real")
    check("GIST-D3 -> discriminative", g.get("GIST-D3") == "discriminative")
    check("GIST-C1 -> consistency", g.get("GIST-C1") == "consistency")


def main() -> int:
    tests = [
        test_valid_pass_on_real,
        test_valid_fail_on_discriminative,
        test_valid_warn_on_discriminative,
        test_false_acceptance_of_discriminative,
        test_false_rejection_of_consistency,
        test_unparseable_counted_separately,
        test_partial_recovered_counted_separately,
        test_invalid_schema_counted_separately,
        test_per_target_aggregation,
        test_high_critical_concern_counting,
        test_unknown_candidate_is_isolated,
        test_answer_key_from_real_mutants_files,
    ]
    for t in tests:
        print(t.__name__)
        t()
    print()
    if _failures:
        print(f"FAIL: {len(_failures)} assertion(s) failed: {_failures}")
        return 1
    print("PASS: all structured score_judge assertions passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
