#!/usr/bin/env python3
"""Offline unit tests for scripts/run_structured_judge_workflow.py (v0.3 milestone 2b).

Hermetic: synthetic results/manifest fixtures + temp output dirs; the real (committed, read-only)
docs/mutants/ supplies the scoring answer key. No Lean, no model, NO API key.

Run directly:  python scripts/test_structured_judge_workflow.py
Exit 0 if every assertion passes, 1 otherwise.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_structured_judge_workflow as wf  # noqa: E402
import validate_judge_schema as vjs  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
MUTANTS_DIR = ROOT / "docs" / "mutants"
MAPPING = ROOT / "docs" / "formal_mapping.yaml"
TARGET = "GoldIrrationalSqrtTwo"

# Synthetic blinded judge results + answer key. candidate_ids mirror the real _manifest so the
# real docs/mutants answer key resolves them (gold_irrational_sqrt_two -> real, GIST-* -> mutant).
RESULTS_YAML = """\
target: GoldIrrationalSqrtTwo
results:
  - blind_id: V-0001
    judge_verdict: PASS
    judge_output: {verdict: PASS, confidence: high, detected_issues: [], rationale: "Faithful."}
  - blind_id: V-0002
    judge_verdict: FAIL
    judge_output: {verdict: FAIL, confidence: high, detected_issues: [{axis: B_conclusion, severity: blocking, description: "Weakened."}], rationale: "Not faithful."}
"""
MANIFEST_YAML = """\
variants:
  V-0001: {target: GoldIrrationalSqrtTwo, variant_id: gold_irrational_sqrt_two, class: real}
  V-0002: {target: GoldIrrationalSqrtTwo, variant_id: GIST-D3, class: discriminative}
"""

_failures: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(f"  [{'ok  ' if cond else 'FAIL'}] {name}" + (f" -- {detail}" if (detail and not cond) else ""))
    if not cond:
        _failures.append(name)


def _fixture(tmp: Path) -> dict:
    (tmp / "results.yaml").write_text(RESULTS_YAML, encoding="utf-8")
    (tmp / "manifest.yaml").write_text(MANIFEST_YAML, encoding="utf-8")
    return dict(
        target=TARGET,
        results_path=tmp / "results.yaml",
        manifest_path=tmp / "manifest.yaml",
        mapping_path=MAPPING,
        source_ref="thm:gold_irrational_sqrt_two",
        mutants_dir=MUTANTS_DIR,
        out_dir=tmp / "out",
        promotion_dir=tmp / "prom",
        with_gate=False,
        plan_only=False,
        allow_missing=False,
        force=False,
        root=ROOT,
    )


def test_plan_only_writes_nothing() -> None:
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        opts = {**_fixture(tmp), "plan_only": True}
        s = wf.run_workflow(**opts)
        check("plan-only ok", s["ok"] is True, str(s))
        check("plan-only export planned", s["steps"]["export"]["status"] == "planned")
        wrote = list((tmp / "out").glob("*")) if (tmp / "out").exists() else []
        check("plan-only wrote no output files", wrote == [], str(wrote))


def test_export_and_score_succeed() -> None:
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        s = wf.run_workflow(**_fixture(tmp))
        check("workflow ok", s["ok"] is True, str(s))
        exp, sc = s["steps"]["export"], s["steps"]["score"]
        check("export 2 records, all valid", exp["records"] == 2 and exp["valid"] == 2 and exp["invalid"] == 0, str(exp))
        check("structured json written", Path(exp["path"]).exists())
        check("score json written", Path(sc["path"]).exists())
        check("score total 2", sc["total"] == 2, str(sc))
        check("score has schema_valid_rate", sc["schema_valid_rate"] == 1.0)
        check("score has discriminative_recall 1.0", sc["discriminative_recall"] == 1.0, str(sc))
        check("score has real_accept_rate 1.0", sc["real_accept_rate"] == 1.0)
        check("gate skipped without --with-gate", s["steps"]["gate"]["status"] == "skipped")


def test_exported_json_validates() -> None:
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        s = wf.run_workflow(**_fixture(tmp))
        doc = json.loads(Path(s["steps"]["export"]["path"]).read_text(encoding="utf-8"))
        check("export doc has results list", isinstance(doc.get("results"), list) and len(doc["results"]) == 2)
        statuses = [vjs.validate_text(json.dumps(r))["status"] for r in doc["results"]]
        check("every exported record validates VALID", all(x == vjs.VALID for x in statuses), str(statuses))


def test_with_gate_produces_decision() -> None:
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        opts = {**_fixture(tmp), "with_gate": True}
        s = wf.run_workflow(**opts)
        check("workflow ok with gate", s["ok"] is True, str(s))
        g = s["steps"]["gate"]
        check("gate produced a decision status",
              g["status"] in ("PROMOTE", "BLOCK", "REVISE", "HUMAN_REVIEW"), str(g))
        check("gate consumed judge metrics (PRESENT)", g["judge_metrics_status"] == "PRESENT", str(g))
        check("promotion file written to temp dir", Path(g["path"]).exists())
        check("promotion file is under the temp promotion dir", str(tmp) in g["path"])


def test_missing_results_fails_by_default() -> None:
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        opts = {**_fixture(tmp), "results_path": tmp / "does_not_exist.yaml"}
        s = wf.run_workflow(**opts)
        check("missing results -> not ok", s["ok"] is False, str(s))
        check("missing results -> clear error", "no judge results" in (s.get("error") or ""))


def test_missing_results_allow_missing_skips() -> None:
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        opts = {**_fixture(tmp), "results_path": tmp / "nope.yaml", "allow_missing": True}
        s = wf.run_workflow(**opts)
        check("allow-missing -> ok", s["ok"] is True, str(s))
        check("allow-missing -> export skipped",
              s["steps"]["export"]["status"] == "skipped_missing_results", str(s["steps"]))


def test_force_required_to_overwrite() -> None:
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        opts = _fixture(tmp)
        s1 = wf.run_workflow(**opts)
        check("first run ok", s1["ok"] is True)
        s2 = wf.run_workflow(**opts)  # outputs already exist, no --force
        check("second run without --force -> not ok", s2["ok"] is False, str(s2))
        s3 = wf.run_workflow(**{**opts, "force": True})
        check("second run with --force -> ok", s3["ok"] is True, str(s3))


def test_no_api_imports() -> None:
    check("workflow module has no 'openai'", not hasattr(wf, "openai"))
    src = (ROOT / "scripts" / "run_structured_judge_workflow.py").read_text(encoding="utf-8")
    check("no 'import openai' in source", "import openai" not in src and "from openai" not in src)
    check("no OPENAI_API_KEY reference", "OPENAI_API_KEY" not in src)
    check("no subprocess shelling", "subprocess" not in src)


def main() -> int:
    tests = [
        test_plan_only_writes_nothing,
        test_export_and_score_succeed,
        test_exported_json_validates,
        test_with_gate_produces_decision,
        test_missing_results_fails_by_default,
        test_missing_results_allow_missing_skips,
        test_force_required_to_overwrite,
        test_no_api_imports,
    ]
    for t in tests:
        print(t.__name__)
        t()
    print()
    if _failures:
        print(f"FAIL: {len(_failures)} assertion(s) failed: {_failures}")
        return 1
    print("PASS: all structured-judge-workflow assertions passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
