#!/usr/bin/env python3
"""Run the audit-first pipeline end to end and write docs/pipeline_report.md.

Stages, in order:

  1. card_and_mapping   — validate_mapping.py: theorem cards <-> mapping <-> reviews consistent
  2. judge_packages     — run_mutants.py --dry-run: assemble blinded judge packages (no model)
  3. build              — lake build the library (proof/build stage)        [human-gated]
  4. no_sorry           — check_sorries.py: no incomplete proofs in the library
  5. comparator         — Lean FRO Comparator per target (statement + kernel audit) [human-gated]
  6. report             — write docs/pipeline_report.md

This is an MVP harness (v0.1, experimental). It does NOT translate LaTeX to Lean and does NOT
guarantee autonomous proof generation: the proofs it builds and audits are authored by a
human/model agent and only *checked* here by Lean and (optionally) the Comparator.

The two heavy/environment-specific stages — `build` and `comparator` — are **human-gated**:
they run only when you pass --with-build / --with-comparator. Otherwise they are recorded as
SKIPPED (gated) so the fast default still produces a full report.

The judge model itself is never called here; that is the separate, opt-in
`scripts/run_judge.py --execute-api` step.

Exit code 0 if no executed stage failed, 1 otherwise. SKIPPED stages never fail the run.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
except ModuleNotFoundError:
    sys.stderr.write(
        "ERROR: PyYAML is required. Install it with: python -m pip install pyyaml\n"
    )
    sys.exit(2)

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
FORMAL_MAPPING = ROOT / "docs" / "formal_mapping.yaml"
REPORT = ROOT / "docs" / "pipeline_report.md"

PASS, FAIL, SKIPPED = "PASS", "FAIL", "SKIPPED"


class Stage:
    def __init__(self, name: str):
        self.name = name
        self.status = SKIPPED
        self.detail = ""
        self.cmd = ""

    def record(self, status: str, detail: str = "", cmd: str = "") -> "Stage":
        self.status, self.detail, self.cmd = status, detail, cmd
        return self


def run_cmd(cmd: list[str], cwd: Path = ROOT) -> tuple[int, str]:
    """Run a subprocess, returning (returncode, combined_output)."""
    proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)
    out = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode, out.strip()


def py(*script_args: str) -> list[str]:
    return [sys.executable, str(SCRIPTS / script_args[0]), *script_args[1:]]


def last_line(text: str) -> str:
    lines = [ln for ln in text.splitlines() if ln.strip()]
    return lines[-1] if lines else ""


def load_targets() -> dict:
    doc = yaml.safe_load(FORMAL_MAPPING.read_text(encoding="utf-8")) or {}
    return doc.get("targets") or {}


# ---------------------------------------------------------------------------
# Stages
# ---------------------------------------------------------------------------
def stage_card_and_mapping() -> Stage:
    s = Stage("card_and_mapping")
    cmd = py("validate_mapping.py")
    rc, out = run_cmd(cmd)
    return s.record(PASS if rc == 0 else FAIL, last_line(out), " ".join(cmd))


def stage_judge_packages() -> Stage:
    s = Stage("judge_packages")
    cmd = py("run_mutants.py", "--dry-run")
    rc, out = run_cmd(cmd)
    return s.record(PASS if rc == 0 else FAIL, last_line(out), " ".join(cmd))


def stage_build(with_build: bool) -> Stage:
    s = Stage("build")
    if not with_build:
        return s.record(SKIPPED, "gated: pass --with-build to run `lake build`")
    cmd = ["lake", "build"]
    rc, out = run_cmd(cmd)
    return s.record(PASS if rc == 0 else FAIL, last_line(out) or f"lake build exit {rc}", " ".join(cmd))


def stage_no_sorry() -> Stage:
    s = Stage("no_sorry")
    cmd = py("check_sorries.py")
    rc, out = run_cmd(cmd)
    return s.record(PASS if rc == 0 else FAIL, last_line(out), " ".join(cmd))


def comparator_env() -> dict | None:
    """Return the Comparator env config if all three pieces are present, else None."""
    binp = os.environ.get("COMPARATOR_BIN") or os.environ.get("COMPARATOR")
    landrun = os.environ.get("COMPARATOR_LANDRUN")
    export = os.environ.get("COMPARATOR_LEAN4EXPORT")
    if binp and landrun and export:
        return {"bin": binp, "landrun": landrun, "export": export}
    return None


def stage_comparator(with_comparator: bool) -> Stage:
    s = Stage("comparator")
    targets = load_targets()
    # The configs must always exist (cheap structural precondition), gated or not.
    config_status = []
    for name, t in targets.items():
        cfg = (t.get("comparator") or {}).get("config")
        ok = bool(cfg) and (ROOT / cfg).exists()
        config_status.append((name, cfg, ok))
    missing = [name for name, _cfg, ok in config_status if not ok]
    if missing:
        return s.record(FAIL, f"missing comparator.json for: {missing}")

    if not with_comparator:
        return s.record(
            SKIPPED,
            f"gated: configs present for {len(config_status)} target(s); pass --with-comparator "
            f"to run. Requires Linux + COMPARATOR_BIN/COMPARATOR_LANDRUN/COMPARATOR_LEAN4EXPORT.",
        )

    if platform.system() != "Linux":
        return s.record(
            SKIPPED,
            "SKIPPED_COMPARATOR_TOOL_UNAVAILABLE: the Comparator sandbox runs on Linux only "
            f"(current platform: {platform.system()}). Run under WSL/Linux.",
        )
    env = comparator_env()
    if not env:
        return s.record(
            SKIPPED,
            "SKIPPED_COMPARATOR_TOOL_UNAVAILABLE: set COMPARATOR_BIN, COMPARATOR_LANDRUN, and "
            "COMPARATOR_LEAN4EXPORT to the built binaries (see README / docs/COMPARATOR.md).",
        )

    runenv = dict(os.environ)
    runenv["COMPARATOR_LANDRUN"] = env["landrun"]
    runenv["COMPARATOR_LEAN4EXPORT"] = env["export"]
    results = []
    all_ok = True
    for name, cfg, _ok in config_status:
        cmd = ["lake", "env", env["bin"], cfg]
        proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, env=runenv)
        out = (proc.stdout or "") + (proc.stderr or "")
        ok = proc.returncode == 0 and "Your solution is okay!" in out
        all_ok = all_ok and ok
        results.append(f"{name}: {'okay' if ok else 'FAILED'}")
    return s.record(PASS if all_ok else FAIL, "; ".join(results), f"lake env {env['bin']} <config>")


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
def write_report(stages: list[Stage], now: str, overall: str) -> None:
    icon = {PASS: "✅", FAIL: "❌", SKIPPED: "⏭️"}
    lines = [
        "# Pipeline report",
        "",
        "_Generated by `scripts/rebuild_pipeline.py`._",
        "",
        f"**Overall: {overall}** — generated {now}",
        "",
        "Stage order: source/card → mapping → judge package → proof/build → no-sorry → "
        "comparator → report. `build` and `comparator` are human-gated (run with "
        "`--with-build` / `--with-comparator`).",
        "",
        "| # | stage | status | detail |",
        "|---|---|---|---|",
    ]
    for i, s in enumerate(stages, start=1):
        detail = s.detail.replace("|", "\\|")
        lines.append(f"| {i} | `{s.name}` | {icon.get(s.status, '')} {s.status} | {detail} |")
    lines += [
        "",
        "> The judge model is never called by this script. Real LLM judging is the separate, "
        "opt-in `scripts/run_judge.py --execute-api` step, scored offline by "
        "`scripts/score_judge.py`.",
        "",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--with-build", action="store_true",
                    help="run the `lake build` proof/build stage (may be slow)")
    ap.add_argument("--with-comparator", action="store_true",
                    help="run the Comparator stage (Linux + built binaries required)")
    args = ap.parse_args()

    stages = [
        stage_card_and_mapping(),
        stage_judge_packages(),
        stage_build(args.with_build),
        stage_no_sorry(),
        stage_comparator(args.with_comparator),
    ]

    failed = [s for s in stages if s.status == FAIL]
    overall = FAIL if failed else PASS
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    write_report(stages, now, overall)

    print(f"PIPELINE {overall} — report: {REPORT.relative_to(ROOT)}")
    for s in stages:
        print(f"  [{s.status:>7}] {s.name}: {s.detail}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
