#!/usr/bin/env python3
"""Blinding-boundary regression tests (ARCHITECTURE.md §9).

Enforces that the **judge-facing path stays blinded**: `run_judge.py` and
`import_manual_judge_results.py` read only the membership sidecar `_targets.yaml` and must **never**
read the answer key `_manifest.yaml`. Un-blinding via `_manifest.yaml` is allowed only on the
scoring/export side (`score_judge.py`, `export_structured_judge_results.py`, ...).

Three layers:
  1. **Static** — the blinded scripts contain no *code-level* `_manifest` reference (docstrings that
     merely state the boundary are allowed; the scoring/export scripts must still reference it).
  2. **Runtime** — assemble fresh dry-run packages into a temp dir, then run `run_judge --dry-run`
     and confirm it works and its blinded output is identical whether `_manifest.yaml` is valid,
     poisoned with contradictory labels, or removed.
  3. **Allowed side** — `score_judge.py` / `export_structured_judge_results.py` still reference
     `_manifest.yaml`.

Pure, offline: no Lean, no model/API. All artifacts go to temp dirs (no repo mutation). Run:
    python scripts/test_blinding_boundary.py
"""
from __future__ import annotations

import ast
import contextlib
import io
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_mutants as rm  # noqa: E402
import run_judge as rj  # noqa: E402

SCRIPTS = Path(__file__).resolve().parent
BLINDED = ["run_judge.py", "import_manual_judge_results.py"]
UNBLINDING_ALLOWED = ["score_judge.py", "export_structured_judge_results.py"]

_failures: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(f"  [{'ok  ' if cond else 'FAIL'}] {name}" + (f" -- {detail}" if (detail and not cond) else ""))
    if not cond:
        _failures.append(name)


def code_string_constants(path: Path) -> list[str]:
    """All string-literal *values* in a module EXCEPT module/class/function docstrings.

    Comments are not AST nodes, so prose `# ... _manifest.yaml ...` is naturally excluded; only a
    string literal that the code actually uses (e.g. a path component) is returned. This lets the
    blinded scripts *document* the boundary in their docstrings while still forbidding any
    code-level `_manifest` reference."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docstring_ids = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(node, "body", [])
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(getattr(body[0], "value", None), ast.Constant)
                    and isinstance(body[0].value.value, str)):
                docstring_ids.add(id(body[0].value))
    return [n.value for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docstring_ids]


# --------------------------- 1. static boundary ---------------------------
def test_blinded_scripts_have_no_code_manifest_reference() -> None:
    for fn in BLINDED:
        consts = code_string_constants(SCRIPTS / fn)
        offenders = [s for s in consts if "_manifest" in s]
        check(f"{fn}: no code-level '_manifest' string literal",
              offenders == [], f"offending literals: {offenders}")


def test_blinded_scripts_read_targets_membership() -> None:
    for fn in BLINDED:
        consts = code_string_constants(SCRIPTS / fn)
        check(f"{fn}: references the membership sidecar '_targets.yaml'",
              any("_targets" in s for s in consts), "no _targets reference found")


def test_unblinding_scripts_do_reference_manifest() -> None:
    # Guard the guard: the scoring/export side must still read the answer key (else the static test
    # could pass vacuously after a refactor).
    for fn in UNBLINDING_ALLOWED:
        consts = code_string_constants(SCRIPTS / fn)
        check(f"{fn}: still references '_manifest.yaml' (un-blinding allowed here)",
              any("_manifest" in s for s in consts), "no _manifest reference found")


def test_blinded_modules_define_no_manifest_path_constant() -> None:
    # score_judge/export define `MANIFEST = ... _manifest.yaml`; the blinded modules must not.
    for fn in BLINDED:
        mod = __import__(fn[:-3])
        man = getattr(mod, "MANIFEST", None)
        check(f"{fn[:-3]}: no MANIFEST module attribute", man is None, f"MANIFEST={man}")


# --------------------------- 2. runtime / poison ---------------------------
def _assemble_into(tmp: Path) -> None:
    """Assemble fresh dry-run packages into `tmp` by pointing run_mutants' output globals there.
    Hashes are computed from the real prompt + mutants, so run_judge (which keeps the real
    MUTANTS_DIR / JUDGE_PROMPT) accepts them. The real repo dirs are never touched."""
    with contextlib.redirect_stdout(io.StringIO()):
        rc = rm.run_dry()
    assert rc == 0, "run_mutants.run_dry() failed"


def _run_judge_dry(target: str) -> list:
    import yaml
    with contextlib.redirect_stdout(io.StringIO()):
        rc = rj.run_dry(target, "openai", "test-model", 0.0, force=True)
    assert rc == 0, "run_judge.run_dry() failed"
    preview = yaml.safe_load((rj.RESULTS_DIR / f"{target}_preview.yaml").read_text(encoding="utf-8"))
    return preview.get("selected")  # the blinded {blind_id, input_sha256} list


def test_blinded_dry_run_independent_of_manifest() -> None:
    target = "PutCallParity"
    saved = {k: getattr(rm, k) for k in ("DRYRUN_DIR", "REPORT")}
    saved_rj = {k: getattr(rj, k) for k in ("DRYRUN_DIR", "TARGETS_FILE", "RESULTS_DIR")}
    # The scripts print paths via `.relative_to(ROOT)`, so the scratch dir must live *under* the
    # repo root; it is removed in `finally` (never committed). The real docs/ dirs are untouched
    # because DRYRUN_DIR/REPORT/RESULTS_DIR are redirected here.
    tmp = Path(tempfile.mkdtemp(prefix=".blinding_test_", dir=str(rm.ROOT)))
    try:
        rm.DRYRUN_DIR = tmp
        rm.REPORT = tmp / "mutation_report.md"
        _assemble_into(tmp)
        check("assembly wrote _targets.yaml", (tmp / "_targets.yaml").exists())
        check("assembly wrote _manifest.yaml", (tmp / "_manifest.yaml").exists())

        rj.DRYRUN_DIR = tmp
        rj.TARGETS_FILE = tmp / "_targets.yaml"
        rj.RESULTS_DIR = tmp

        # A: valid manifest present
        sel_valid = _run_judge_dry(target)
        check("dry-run works with a valid _manifest present", sel_valid is not None and len(sel_valid) > 0)

        # B: manifest poisoned with deliberately contradictory labels
        (tmp / "_manifest.yaml").write_text(
            "_warning: POISON\nvariants:\n  V-0001: {target: WRONG_TARGET, expected_verdict: FAIL, class: real}\n",
            encoding="utf-8")
        sel_poison = _run_judge_dry(target)
        check("dry-run still works with a POISONED _manifest", sel_poison is not None)

        # C: manifest removed entirely
        (tmp / "_manifest.yaml").unlink()
        check("manifest removed", not (tmp / "_manifest.yaml").exists())
        sel_absent = _run_judge_dry(target)
        check("dry-run still works with NO _manifest (blinded path needs only _targets)",
              sel_absent is not None)

        # Independence: the blinded output is identical regardless of the manifest.
        check("blinded selection independent of manifest poison",
              sel_valid == sel_poison, f"{sel_valid} != {sel_poison}")
        check("blinded selection independent of manifest removal",
              sel_valid == sel_absent, f"{sel_valid} != {sel_absent}")
    finally:
        for k, v in saved.items():
            setattr(rm, k, v)
        for k, v in saved_rj.items():
            setattr(rj, k, v)
        shutil.rmtree(tmp, ignore_errors=True)


# --------------------------- 3. allowed side ---------------------------
def test_scoring_side_reads_manifest_at_runtime() -> None:
    import score_judge as sj
    import export_structured_judge_results as ex
    check("score_judge.MANIFEST points at _manifest.yaml",
          getattr(sj, "MANIFEST", None) is not None and sj.MANIFEST.name == "_manifest.yaml")
    check("export.MANIFEST points at _manifest.yaml",
          getattr(ex, "MANIFEST", None) is not None and ex.MANIFEST.name == "_manifest.yaml")


def main() -> int:
    tests = [
        test_blinded_scripts_have_no_code_manifest_reference,
        test_blinded_scripts_read_targets_membership,
        test_unblinding_scripts_do_reference_manifest,
        test_blinded_modules_define_no_manifest_path_constant,
        test_blinded_dry_run_independent_of_manifest,
        test_scoring_side_reads_manifest_at_runtime,
    ]
    for t in tests:
        print(t.__name__)
        t()
    print()
    if _failures:
        print(f"FAIL: {len(_failures)} assertion(s) failed: {_failures}")
        return 1
    print("PASS: all blinding-boundary assertions passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
