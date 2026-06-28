#!/usr/bin/env python3
"""Offline provable-equivalence audit.

For each selected target in docs/formal_mapping.yaml:
  - verdict != PASS_PROVABLE_EQUIV  -> NOT_REQUIRED (no Lean run);
  - verdict == PASS_PROVABLE_EQUIV  -> require equivalence evidence
        {kind: provable_equiv, lemma, module}, then run Lean to confirm the lemma resolves and
        builds, and — reusing the axiom audit — depends only on `permitted_axioms` (no sorryAx).

This makes PASS_PROVABLE_EQUIV an *evidence-backed* state: a model merely saying "provably
equivalent" is never enough. It needs Lean/Lake + built oleans (like check_axioms.py); it calls
no model/API and does not touch the Comparator.

Usage:
    python scripts/check_equivalence.py                 # all targets
    python scripts/check_equivalence.py --target T       # one target
    python scripts/check_equivalence.py --json           # machine-readable

Exit 0 if every required check passes (NOT_REQUIRED counts as pass), 1 if any fails, 2 on a
usage error.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    import yaml
except ModuleNotFoundError:
    sys.stderr.write("ERROR: PyYAML is required. Install it with: python -m pip install pyyaml\n")
    sys.exit(2)

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_axioms as ca       # noqa: E402  reuse parse_axioms/classify/permitted_axioms/resolve_targets
import validate_mapping as vm   # noqa: E402  reuse equivalence_evidence_error

ROOT = ca.ROOT
FORMAL_MAPPING = ca.FORMAL_MAPPING
PROVABLE = "PASS_PROVABLE_EQUIV"


def run_lemma_check(module: str, lemma: str) -> tuple[int, str]:
    """`lake env lean` on `import module; #check @lemma; #print axioms lemma`. Returns (rc, out).
    The temp file lives under the system temp dir and is never written into the repo."""
    src = f"import {module}\n#check @{lemma}\n#print axioms {lemma}\n"
    with tempfile.TemporaryDirectory() as tmp:
        f = Path(tmp) / "equivalence_check.lean"
        f.write_text(src, encoding="utf-8")
        proc = subprocess.run(["lake", "env", "lean", str(f)], cwd=str(ROOT),
                              capture_output=True, text=True)
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def audit_target(name: str, tmap: dict, permitted: list[str]) -> dict:
    """Run the equivalence audit for one target; return a result record."""
    verdict = tmap.get("verdict")
    rec = {"target": name, "verdict": verdict, "kind": None, "lemma": None, "module": None,
           "axioms": None, "unexpected": None, "status": "FAIL", "detail": ""}
    if verdict != PROVABLE:
        rec["status"] = "NOT_REQUIRED"
        rec["detail"] = f"verdict {verdict!r}; no provable-equivalence evidence required"
        return rec

    eq = tmap.get("equivalence")
    err = vm.equivalence_evidence_error(eq)
    if err:
        rec["detail"] = f"PASS_PROVABLE_EQUIV is missing equivalence evidence ({err})"
        return rec
    rec["kind"], rec["lemma"], rec["module"] = eq.get("kind"), eq.get("lemma"), eq.get("module")

    rc, out = run_lemma_check(rec["module"], rec["lemma"])
    if rc != 0:
        rec["detail"] = (f"lean exited {rc} (lemma unresolved or build failed): "
                         + " ".join(out.split())[:300])
        return rec
    axioms, perr = ca.parse_axioms(out)
    if perr:
        rec["detail"] = perr
        return rec
    rec["axioms"] = sorted(axioms)
    status, unexpected = ca.classify(axioms, permitted)
    rec["unexpected"] = unexpected
    if status != "PASS":
        rec["detail"] = (f"INCOMPLETE/UNSOUND: equivalence lemma {rec['lemma']} depends on "
                         f"unexpected axioms {unexpected}")
        return rec
    rec["status"] = "PASS"
    rec["detail"] = (f"equivalence lemma {rec['lemma']} builds; axioms {sorted(axioms)} "
                     f"within permitted")
    return rec


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Verify in-Lean equivalence lemmas for PASS_PROVABLE_EQUIV targets.")
    ap.add_argument("--target", default=None, help="audit one mapping target (default: all)")
    ap.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = ap.parse_args()

    mapping = yaml.safe_load(FORMAL_MAPPING.read_text(encoding="utf-8")) or {}
    perm = ca.permitted_axioms(mapping)
    names, err = ca.resolve_targets(mapping, args.target)
    if err:
        sys.stderr.write(f"ERROR: {err}\n")
        return 2
    if not names:
        sys.stderr.write("ERROR: no targets in formal_mapping.yaml\n")
        return 2

    targets = mapping.get("targets") or {}
    results = [audit_target(n, targets[n], perm) for n in names]
    ok = all(r["status"] in ("PASS", "NOT_REQUIRED") for r in results)

    if args.json:
        print(json.dumps({"permitted_axioms": perm, "all_pass": ok, "results": results}, indent=2))
    else:
        for r in results:
            print(f"[{r['status']:>12}] {r['target']} ({r['lemma'] or '-'}): {r['detail']}")
        n_ok = sum(r["status"] in ("PASS", "NOT_REQUIRED") for r in results)
        print(f"\n{'PASS' if ok else 'FAIL'}: {n_ok}/{len(results)} target(s) satisfy the "
              f"provable-equivalence policy.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
