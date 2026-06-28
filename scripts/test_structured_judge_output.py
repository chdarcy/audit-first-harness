#!/usr/bin/env python3
"""Offline unit tests for scripts/export_structured_judge_results.py (v0.3 milestone 2a).

Pure functions + a synthetic in-memory fixture (no Lean, no model, NO API key). Confirms the
exported records validate with validate_judge_schema.py and score with score_judge.py --structured.

Run directly:  python scripts/test_structured_judge_output.py
Exit 0 if every assertion passes, 1 otherwise.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import export_structured_judge_results as ex  # noqa: E402
import validate_judge_schema as vjs  # noqa: E402
import score_judge as sj  # noqa: E402

TARGET = "GoldIrrationalSqrtTwo"
SOURCE_REF = "thm:gold_irrational_sqrt_two"

# A synthetic blinded results document (the shape import_manual_judge_results / run_judge write).
RESULTS_DOC = {
    "target": TARGET,
    "results": [
        {"blind_id": "V-0001", "judge_verdict": "PASS",
         "judge_output": {"verdict": "PASS", "confidence": "high", "detected_issues": [],
                          "rationale": "Faithful."}},
        {"blind_id": "V-0002", "judge_verdict": "FAIL",
         "judge_output": {"verdict": "FAIL", "confidence": "high",
                          "detected_issues": [{"axis": "B_conclusion", "severity": "blocking",
                                               "description": "Weakened to an inequality."}],
                          "rationale": "Not faithful."}},
        {"blind_id": "V-0003", "judge_verdict": "OUT_OF_SCOPE",
         "judge_output": {"verdict": "OUT_OF_SCOPE", "confidence": "low",
                          "detected_issues": [], "rationale": "Different theorem."}},
        {"blind_id": "V-0004", "judge_verdict": "PASS", "recovered_verdict": True,
         "judge_output": None, "parse_error": "unquoted colon"},
        {"blind_id": "V-0005", "judge_verdict": None,
         "judge_output": None, "parse_error": "no verdict"},
    ],
}

# Synthetic answer key (un-blinding map). variant_id mirrors the real _manifest shape.
MANIFEST = {
    "variants": {
        "V-0001": {"target": TARGET, "variant_id": "gold_irrational_sqrt_two", "class": "real"},
        "V-0002": {"target": TARGET, "variant_id": "GIST-D3", "class": "discriminative"},
        "V-0003": {"target": TARGET, "variant_id": "GIST-D2", "class": "discriminative"},
        "V-0004": {"target": TARGET, "variant_id": "GIST-C1", "class": "consistency"},
        "V-0005": {"target": TARGET, "variant_id": "GIST-D4", "class": "discriminative"},
    }
}

_failures: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(f"  [{'ok  ' if cond else 'FAIL'}] {name}" + (f" -- {detail}" if (detail and not cond) else ""))
    if not cond:
        _failures.append(name)


def convert():
    recs, errs = ex.convert_results(RESULTS_DOC, MANIFEST, SOURCE_REF, TARGET)
    return {r["candidate_id"]: r for r in recs}, errs


def test_clean_pass_record() -> None:
    by_id, errs = convert()
    check("no un-blinding errors", errs == [], str(errs))
    r = by_id["gold_irrational_sqrt_two"]
    check("real PASS -> verdict PASS", r["verdict"] == "PASS", str(r))
    check("real PASS -> candidate_id un-blinded", r["candidate_id"] == "gold_irrational_sqrt_two")
    check("real PASS -> confidence 0.9 (high)", r["confidence"] == 0.9, str(r["confidence"]))
    check("real PASS -> no human review", r["requires_human_review"] is False)
    check("real PASS validates VALID", vjs.classify_record(r)["status"] == vjs.VALID, str(r))


def test_fail_with_concern() -> None:
    r = convert()[0]["GIST-D3"]
    check("discriminative FAIL -> verdict FAIL", r["verdict"] == "FAIL")
    check("FAIL -> one concern", len(r["concerns"]) == 1, str(r["concerns"]))
    check("axis B_conclusion -> conclusion_mismatch", r["concerns"][0]["type"] == "conclusion_mismatch")
    check("severity blocking -> high", r["concerns"][0]["severity"] == "high")
    check("FAIL -> requires_human_review", r["requires_human_review"] is True)
    check("FAIL validates VALID", vjs.classify_record(r)["status"] == vjs.VALID, str(r))


def test_out_of_scope_becomes_unparseable() -> None:
    r = convert()[0]["GIST-D2"]
    check("OUT_OF_SCOPE -> UNPARSEABLE", r["verdict"] == "UNPARSEABLE", str(r))
    check("UNPARSEABLE -> confidence 0.0", r["confidence"] == 0.0)
    check("UNPARSEABLE -> requires_human_review", r["requires_human_review"] is True)
    check("UNPARSEABLE record still schema-VALID", vjs.classify_record(r)["status"] == vjs.VALID, str(r))


def test_recovered_verdict_flags_review() -> None:
    r = convert()[0]["GIST-C1"]
    check("recovered PASS -> verdict PASS", r["verdict"] == "PASS")
    check("recovered -> confidence 0.3", r["confidence"] == 0.3, str(r["confidence"]))
    check("recovered -> requires_human_review", r["requires_human_review"] is True)
    check("recovered validates VALID", vjs.classify_record(r)["status"] == vjs.VALID)


def test_unrecoverable_becomes_unparseable() -> None:
    r = convert()[0]["GIST-D4"]
    check("None verdict -> UNPARSEABLE", r["verdict"] == "UNPARSEABLE", str(r))
    check("UNPARSEABLE summary mentions human review", "human review" in r["summary"].lower())


def test_all_records_validate() -> None:
    recs, _ = ex.convert_results(RESULTS_DOC, MANIFEST, SOURCE_REF, TARGET)
    statuses = [vjs.classify_record(r)["status"] for r in recs]
    check("all 5 records produced", len(recs) == 5, str(len(recs)))
    check("every record schema-VALID", all(s == vjs.VALID for s in statuses), str(statuses))


def test_results_json_roundtrip_validates() -> None:
    # Emit one {"results": [...]} JSON file and re-validate each record through the CLI validator.
    recs, _ = ex.convert_results(RESULTS_DOC, MANIFEST, SOURCE_REF, TARGET)
    doc = {"schema_version": ex.SCHEMA_VERSION, "target": TARGET, "results": recs}
    text = json.dumps(doc)
    reloaded = json.loads(text)["results"]
    check("JSON round-trips all records", len(reloaded) == 5)
    check("each round-tripped record validates via validate_text",
          all(vjs.validate_text(json.dumps(r))["status"] == vjs.VALID for r in reloaded))


def test_scoreable_by_score_judge_structured() -> None:
    recs, _ = ex.convert_results(RESULTS_DOC, MANIFEST, SOURCE_REF, TARGET)
    # Answer key keyed by candidate_id (matches score_judge's structured answer-key shape).
    answer_key = {TARGET: {"gold_irrational_sqrt_two": "real", "GIST-D3": "discriminative",
                           "GIST-D2": "discriminative", "GIST-C1": "consistency",
                           "GIST-D4": "discriminative"}}
    summary = sj.score_structured_records(recs, answer_key)
    check("score_judge consumes exported records: total 5", summary["totals"]["total"] == 5)
    # GIST-D3 FAIL (reject) is the only *usable* discriminative; GIST-D2/D4 are UNPARSEABLE.
    check("discriminative_recall 1.0 over usable", summary["reliability"]["discriminative_recall"] == 1.0,
          str(summary["reliability"]))
    check("real accepted", summary["reliability"]["real_accept_rate"] == 1.0)
    check("two unparseable counted", summary["totals"]["unparseable"] == 2, str(summary["totals"]))


def test_split_dir_one_file_per_candidate() -> None:
    recs, _ = ex.convert_results(RESULTS_DOC, MANIFEST, SOURCE_REF, TARGET)
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        for r in recs:
            (d / f"{r['candidate_id']}.json").write_text(json.dumps(r), encoding="utf-8")
        files = sorted(p.name for p in d.glob("*.json"))
        check("one file per candidate", len(files) == 5, str(files))
        check("a known candidate file exists", "GIST-D3.json" in files)


def test_unknown_blind_id_reported_not_guessed() -> None:
    doc = {"results": [{"blind_id": "V-9999", "judge_verdict": "PASS", "judge_output": {}}]}
    recs, errs = ex.convert_results(doc, MANIFEST, SOURCE_REF, TARGET)
    check("unknown blind_id -> no record", recs == [], str(recs))
    check("unknown blind_id -> error reported", len(errs) == 1 and "un-blind" in errs[0])


def test_no_api_import() -> None:
    # The module must not import openai or require a key at import time.
    check("export module has no 'openai' attribute", not hasattr(ex, "openai"))
    check("export module has no _call_openai", not hasattr(ex, "_call_openai"))


def main() -> int:
    tests = [
        test_clean_pass_record,
        test_fail_with_concern,
        test_out_of_scope_becomes_unparseable,
        test_recovered_verdict_flags_review,
        test_unrecoverable_becomes_unparseable,
        test_all_records_validate,
        test_results_json_roundtrip_validates,
        test_scoreable_by_score_judge_structured,
        test_split_dir_one_file_per_candidate,
        test_unknown_blind_id_reported_not_guessed,
        test_no_api_import,
    ]
    for t in tests:
        print(t.__name__)
        t()
    print()
    if _failures:
        print(f"FAIL: {len(_failures)} assertion(s) failed: {_failures}")
        return 1
    print("PASS: all structured-judge-output assertions passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
