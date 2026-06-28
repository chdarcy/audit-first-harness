#!/usr/bin/env python3
"""Offline unit tests for scripts/source_review_decision.py (pre-proof source-fidelity gate).

Pure functions over synthetic structured-scoring summaries — no Lean, no model/API, no file writes.
Run:  python scripts/test_source_review_decision.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import source_review_decision as sr  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent

_failures: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(f"  [{'ok  ' if cond else 'FAIL'}] {name}" + (f" -- {detail}" if (detail and not cond) else ""))
    if not cond:
        _failures.append(name)


def summary(target="T", *, real_verdict="PASS", real_schema="VALID", real_high=0,
            recall=1.0, fa=0.0, fr=0.0, invalid=0.0, unparseable=0.0, with_real=True) -> dict:
    """A structured-scoring summary (score_judge.score_structured_records shape) for one target."""
    per_record = []
    if with_real:
        per_record.append({
            "target": target, "candidate_id": "real", "class": "real",
            "schema_status": real_schema, "verdict": real_verdict,
            "verdict_bucket": "accept" if real_verdict in sr.ACCEPT else "reject",
            "usable": real_schema != "INVALID" and real_verdict not in (None, "UNPARSEABLE"),
            "is_unparseable": real_verdict == "UNPARSEABLE",
            "high_critical_concerns": real_high, "concern_types": [],
        })
    node = {
        "reliability": {"discriminative_recall": recall,
                        "false_acceptance_rate_discriminative": fa,
                        "false_rejection_rate_consistency": fr},
        "totals": {"invalid_rate": invalid, "unparseable_rate": unparseable},
    }
    return {**node, "per_record": per_record, "per_target": {target: node}}


def d(**kw):
    return sr.decide_source_review(summary("T", **kw), "T")


# 1 — real PASS + perfect calibration -> PASS
def test_pass() -> None:
    r = d()
    check("real PASS + perfect calibration -> SOURCE_REVIEW_PASS", r["status"] == sr.PASS, r["status"])


# 2 — real WARN -> human review
def test_warn() -> None:
    r = d(real_verdict="WARN")
    check("real WARN -> HUMAN_REVIEW", r["status"] == sr.HUMAN_REVIEW, r["status"])


# 3 — real FAIL -> revise
def test_fail() -> None:
    r = d(real_verdict="FAIL")
    check("real FAIL -> REVISE", r["status"] == sr.REVISE, r["status"])
    check("FAIL reason mentions revision", any("revis" in x.lower() for x in r["reasons"]))


# 4 — real PASS but recall < 1.0 -> human review (lower trust)
def test_low_recall_caps() -> None:
    r = d(recall=0.667)
    check("real PASS + recall 0.667 -> HUMAN_REVIEW", r["status"] == sr.HUMAN_REVIEW, r["status"])
    check("reason cites recall / lower trust", any("recall" in x.lower() for x in r["reasons"]))


# 5 — real PASS but false acceptance > 0 -> human review
def test_false_acceptance_caps() -> None:
    r = d(fa=0.5)
    check("real PASS + false acceptance -> HUMAN_REVIEW", r["status"] == sr.HUMAN_REVIEW, r["status"])


# 6 — invalid / unparseable structured judge output -> block
def test_invalid_or_unparseable_real() -> None:
    check("real schema INVALID -> BLOCK", d(real_schema="INVALID")["status"] == sr.BLOCK)
    check("real verdict UNPARSEABLE -> BLOCK", d(real_verdict="UNPARSEABLE")["status"] == sr.BLOCK)
    check("no real record -> BLOCK", sr.decide_source_review(summary("T", with_real=False), "T")["status"] == sr.BLOCK)


# 7 — output includes reasons
def test_reasons_present() -> None:
    for kw in [{}, {"real_verdict": "WARN"}, {"real_verdict": "FAIL"}, {"recall": 0.5}]:
        r = d(**kw)
        check(f"reasons non-empty for {kw or 'pass'}", isinstance(r["reasons"], list) and len(r["reasons"]) >= 1)


# 8 — judge decision never claims theorem truth
def test_no_theorem_truth_claim() -> None:
    r = d()
    check("note says source-fidelity, not theorem truth",
          "not theorem truth" in r["note"].lower())
    check("disclaimer present in reasons",
          any("not theorem truth" in x.lower() and "never edits lean" in x.lower() for x in r["reasons"]))
    check("never claims the theorem is true/proved",
          not any(("theorem is true" in x.lower() or "proves the theorem" in x.lower()) for x in r["reasons"]))


# 9 — this milestone touches no Lean / preserves the theorem-helper split
def test_no_lean_touched_and_split_preserved() -> None:
    src = (ROOT / "scripts" / "source_review_decision.py").read_text(encoding="utf-8")
    check("decision module writes no Lean", ".lean" not in src.replace("`AuditHarness/<Target>.lean`", "")
          .replace("AuditHarness/<Target>/Helpers.lean", "").replace("<Target>Helpers.lean", "")
          or "open(" not in src)  # it has no Lean writes; the only .lean mentions are docstring examples
    # the public-theorem / helper split files still exist for the current targets
    for f in ["AuditHarness/PutCallParity.lean", "AuditHarness/PutCallParity/Helpers.lean",
              "AuditHarness/TwoAssetMinVar.lean", "AuditHarness/TwoAssetMinVar/Helpers.lean",
              "AuditHarness/GoldIrrationalSqrtTwo.lean"]:
        check(f"theorem/helper split file present: {f}", (ROOT / f).is_file())
    # decide_source_review is pure: returns a dict and creates no file
    before = set(p.name for p in (ROOT / "scripts").glob("*"))
    _ = d()
    after = set(p.name for p in (ROOT / "scripts").glob("*"))
    check("decide writes no files (pure)", before == after)


# extras — ordering + concerns + consistency false alarm
def test_high_concerns_caps_even_on_pass() -> None:
    r = d(real_high=2)
    check("real PASS + high/critical concerns -> HUMAN_REVIEW", r["status"] == sr.HUMAN_REVIEW, r["status"])


def test_consistency_false_alarm_caps() -> None:
    r = d(fr=0.5)
    check("consistency false-alarm -> HUMAN_REVIEW", r["status"] == sr.HUMAN_REVIEW, r["status"])


def test_most_conservative_wins() -> None:
    # real FAIL with also-bad calibration -> still REVISE (not downgraded to HUMAN_REVIEW)
    r = d(real_verdict="FAIL", recall=0.5, fa=0.5)
    check("FAIL + bad calibration -> REVISE (conservative)", r["status"] == sr.REVISE, r["status"])
    # INVALID real beats everything -> BLOCK
    r2 = d(real_schema="INVALID", real_verdict="PASS", recall=1.0)
    check("INVALID real -> BLOCK regardless", r2["status"] == sr.BLOCK, r2["status"])


def main() -> int:
    tests = [
        test_pass, test_warn, test_fail, test_low_recall_caps, test_false_acceptance_caps,
        test_invalid_or_unparseable_real, test_reasons_present, test_no_theorem_truth_claim,
        test_no_lean_touched_and_split_preserved, test_high_concerns_caps_even_on_pass,
        test_consistency_false_alarm_caps, test_most_conservative_wins,
    ]
    for t in tests:
        print(t.__name__)
        t()
    print()
    if _failures:
        print(f"FAIL: {len(_failures)} assertion(s) failed: {_failures}")
        return 1
    print("PASS: all source-review-decision assertions passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
