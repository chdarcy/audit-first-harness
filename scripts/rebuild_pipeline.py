#!/usr/bin/env python3
"""Run the audit-first pipeline end to end and write docs/pipeline_report.md.

Stages, in order:

  1. card_and_mapping   — validate_mapping.py: theorem cards <-> mapping <-> reviews consistent
  2. judge_packages     — run_mutants.py --dry-run: assemble blinded judge packages (no model)
  3. build              — lake build the library (proof/build stage)        [human-gated]
  4. no_sorry           — check_sorries.py: no incomplete proofs in the library
  5. axiom_audit        — check_axioms.py: mapped declarations within permitted axioms [human-gated]
  6. equivalence_check  — check_equivalence.py: PASS_PROVABLE_EQUIV lemmas build & are clean [human-gated]
  7. comparator         — Lean FRO Comparator per target (statement + kernel audit) [human-gated]
  8. report             — write docs/pipeline_report.md

This is an MVP harness (v0.1, experimental). It does NOT translate LaTeX to Lean and does NOT
guarantee autonomous proof generation: the proofs it builds and audits are authored by a
human/model agent and only *checked* here by Lean and (optionally) the Comparator.

The two heavy/environment-specific stages — `build` and `comparator` — are **human-gated**:
they run only when you pass --with-build / --with-comparator. Otherwise they are recorded as
SKIPPED (gated) so the fast default still produces a full report.

Pass `--target <T>` to scope the per-target `comparator`, `axiom_audit`, and `equivalence_check`
stages to a single mapping target. `build` and `no_sorry` remain whole-library, and judge-package
assembly stays repo-wide (per-target judging is done downstream by `run_judge`/`score_judge --target`).

With `--with-comparator --writeback-comparator-status` (and `--target`), the resulting Comparator
status is written back to that target's `comparator_status` in docs/formal_mapping.yaml via a
text-level edit that preserves comments (opt-in; off by default).

The judge model itself is never called here; that is the separate, opt-in
`scripts/run_judge.py --execute-api` step.

Exit code 0 if no executed stage failed, 1 otherwise. SKIPPED stages never fail the run.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import re
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


def resolve_target(arg_target: str | None, available: dict) -> tuple[str | None, str | None]:
    """Return (target_or_None, error_or_None). None target means 'all targets' (default)."""
    if arg_target is None:
        return None, None
    if arg_target in available:
        return arg_target, None
    return None, (f"target {arg_target!r} is not in formal_mapping.yaml; "
                  f"available targets: {sorted(available)}")


def select_targets(available: dict, target: str | None) -> dict:
    """All targets when target is None, else just the selected one (assumed validated)."""
    return available if target is None else {target: available[target]}


# ---------------------------------------------------------------------------
# Comparator-status writeback (opt-in; see ARCHITECTURE.md §13.4)
# ---------------------------------------------------------------------------
def writeback_precondition_error(writeback: bool, target: str | None,
                                 with_comparator: bool) -> str | None:
    """Return an error string if --writeback-comparator-status is misused, else None."""
    if not writeback:
        return None
    if target is None:
        return "--writeback-comparator-status requires --target (writeback is target-specific)."
    if not with_comparator:
        return ("--writeback-comparator-status requires --with-comparator "
                "(nothing to write back without a Comparator run).")
    return None


def derive_comparator_status(stage_status: str, *, landrun_path: str | None = None,
                             abi: int | None = None) -> tuple[str | None, str]:
    """Map a Comparator stage outcome to an honest comparator_status value + a reason.

    `status` is None when the stage has no terminal result (nothing should be written). Because
    the Comparator always runs landrun with --best-effort and leaves no reliable post-hoc signal
    of whether the sandbox degraded, a PASS is recorded **conservatively** as
    PASSED_REAL_LANDRUN_BEST_EFFORT unless the operator supplies the Landlock ABI via `abi`
    (COMPARATOR_LANDRUN_ABI): ABI >= 5 -> PASSED_REAL_LANDRUN; ABI < 5 -> _BEST_EFFORT."""
    if stage_status == SKIPPED:
        return ("SKIPPED_COMPARATOR_TOOL_UNAVAILABLE",
                "Comparator stage was skipped (tool/platform unavailable).")
    if stage_status == FAIL:
        return ("FAILED_COMPARATOR", "Comparator stage failed.")
    if stage_status == PASS:
        if landrun_path and "fake" in Path(landrun_path).name.lower():
            return ("PASSED_FAKE_LANDRUN",
                    "Comparator passed but COMPARATOR_LANDRUN is a fake/unsandboxed shim; "
                    "not a high-confidence pass.")
        if abi is not None and abi < 5:
            return ("PASSED_REAL_LANDRUN_BEST_EFFORT",
                    f"Comparator passed; Landlock ABI {abi} (<5) means a best-effort/degraded "
                    "sandbox.")
        if abi is not None:
            return ("PASSED_REAL_LANDRUN",
                    f"Comparator passed with a real landrun sandbox (Landlock ABI {abi}).")
        return ("PASSED_REAL_LANDRUN_BEST_EFFORT",
                "Comparator passed using real landrun, but COMPARATOR_LANDRUN_ABI was not "
                "supplied; since landrun is invoked with --best-effort, status is conservatively "
                "recorded as PASSED_REAL_LANDRUN_BEST_EFFORT.")
    return (None, f"Comparator stage status {stage_status!r} is not terminal; nothing written.")


def set_comparator_status_text(text: str, target: str, new_status: str) -> tuple[str, str]:
    """Text-level update of one target's `comparator_status:` value. Preserves every other line,
    comment, and the file's formatting (no YAML round-trip). Returns (new_text, old_status);
    raises ValueError if the target or its comparator_status line is not found."""
    lines = text.splitlines(keepends=True)
    target_re = re.compile(rf"^(\s+){re.escape(target)}:\s*$")
    field_re = re.compile(r"^(\s*)comparator_status:[ \t]*(\S+)(.*)$")
    ti = target_indent = None
    for i, line in enumerate(lines):
        m = target_re.match(line)
        if m:
            ti, target_indent = i, len(m.group(1))
            break
    if ti is None:
        raise ValueError(f"target {target!r} not found in formal_mapping.yaml")
    for j in range(ti + 1, len(lines)):
        stripped = lines[j].strip()
        if stripped and not stripped.startswith("#"):
            indent = len(lines[j]) - len(lines[j].lstrip())
            if indent <= target_indent:
                break  # left the target's block before finding the field
        fm = field_re.match(lines[j])
        if fm:
            old = fm.group(2)
            newline = "\n" if lines[j].endswith("\n") else ""
            trailing = fm.group(3).rstrip("\n")  # keep any inline comment, drop the line break
            lines[j] = f"{fm.group(1)}comparator_status: {new_status}{trailing}{newline}"
            return "".join(lines), old
    raise ValueError(f"comparator_status not found in target {target!r} block")


def write_comparator_status(target: str, new_status: str) -> str:
    """Apply set_comparator_status_text to docs/formal_mapping.yaml in place; return old status."""
    text = FORMAL_MAPPING.read_text(encoding="utf-8")
    new_text, old = set_comparator_status_text(text, target, new_status)
    FORMAL_MAPPING.write_text(new_text, encoding="utf-8")
    return old


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


def stage_axiom_audit(with_axiom_audit: bool, target: str | None = None) -> Stage:
    s = Stage("axiom_audit")
    if not with_axiom_audit:
        return s.record(SKIPPED, "gated: pass --with-axiom-audit to run `check_axioms.py` "
                        "(needs Lean/Lake + built oleans)")
    cmd = py("check_axioms.py", *(["--target", target] if target else []))
    rc, out = run_cmd(cmd)
    return s.record(PASS if rc == 0 else FAIL, last_line(out), " ".join(cmd))


def stage_equivalence_check(with_equivalence_check: bool, target: str | None = None) -> Stage:
    s = Stage("equivalence_check")
    if not with_equivalence_check:
        return s.record(SKIPPED, "gated: pass --with-equivalence-check to run "
                        "`check_equivalence.py` (verifies PASS_PROVABLE_EQUIV lemmas; needs Lean)")
    cmd = py("check_equivalence.py", *(["--target", target] if target else []))
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


def stage_comparator(with_comparator: bool, target: str | None = None) -> Stage:
    s = Stage("comparator")
    targets = select_targets(load_targets(), target)
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
def render_report(stages: list[Stage], now: str, overall: str, target: str | None,
                  writeback: dict | None = None) -> str:
    icon = {PASS: "✅", FAIL: "❌", SKIPPED: "⏭️"}
    scope = "ALL targets" if target is None else f"`{target}` (target-scoped run)"
    if writeback is None:
        wb_line = "not requested"
    elif writeback.get("performed"):
        wb_line = (f"`{writeback['target']}`.comparator_status: "
                   f"{writeback['old']} → {writeback['new']} — {writeback['reason']}")
    else:
        wb_line = f"requested but not applied — {writeback['reason']}"
    lines = [
        "# Pipeline report",
        "",
        "_Generated by `scripts/rebuild_pipeline.py`._",
        "",
        f"**Overall: {overall}** — generated {now}",
        f"**Target scope:** {scope}",
        f"**Comparator-status writeback:** {wb_line}",
        "",
        "Stage order: source/card → mapping → judge package → proof/build → no-sorry → "
        "axiom-audit → equivalence-check → comparator → report. `build`, `axiom_audit`, "
        "`equivalence_check`, and `comparator` are human-gated (run with `--with-build` / "
        "`--with-axiom-audit` / `--with-equivalence-check` / `--with-comparator`).",
        "",
        "| # | stage | status | detail |",
        "|---|---|---|---|",
    ]
    for i, s in enumerate(stages, start=1):
        detail = s.detail.replace("|", "\\|")
        lines.append(f"| {i} | `{s.name}` | {icon.get(s.status, '')} {s.status} | {detail} |")

    cmds = [f"- `{s.cmd}`" for s in stages if s.cmd]
    lines += ["", "**Commands run:**", ""] + (cmds or ["- (none)"])
    lines += [
        "",
        "**Scope notes (v0.2):**",
        "",
        "- `build` (`lake build`) and `no_sorry` (`check_sorries.py`) are currently "
        "**whole-library**, even for a target-scoped run; per-target build/no-sorry is not yet "
        "implemented.",
        "- `card_and_mapping` (`validate_mapping.py`) and `judge_packages` "
        "(`run_mutants.py --dry-run`) operate over the **whole repo / all targets**; per-target "
        "judging is done downstream by `run_judge` / `score_judge --target`.",
        "- Only the `comparator`, `axiom_audit`, and `equivalence_check` stages are target-scoped "
        "when `--target` is given.",
        "- Promotion decisions are produced separately by "
        "`python scripts/gate_decision.py --target <Target>`.",
        "",
        "> The judge model is never called by this script. Real LLM judging is the separate, "
        "opt-in `scripts/run_judge.py --execute-api` step, scored offline by "
        "`scripts/score_judge.py`.",
        "",
    ]
    return "\n".join(lines)


def write_report(stages: list[Stage], now: str, overall: str, target: str | None,
                 writeback: dict | None = None) -> None:
    REPORT.write_text(render_report(stages, now, overall, target, writeback), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--target", default=None,
                    help="restrict the per-target comparator stage to one mapping target "
                         "(default: all targets). build/no-sorry stay whole-library.")
    ap.add_argument("--with-build", action="store_true",
                    help="run the `lake build` proof/build stage (may be slow)")
    ap.add_argument("--with-comparator", action="store_true",
                    help="run the Comparator stage (Linux + built binaries required)")
    ap.add_argument("--with-axiom-audit", action="store_true",
                    help="run the kernel/axiom audit stage (`check_axioms.py`; needs Lean/Lake)")
    ap.add_argument("--with-equivalence-check", action="store_true",
                    help="run the provable-equivalence stage (`check_equivalence.py`; needs Lean "
                         "only for PASS_PROVABLE_EQUIV targets)")
    ap.add_argument("--writeback-comparator-status", action="store_true",
                    help="after the Comparator run, write the resulting status back to the "
                         "selected target's comparator_status in docs/formal_mapping.yaml "
                         "(opt-in; requires --target and --with-comparator)")
    args = ap.parse_args()

    target, err = resolve_target(args.target, load_targets())
    if err:
        sys.stderr.write(f"ERROR: {err}\n")
        return 2

    wb_err = writeback_precondition_error(
        args.writeback_comparator_status, target, args.with_comparator)
    if wb_err:
        sys.stderr.write(f"ERROR: {wb_err}\n")
        return 2

    stages = [
        stage_card_and_mapping(),
        stage_judge_packages(),
        stage_build(args.with_build),
        stage_no_sorry(),
        stage_axiom_audit(args.with_axiom_audit, target),
        stage_equivalence_check(args.with_equivalence_check, target),
        stage_comparator(args.with_comparator, target),
    ]
    comparator_stage = stages[-1]

    writeback = None
    if args.writeback_comparator_status:
        env = comparator_env()
        abi_env = os.environ.get("COMPARATOR_LANDRUN_ABI")
        abi = int(abi_env) if (abi_env and abi_env.lstrip("-").isdigit()) else None
        new_status, reason = derive_comparator_status(
            comparator_stage.status, landrun_path=(env["landrun"] if env else None), abi=abi)
        if new_status is None:
            writeback = {"requested": True, "performed": False, "target": target,
                         "old": None, "new": None, "reason": reason}
        else:
            old = write_comparator_status(target, new_status)
            writeback = {"requested": True, "performed": True, "target": target,
                         "old": old, "new": new_status, "reason": reason}

    failed = [s for s in stages if s.status == FAIL]
    overall = FAIL if failed else PASS
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    write_report(stages, now, overall, target, writeback)

    scope = "all targets" if target is None else f"target {target}"
    print(f"PIPELINE {overall} ({scope}) — report: {REPORT.relative_to(ROOT)}")
    for s in stages:
        print(f"  [{s.status:>7}] {s.name}: {s.detail}")
    if writeback and writeback["performed"]:
        print(f"  [writeback] {target}.comparator_status: "
              f"{writeback['old']} -> {writeback['new']}")
    elif writeback:
        print(f"  [writeback] requested but not applied: {writeback['reason']}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
