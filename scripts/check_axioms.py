#!/usr/bin/env python3
"""Offline kernel/axiom audit of the mapped Lean declarations.

For each selected target in docs/formal_mapping.yaml this runs Lean's `#print axioms` on the
mapped declaration and confirms its axiom set is a subset of `permitted_axioms`. A dependency on
`sorryAx` (an incomplete proof) — or on any axiom outside the permitted set — fails the target.

This AUGMENTS the textual scan in check_sorries.py with a kernel-level signal; it does not
replace it. It needs Lean/Lake and the project's built oleans (it runs `lake env lean` on a tiny
temp file under the system temp dir). It calls no model/API and does not touch the Comparator.

Usage:
    python scripts/check_axioms.py                 # all targets
    python scripts/check_axioms.py --target T       # one target
    python scripts/check_axioms.py --json           # machine-readable

Exit code 0 if every checked target passes, 1 if any fails, 2 on a usage error.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    import yaml
except ModuleNotFoundError:
    sys.stderr.write("ERROR: PyYAML is required. Install it with: python -m pip install pyyaml\n")
    sys.exit(2)

ROOT = Path(__file__).resolve().parent.parent
FORMAL_MAPPING = ROOT / "docs" / "formal_mapping.yaml"

# Documented permitted set; used only if the mapping omits `permitted_axioms`.
DEFAULT_PERMITTED = ["propext", "Quot.sound", "Classical.choice"]

# The axiom an incomplete proof depends on; never permitted, flagged explicitly.
SORRY_AXIOM = "sorryAx"


# ---------------------------------------------------------------------------
# Pure helpers (unit-testable; no Lean, no I/O)
# ---------------------------------------------------------------------------
def permitted_axioms(mapping: dict) -> list[str]:
    perm = mapping.get("permitted_axioms")
    return list(perm) if perm else list(DEFAULT_PERMITTED)


def resolve_targets(mapping: dict, target: str | None) -> tuple[list[str], str | None]:
    """Return (targets_to_check, error). target=None means all targets."""
    available = list((mapping.get("targets") or {}).keys())
    if target is None:
        return available, None
    if target in available:
        return [target], None
    return [], f"target {target!r} is not in formal_mapping.yaml; available: {sorted(available)}"


def target_lean(tmap: dict) -> tuple[str | None, str | None, str | None]:
    """Return (module, fully_qualified, error). Prefer fully_qualified; never guess a namespace."""
    lean = tmap.get("lean") or {}
    module = lean.get("module")
    fqn = lean.get("fully_qualified")
    if not module:
        return None, None, "mapping has no lean.module"
    if not fqn:
        return module, None, "mapping has no lean.fully_qualified (refusing to guess the namespace)"
    return module, fqn, None


def parse_axioms(output: str) -> tuple[set[str] | None, str | None]:
    """Parse `#print axioms` output conservatively. Returns (axiom_set, error).

    Recognises exactly two shapes:
      "'<name>' depends on axioms: [a, b, c]"   -> {a, b, c}
      "'<name>' does not depend on any axioms"  -> set()
    Anything else (Lean errors, unknown identifier, empty output) -> (None, error)."""
    if re.search(r"does not depend on any axioms", output):
        return set(), None
    m = re.search(r"depends on axioms:\s*\[([^\]]*)\]", output, re.DOTALL)
    if m:
        items = [a.strip() for a in m.group(1).split(",")]
        return {a for a in items if a}, None
    snippet = " ".join(output.split())[:300]
    return None, f"no '#print axioms' result in Lean output: {snippet or '(empty output)'}"


def classify(axioms: set[str], permitted: list[str]) -> tuple[str, list[str]]:
    """Return (status, sorted_unexpected). PASS iff axioms is a subset of permitted (sorryAx is
    never permitted, so it always lands in `unexpected`)."""
    permitted_set = set(permitted)
    unexpected = sorted(a for a in axioms if a not in permitted_set)
    return ("PASS" if not unexpected else "FAIL"), unexpected


# ---------------------------------------------------------------------------
# I/O layer
# ---------------------------------------------------------------------------
def run_print_axioms(module: str, fqn: str) -> tuple[int, str]:
    """Run `lake env lean <tmp>` for `import module; #print axioms fqn`. Returns (rc, output).
    The temp file lives under the system temp dir and is never written into the repo."""
    src = f"import {module}\n#print axioms {fqn}\n"
    with tempfile.TemporaryDirectory() as tmp:
        f = Path(tmp) / "axiom_audit.lean"
        f.write_text(src, encoding="utf-8")
        proc = subprocess.run(["lake", "env", "lean", str(f)], cwd=str(ROOT),
                              capture_output=True, text=True)
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def audit_target(name: str, tmap: dict, permitted: list[str]) -> dict:
    """Run the audit for one target and return a result record."""
    rec = {"target": name, "declaration": (tmap.get("lean") or {}).get("declaration"),
           "fully_qualified": None, "permitted": list(permitted), "axioms": None,
           "unexpected": None, "status": "FAIL", "detail": ""}
    module, fqn, err = target_lean(tmap)
    rec["fully_qualified"] = fqn
    if err:
        rec["detail"] = err
        return rec
    rc, out = run_print_axioms(module, fqn)
    if rc != 0:
        rec["detail"] = f"lean exited {rc}: " + " ".join(out.split())[:300]
        return rec
    axioms, perr = parse_axioms(out)
    if perr:
        rec["detail"] = perr
        return rec
    rec["axioms"] = sorted(axioms)
    status, unexpected = classify(axioms, permitted)
    rec["unexpected"], rec["status"] = unexpected, status
    if status == "PASS":
        rec["detail"] = f"axioms {sorted(axioms)} are within the permitted set"
    elif SORRY_AXIOM in unexpected:
        rec["detail"] = f"INCOMPLETE PROOF: depends on {SORRY_AXIOM} (unexpected: {unexpected})"
    else:
        rec["detail"] = f"unexpected axioms: {unexpected}"
    return rec


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Kernel/axiom audit of mapped Lean declarations (augments check_sorries.py).")
    ap.add_argument("--target", default=None, help="audit one mapping target (default: all)")
    ap.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = ap.parse_args()

    mapping = yaml.safe_load(FORMAL_MAPPING.read_text(encoding="utf-8")) or {}
    perm = permitted_axioms(mapping)
    names, err = resolve_targets(mapping, args.target)
    if err:
        sys.stderr.write(f"ERROR: {err}\n")
        return 2
    if not names:
        sys.stderr.write("ERROR: no targets in formal_mapping.yaml\n")
        return 2

    targets = mapping.get("targets") or {}
    results = [audit_target(n, targets[n], perm) for n in names]
    all_pass = all(r["status"] == "PASS" for r in results)

    if args.json:
        print(json.dumps({"permitted_axioms": perm, "all_pass": all_pass, "results": results},
                         indent=2))
    else:
        for r in results:
            print(f"[{r['status']:>4}] {r['target']} "
                  f"({r['fully_qualified'] or r['declaration']}): {r['detail']}")
        print(f"\n{'PASS' if all_pass else 'FAIL'}: "
              f"{sum(r['status'] == 'PASS' for r in results)}/{len(results)} "
              f"target(s) within permitted axioms {perm}.")
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
