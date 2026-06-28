#!/usr/bin/env python3
"""Offline unit tests for the structured pipeline-status path:
  - rebuild_pipeline.py writes a `pipeline_status.v0.1` document (writer);
  - gate_decision.py --pipeline-status validates + fingerprint-checks it (verifier), failing
    closed (BLOCK) on staleness / target mismatch / bad schema / formal failure.

Pure: no Lean, no model/API; all generated files go to temp dirs. Run:
    python scripts/test_pipeline_status.py
"""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rebuild_pipeline as rp  # noqa: E402
import gate_decision as gd  # noqa: E402
import test_gate_decision as tg  # noqa: E402  (reuse the fully-promotable base_sig)

_failures: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(f"  [{'ok  ' if cond else 'FAIL'}] {name}" + (f" -- {detail}" if (detail and not cond) else ""))
    if not cond:
        _failures.append(name)


def _write_files(root: Path, files: dict) -> None:
    for rel, content in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")


def _fingerprints(root: Path, files: dict) -> dict:
    return {rel: "sha256:" + hashlib.sha256((root / rel).read_bytes()).hexdigest() for rel in files}


def _status(target="T", stages=None, fps=None) -> dict:
    st = stages or {"card_and_mapping": "PASS", "judge_packages": "PASS", "build": "PASS",
                    "no_sorry": "PASS", "axiom_audit": "PASS", "equivalence_check": "SKIPPED",
                    "comparator": "PASS"}
    return {
        "schema_version": gd.PIPELINE_STATUS_SCHEMA,
        "generated_utc": "2026-06-28T00:00:00Z",
        "target": target,
        "command": {"with_build": True, "with_axiom_audit": True, "with_equivalence_check": True,
                    "with_comparator": True, "writeback_comparator_status": False},
        "stages": {k: {"status": v, "message": "ok"} for k, v in st.items()},
        "overall_status": "FAIL" if "FAIL" in st.values() else "PASS",
        "input_fingerprints": fps or {},
    }


def _fresh_case(tmp: Path, target="T", stages=None, files=None):
    files = files or {"docs/formal_mapping.yaml": "mapping-a", "AuditHarness/T.lean": "thm-b"}
    _write_files(tmp, files)
    status = _status(target=target, stages=stages, fps=_fingerprints(tmp, files))
    sp = tmp / "pipeline_status.json"
    sp.write_text(json.dumps(status), encoding="utf-8")
    return sp, files


# ------------------------- writer (rebuild_pipeline) -------------------------
def test_writer_schema_and_stage_match() -> None:
    # Build a status doc against the real repo (read-only) for an existing target.
    stages = [rp.Stage("card_and_mapping").record(rp.PASS, "ok"),
              rp.Stage("judge_packages").record(rp.PASS, "ok"),
              rp.Stage("build").record(rp.SKIPPED, "gated"),
              rp.Stage("no_sorry").record(rp.PASS, "ok"),
              rp.Stage("axiom_audit").record(rp.PASS, "within permitted"),
              rp.Stage("equivalence_check").record(rp.SKIPPED, "gated"),
              rp.Stage("comparator").record(rp.PASS, "okay")]
    doc = rp.build_pipeline_status(stages, rp.PASS, "PutCallParity",
                                   {"with_build": False}, rp.load_targets(),
                                   generated_utc="2026-06-28T00:00:00Z")
    check("schema_version is pipeline_status.v0.1", doc["schema_version"] == "pipeline_status.v0.1")
    check("target recorded", doc["target"] == "PutCallParity")
    check("overall recorded", doc["overall_status"] == "PASS")
    check("stage statuses match inputs",
          doc["stages"]["axiom_audit"] == {"status": "PASS", "message": "within permitted"}
          and doc["stages"]["comparator"]["status"] == "PASS", str(doc["stages"]))
    fps = doc["input_fingerprints"]
    check("fingerprints include the ledgers",
          "docs/formal_mapping.yaml" in fps and "docs/theorem_index.yaml" in fps, str(list(fps)))
    check("fingerprints include the target theorem module + triple",
          "AuditHarness/PutCallParity.lean" in fps
          and "Audit/PutCallParity/Challenge.lean" in fps
          and "Audit/PutCallParity/comparator.json" in fps, str(list(fps)))
    check("fingerprint values are sha256:<64 hex>",
          all(v.startswith("sha256:") and len(v) == 71 for v in fps.values()))


def test_writer_helper_module_included_when_present() -> None:
    doc = rp.build_pipeline_status([], rp.PASS, "PutCallParity", {}, rp.load_targets(),
                                   generated_utc="t")
    # PutCallParity has a Helpers.lean; GoldIrrationalSqrtTwo does not.
    check("PutCallParity Helpers fingerprinted",
          "AuditHarness/PutCallParity/Helpers.lean" in doc["input_fingerprints"])
    gold = rp.build_pipeline_status([], rp.PASS, "GoldIrrationalSqrtTwo", {}, rp.load_targets(),
                                    generated_utc="t")
    check("Gold has no Helpers fingerprint (no helper file)",
          "AuditHarness/GoldIrrationalSqrtTwo/Helpers.lean" not in gold["input_fingerprints"])


# ------------------------- verifier (gate_decision) -------------------------
def test_fresh_status_accepted() -> None:
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        sp, _ = _fresh_case(tmp)
        formal, err = gd.read_structured_status(str(sp), "T", tmp)
        check("fresh status: no error", err is None, str(err))
        check("fresh status: build PASS surfaced", formal.get("build") == "PASS", str(formal))
        check("fresh status: comparator PASS surfaced", formal.get("comparator") == "PASS")
        check("fresh status: SKIPPED surfaced", formal.get("equivalence_check") == "SKIPPED")


def test_stale_fingerprint_blocks() -> None:
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        sp, files = _fresh_case(tmp)
        (tmp / "AuditHarness/T.lean").write_text("TAMPERED", encoding="utf-8")  # change a fingerprinted input
        formal, err = gd.read_structured_status(str(sp), "T", tmp)
        check("stale fingerprint: error returned", err is not None and "stale" in err.lower(), str(err))
        check("stale fingerprint: no formal stages trusted", formal == {})


def test_target_mismatch_blocks() -> None:
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        sp, _ = _fresh_case(tmp, target="T")
        formal, err = gd.read_structured_status(str(sp), "OTHER", tmp)
        check("target mismatch: error", err is not None and "target" in err.lower(), str(err))


def test_bad_schema_blocks() -> None:
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        sp, _ = _fresh_case(tmp)
        doc = json.loads(sp.read_text(encoding="utf-8"))
        doc["schema_version"] = "pipeline_status.v9.9"
        sp.write_text(json.dumps(doc), encoding="utf-8")
        _, err = gd.read_structured_status(str(sp), "T", tmp)
        check("bad schema: error", err is not None and "schema_version" in err, str(err))


def test_missing_required_stage_blocks() -> None:
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        stages = {"build": "PASS", "no_sorry": "PASS", "axiom_audit": "PASS",
                  "equivalence_check": "SKIPPED"}  # comparator missing
        sp, _ = _fresh_case(tmp, stages=stages)
        _, err = gd.read_structured_status(str(sp), "T", tmp)
        check("missing stage: error names comparator", err is not None and "comparator" in err, str(err))


def test_missing_file_blocks() -> None:
    with tempfile.TemporaryDirectory() as t:
        _, err = gd.read_structured_status(str(Path(t) / "nope.json"), "T", Path(t))
        check("missing file: error (fail closed)", err is not None and "not found" in err.lower(), str(err))


def test_formal_failure_surfaced_then_blocks() -> None:
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        stages = {"card_and_mapping": "PASS", "judge_packages": "PASS", "build": "FAIL",
                  "no_sorry": "PASS", "axiom_audit": "PASS", "equivalence_check": "SKIPPED",
                  "comparator": "PASS"}
        sp, _ = _fresh_case(tmp, stages=stages)
        formal, err = gd.read_structured_status(str(sp), "T", tmp)
        check("valid-but-failing status parses (no integrity error)", err is None, str(err))
        check("build FAIL surfaced", formal.get("build") == "FAIL")
        d = gd.decide({**tg.base_sig(), "build_status": "FAIL"})
        check("decide blocks on build FAIL from structured status", d["status"] == gd.BLOCK, d["status"])


# ------------------------- decide() integration -------------------------
def test_decide_structured_error_blocks() -> None:
    d = gd.decide({**tg.base_sig(), "structured_status_error": "stale; fingerprint mismatch for [x]"})
    check("structured_status_error -> BLOCK", d["status"] == gd.BLOCK, d["status"])
    check("reason cites the integrity failure",
          any("integrity" in r.lower() or "pipeline status" in r.lower() for r in d["reasons"]))


def test_judge_metrics_cannot_upgrade_structured_block() -> None:
    perfect = {"totals": {"schema_valid_rate": 1.0, "invalid_rate": 0.0, "unparseable_rate": 0.0},
               "reliability": {"discriminative_recall": 1.0,
                               "false_acceptance_rate_discriminative": 0.0,
                               "false_rejection_rate_consistency": 0.0},
               "high_critical_concern_count": 0}
    d = gd.decide({**tg.base_sig(), "structured_status_error": "stale",
                   "judge_metrics_status": gd.JM_PRESENT, "judge_metrics": perfect})
    check("judge metrics cannot rescue a structured BLOCK", d["status"] == gd.BLOCK, d["status"])


def test_markdown_fallback_unchanged_without_flag() -> None:
    # No --pipeline-status: gather must not set a structured_status_error (backward compatible).
    with tempfile.TemporaryDirectory() as t:
        g = gd.gather("PutCallParity", root=Path(t))  # empty root: artifacts absent, but no crash
        check("default gather: structured_status_error is None",
              g["sig"]["structured_status_error"] is None, str(g["sig"].get("structured_status_error")))


def test_read_formal_status_handles_nested_json() -> None:
    # The auto-read fallback must tolerate the nested pipeline_status.v0.1 shape too.
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        (tmp / "docs").mkdir()
        (tmp / "docs" / "pipeline_status.json").write_text(
            json.dumps({"stages": {"build": {"status": "PASS"}, "comparator": {"status": "FAIL"}}}),
            encoding="utf-8")
        out = gd.read_formal_status(tmp)
        check("nested auto-read: build PASS", out.get("build") == "PASS", str(out))
        check("nested auto-read: comparator FAIL", out.get("comparator") == "FAIL")


def main() -> int:
    tests = [
        test_writer_schema_and_stage_match,
        test_writer_helper_module_included_when_present,
        test_fresh_status_accepted,
        test_stale_fingerprint_blocks,
        test_target_mismatch_blocks,
        test_bad_schema_blocks,
        test_missing_required_stage_blocks,
        test_missing_file_blocks,
        test_formal_failure_surfaced_then_blocks,
        test_decide_structured_error_blocks,
        test_judge_metrics_cannot_upgrade_structured_block,
        test_markdown_fallback_unchanged_without_flag,
        test_read_formal_status_handles_nested_json,
    ]
    for t in tests:
        print(t.__name__)
        t()
    print()
    if _failures:
        print(f"FAIL: {len(_failures)} assertion(s) failed: {_failures}")
        return 1
    print("PASS: all pipeline-status assertions passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
