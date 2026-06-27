#!/usr/bin/env python3
"""Import manually-collected judge responses.

After a human pastes each exported request (docs/judge_requests/<target>/<blind_id>.md)
into the chosen judge and saves the strict-YAML reply as
docs/judge_responses_manual/<target>/<blind_id>.yaml, this script aggregates those replies
into docs/judge_results/<target>.yaml WITH provenance.

Guarantees:
  - it calls no model/API;
  - it reads _targets.yaml (membership), never _manifest.yaml (the answer key);
  - it writes docs/judge_results/<target>.yaml ONLY when ALL of a target's responses are
    present; if any are missing it refuses and writes nothing;
  - it does NOT score — scoring stays in scripts/score_judge.py.

Provenance (provider/model/temperature, prompt_sha256, input_sha256, mutants_sha256) is read
from the exported request files and cross-checked against freshly recomputed hashes, so the
imported results are tied to exactly what was sent to the judge.

Enabled targets are the keys under `targets:` in formal_mapping.yaml (no hard-coded target).
"""
from __future__ import annotations

import argparse
import re
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

# Reuse assembly-time constants/checks and the judge runner's hash helpers.
import run_mutants as rm
import run_judge as rj

ROOT = rm.ROOT
DRYRUN_DIR = rm.DRYRUN_DIR
TARGETS_FILE = DRYRUN_DIR / "_targets.yaml"
REQUESTS_DIR = ROOT / "docs" / "judge_requests"
RESPONSES_DIR = ROOT / "docs" / "judge_responses_manual"
RESULTS_DIR = ROOT / "docs" / "judge_results"

MEMBERSHIP_KEYS = {"target", "input_sha256"}
ALLOWED_VERDICTS = {
    "PASS", "PASS_EQUIV", "PASS_PROVABLE_EQUIV", "WARN", "FAIL", "OUT_OF_SCOPE",
}


def fail(msg: str) -> int:
    sys.stderr.write(f"ERROR: {msg}\n")
    return 1


def parse_request_provenance(md_path: Path) -> dict | None:
    """Return the first ```yaml fenced block (the Provenance block) as a dict, or None."""
    text = md_path.read_text(encoding="utf-8")
    m = re.search(r"```yaml\n(.*?)\n```", text, re.DOTALL)
    if not m:
        return None
    try:
        out = yaml.safe_load(m.group(1))
    except yaml.YAMLError:
        return None
    return out if isinstance(out, dict) else None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--target", default=None,
                    help="mapping target (defaults to the sole target if only one exists)")
    ap.add_argument("--force", action="store_true", help="overwrite an existing results file")
    args = ap.parse_args()

    allowed = rm.load_allowed_targets()
    target = args.target or (sorted(allowed)[0] if len(allowed) == 1 else None)
    if not target:
        return fail("--target is required (more than one target in formal_mapping.yaml).")
    if target not in allowed:
        return fail(f"target {target!r} is not in formal_mapping.yaml; enabled: {sorted(allowed)}.")

    responses_dir = RESPONSES_DIR / target
    if not responses_dir.exists() or not any(responses_dir.glob("*.yaml")):
        return fail(
            f"no manual responses found under docs/judge_responses_manual/{target}/. "
            f"Export requests with `python scripts/run_judge.py --target {target} "
            f"--provider <P> --model <M> --temperature 0.0 --export-manual`, run each through "
            f"the judge, and save each strict-YAML reply as <blind_id>.yaml there."
        )

    if not TARGETS_FILE.exists():
        return fail("_targets.yaml not found; run `python scripts/run_mutants.py --dry-run` first")
    membership = yaml.safe_load(TARGETS_FILE.read_text(encoding="utf-8")) or {}
    variants = membership.get("variants") or {}
    expected = sorted(b for b, e in variants.items() if e.get("target") == target)
    if not expected:
        return fail(f"no blind IDs for target {target} in _targets.yaml")

    # Require ALL responses present before writing anything.
    missing = [b for b in expected if not (responses_dir / f"{b}.yaml").exists()]
    if missing:
        return fail(
            f"incomplete: {len(expected) - len(missing)}/{len(expected)} responses present; "
            f"missing {missing}. docs/judge_results/{target}.yaml is not written until all "
            f"{len(expected)} responses exist."
        )

    prompt_sha256 = rm.sha256_bytes(rm.JUDGE_PROMPT.read_bytes())
    mutants_sha256 = rj.recompute_mutants_sha256()
    if membership.get("mutants_sha256") != mutants_sha256:
        return fail("mutants_sha256 mismatch; regenerate dry-run packages before importing")

    prov_seen = {"provider": set(), "model": set(), "temperature": set()}
    results = []
    for bid in expected:
        # 1. parse the human-saved strict-YAML judge reply
        resp_path = responses_dir / f"{bid}.yaml"
        try:
            resp = yaml.safe_load(resp_path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            return fail(f"{bid}: response is not valid YAML: {exc}")
        if not isinstance(resp, dict) or "verdict" not in resp:
            return fail(f"{bid}: response YAML missing required 'verdict' key")
        if resp.get("verdict") not in ALLOWED_VERDICTS:
            return fail(
                f"{bid}: response verdict {resp.get('verdict')!r} not in {sorted(ALLOWED_VERDICTS)}"
            )

        # 2. provenance from the exported request
        req_path = REQUESTS_DIR / target / f"{bid}.md"
        if not req_path.exists():
            return fail(
                f"{bid}: exported request {req_path.relative_to(ROOT)} missing; "
                f"run --export-manual first"
            )
        prov = parse_request_provenance(req_path)
        if not prov:
            return fail(f"{bid}: could not parse provenance from {req_path.relative_to(ROOT)}")

        # 3. cross-check every hash against freshly recomputed values
        pkg = (yaml.safe_load((DRYRUN_DIR / f"{bid}.yaml").read_text(encoding="utf-8")) or {}).get(
            "package"
        ) or {}
        input_sha256 = rm.sha256_text(rm.canonical(pkg))
        for field, val in (
            ("prompt_sha256", prompt_sha256),
            ("mutants_sha256", mutants_sha256),
            ("input_sha256", input_sha256),
        ):
            if prov.get(field) != val:
                return fail(f"{bid}: {field} in request provenance does not match recomputed value")
        if variants[bid].get("input_sha256") != input_sha256:
            return fail(f"{bid}: input_sha256 mismatch vs _targets.yaml")

        prov_seen["provider"].add(prov.get("provider"))
        prov_seen["model"].add(prov.get("model"))
        prov_seen["temperature"].add(prov.get("temperature"))
        results.append({
            "blind_id": bid,
            "input_sha256": input_sha256,
            "judge_verdict": resp.get("verdict"),
            "judge_output": resp,
            "provenance": {
                "provider": prov.get("provider"),
                "model": prov.get("model"),
                "temperature": prov.get("temperature"),
                "prompt_sha256": prompt_sha256,
                "input_sha256": input_sha256,
                "mutants_sha256": mutants_sha256,
                "de_anchored": True,
                "mode": "manual_import",
            },
        })

    for k, vals in prov_seen.items():
        if len(vals) != 1:
            return fail(f"inconsistent {k} across exported requests: {sorted(map(str, vals))}")

    out_path = RESULTS_DIR / f"{target}.yaml"
    if out_path.exists() and not args.force:
        return fail(f"{out_path.relative_to(ROOT)} already exists; pass --force to overwrite")

    ran_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "status": "MANUAL_IMPORT_COMPLETE",
        "target": target,
        "mode": "manual_import",
        "de_anchored": True,
        "provider": next(iter(prov_seen["provider"])),
        "model": next(iter(prov_seen["model"])),
        "temperature": next(iter(prov_seen["temperature"])),
        "prompt_sha256": prompt_sha256,
        "mutants_sha256": mutants_sha256,
        "ran_utc": ran_utc,
        "results": results,
    }
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=100), encoding="utf-8"
    )
    print(f"MANUAL_IMPORT_COMPLETE: wrote {len(results)} responses to {out_path.relative_to(ROOT)}")
    print(f"  Scoring is NOT performed here; run `python scripts/score_judge.py --target {target}`.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
