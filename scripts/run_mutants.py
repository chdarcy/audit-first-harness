#!/usr/bin/env python3
"""Offline judge/mutation harness for the audit-first pipeline.

**DRY-RUN ONLY.** This script assembles exactly the input packages a fidelity judge
would receive — for the real approved mapping and for every mutant — and writes them
to docs/judge_inputs_dryrun/ for human inspection. It does NOT call any model or API,
and it does NOT write docs/judge_results/. Those are deferred until the packages here
have been reviewed.

Inputs read:
  docs/theorem_index.yaml        source claims (paraphrase / verbatim / informal assumptions)
  docs/formal_mapping.yaml       targets, the approved verdict, the human-approval gate
  docs/fidelity_reviews/*.md     frontmatter only (second half of the human-approval gate)
  docs/mutants/<target>.yaml     real statement text + mutant test cases (expected labels)
  docs/judge_prompts/judge_v1.md the (hashed) judge system prompt

Outputs written:
  docs/judge_inputs_dryrun/<blind_id>.yaml   one per variant (meta + the exact judge package)
  docs/judge_inputs_dryrun/_manifest.yaml    blind_id -> answer key (OURS; never shown to a judge)
  docs/mutation_report.md                    summary (status: DRY_RUN_ONLY)

Anti-circularity: refuses to run unless all pilot targets are human_approved (in BOTH the
mapping and the review frontmatter) and at lifecycle state >= HUMAN_APPROVED. The mutant set
is hashed (mutants_sha256) so expected labels are frozen before any future judge run.

This is an MVP harness (v0.1, experimental). It does NOT translate LaTeX to Lean and does
NOT guarantee autonomous proof generation; it assembles blinded comparison packages from
artefacts a human/model agent authored and a human approved.
"""
from __future__ import annotations

import argparse
import hashlib
import json
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

ROOT = Path(__file__).resolve().parent.parent
THEOREM_INDEX = ROOT / "docs" / "theorem_index.yaml"
FORMAL_MAPPING = ROOT / "docs" / "formal_mapping.yaml"
REVIEWS_DIR = ROOT / "docs" / "fidelity_reviews"
MUTANTS_DIR = ROOT / "docs" / "mutants"
JUDGE_PROMPT = ROOT / "docs" / "judge_prompts" / "judge_v1.md"
DRYRUN_DIR = ROOT / "docs" / "judge_inputs_dryrun"
REPORT = ROOT / "docs" / "mutation_report.md"

ALLOWED_VERDICTS = {
    "PASS", "PASS_EQUIV", "PASS_PROVABLE_EQUIV", "WARN", "FAIL", "OUT_OF_SCOPE",
}
ALLOWED_CLASSES = {"discriminative", "consistency"}

# Lifecycle order; the gate requires state index >= index(HUMAN_APPROVED).
STATE_ORDER = [
    "EXTRACTED", "MAPPED", "FIDELITY_REVIEWED", "HUMAN_APPROVED",
    "PROVED", "AUDIT_BUILT", "COMPARATOR_PASSED", "DOCUMENTED",
]

# The judge package may contain ONLY these top-level keys.
PACKAGE_WHITELIST = {
    "variant", "instructions", "source", "lean", "formalisation_choices",
    "provable_equiv_lemma",
}

# Tokens that must never leak into a judge package (would de-anchor or reveal the key).
FORBIDDEN_TOKENS = [
    "human_approved", "human_approver", "human_approved_utc",
    "expected_verdict", "rationale", "real_statement_ref",
    "PASS_EQUIV", "PASS_PROVABLE_EQUIV", "OUT_OF_SCOPE",
    "discriminative", "consistency",
]


class HarnessError(Exception):
    pass


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_text(s: str) -> str:
    return sha256_bytes(s.encode("utf-8"))


def canonical(obj) -> str:
    """Stable serialization for hashing a package."""
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def load_yaml(path: Path) -> dict:
    if not path.exists():
        raise HarnessError(f"missing file: {path.relative_to(ROOT)}")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def load_allowed_targets() -> set[str]:
    """The enabled targets are exactly the keys under `targets:` in formal_mapping.yaml.

    This replaces the original project's hard-coded single-target allowlist, so the harness
    is driven by the mapping ledger rather than by a constant baked into each script."""
    mapping = load_yaml(FORMAL_MAPPING)
    return set((mapping.get("targets") or {}).keys())


def load_frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise HarnessError(f"{path.relative_to(ROOT)}: no YAML frontmatter")
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        raise HarnessError(f"{path.relative_to(ROOT)}: unterminated frontmatter")
    return yaml.safe_load("\n".join(lines[1:end])) or {}


def normalize_statement(text: str) -> str:
    """Blind the declaration name so the judge cannot tell real from mutant by name."""
    text = text.strip("\n")
    return re.sub(r"^\s*theorem\s+\S+", "theorem candidate_statement", text, count=1)


# ---------------------------------------------------------------------------
# Anti-circularity gate
# ---------------------------------------------------------------------------
def enforce_gate(mapping: dict) -> None:
    targets = mapping.get("targets") or {}
    if not targets:
        raise HarnessError("formal_mapping.yaml has no targets")
    ha_idx = STATE_ORDER.index("HUMAN_APPROVED")
    for name, t in targets.items():
        if t.get("human_approved") is not True:
            raise HarnessError(
                f"[{name}] mapping human_approved is not true; refusing to run"
            )
        state = t.get("state")
        if state not in STATE_ORDER:
            raise HarnessError(f"[{name}] unknown lifecycle state {state!r}")
        if STATE_ORDER.index(state) < ha_idx:
            raise HarnessError(
                f"[{name}] state {state} is below HUMAN_APPROVED; refusing to run"
            )
        review_rel = t.get("review")
        if not review_rel:
            raise HarnessError(f"[{name}] no review path")
        fm = load_frontmatter(ROOT / review_rel)
        if fm.get("human_approved") is not True:
            raise HarnessError(
                f"[{name}] review frontmatter human_approved is not true; refusing to run"
            )


# ---------------------------------------------------------------------------
# Package assembly
# ---------------------------------------------------------------------------
def build_source_block(source_refs, index_entries) -> dict:
    """Source-side material the judge may see. Excludes `notes` (which can name the
    Lean side or the verdict) — only paraphrase / verbatim body / informal assumptions."""
    claims = []
    for ref in source_refs:
        entry = index_entries.get(ref) or {}
        auto = entry.get("auto") or {}
        curated = entry.get("curated") or {}
        claim = {"ref": ref}
        if curated.get("paraphrase"):
            claim["paraphrase"] = curated["paraphrase"].strip()
        if auto.get("body_tex"):
            claim["body_tex"] = auto["body_tex"].strip("\n")
        if curated.get("informal_assumptions"):
            claim["informal_assumptions"] = list(curated["informal_assumptions"])
        claims.append(claim)
    return {"refs": list(source_refs), "claims": claims}


def build_package(blind_id, source_block, lean_ambient, statement_text,
                  formalisation_choices) -> dict:
    pkg = {
        "variant": blind_id,
        "instructions": (
            "Compare the source claim to the Lean statement and output the verdict "
            "YAML defined in the system prompt. Judge this package in isolation."
        ),
        "source": source_block,
        "lean": {
            "ambient": lean_ambient,
            "statement": normalize_statement(statement_text),
        },
        "formalisation_choices": list(formalisation_choices or []),
        "provable_equiv_lemma": None,
    }
    assert_package_clean(pkg)
    return pkg


def assert_package_clean(pkg: dict, target_name: str | None = None) -> None:
    extra = set(pkg.keys()) - PACKAGE_WHITELIST
    if extra:
        raise HarnessError(f"package has non-whitelisted keys: {sorted(extra)}")
    blob = canonical(pkg)
    forbidden = list(FORBIDDEN_TOKENS)
    if target_name:
        forbidden.append(target_name)
    for tok in forbidden:
        if tok in blob:
            raise HarnessError(
                f"forbidden token {tok!r} leaked into judge package {pkg.get('variant')}"
            )


# ---------------------------------------------------------------------------
# Main dry-run
# ---------------------------------------------------------------------------
def run_dry() -> int:
    index = load_yaml(THEOREM_INDEX)
    mapping = load_yaml(FORMAL_MAPPING)
    index_entries = index.get("entries") or {}
    targets = mapping.get("targets") or {}

    # --- gate (refuses before assembling anything) ---
    enforce_gate(mapping)

    if not JUDGE_PROMPT.exists():
        raise HarnessError(f"judge prompt missing: {JUDGE_PROMPT.relative_to(ROOT)}")
    prompt_sha256 = sha256_bytes(JUDGE_PROMPT.read_bytes())

    # --- freeze the mutant set (expected labels) before building packages ---
    mutant_files = sorted(MUTANTS_DIR.glob("*.yaml"))
    if not mutant_files:
        raise HarnessError(f"no mutant files under {MUTANTS_DIR.relative_to(ROOT)}")
    h = hashlib.sha256()
    for mf in mutant_files:
        h.update(mf.name.encode("utf-8"))
        h.update(b"\0")
        h.update(mf.read_bytes())
        h.update(b"\0")
    mutants_sha256 = h.hexdigest()

    # --- assemble variants ---
    variants = []  # each: dict(target, variant_id, class, operator, expected_verdict, package)
    per_target = {}

    for mf in mutant_files:
        mdoc = load_yaml(mf)
        target = mdoc.get("target")
        if target not in targets:
            raise HarnessError(f"{mf.name}: target {target!r} not in formal_mapping.yaml")
        tmap = targets[target]
        source_block = build_source_block(tmap.get("source_refs") or [], index_entries)
        choices = mdoc.get("formalisation_choices") or []
        ambient = mdoc.get("lean_ambient", "")

        counts = {"real": 0, "discriminative": 0, "consistency": 0, "operators": set()}

        # (a) the real approved mapping -> expected = the mapping's own verdict
        real_stmt = mdoc.get("real_statement")
        if not real_stmt:
            raise HarnessError(f"{mf.name}: missing real_statement")
        real_pkg = build_package("PENDING", source_block, ambient, real_stmt, choices)
        assert_package_clean(real_pkg, target_name=target)
        variants.append({
            "target": target,
            "variant_id": mdoc.get("real_statement_ref", "real"),
            "class": "real",
            "operator": "none",
            "expected_verdict": tmap.get("verdict"),
            "package": real_pkg,
        })
        counts["real"] += 1

        # (b) every mutant -> expected = its fixed label
        for mut in mdoc.get("mutants") or []:
            cls = mut.get("class")
            if cls not in ALLOWED_CLASSES:
                raise HarnessError(f"{mf.name}:{mut.get('id')}: bad class {cls!r}")
            ev = mut.get("expected_verdict")
            if ev not in ALLOWED_VERDICTS:
                raise HarnessError(f"{mf.name}:{mut.get('id')}: bad expected_verdict {ev!r}")
            stmt = mut.get("mutated_statement")
            if not stmt:
                raise HarnessError(f"{mf.name}:{mut.get('id')}: missing mutated_statement")
            pkg = build_package("PENDING", source_block, ambient, stmt, choices)
            assert_package_clean(pkg, target_name=target)
            variants.append({
                "target": target,
                "variant_id": mut.get("id"),
                "class": cls,
                "operator": mut.get("operator"),
                "expected_verdict": ev,
                "package": pkg,
            })
            counts[cls] += 1
            counts["operators"].add(mut.get("operator"))

        per_target[target] = counts

    # --- assign blind IDs in a deterministic shuffled order (seeded by mutants_sha256) ---
    import random
    rng = random.Random(int(mutants_sha256[:16], 16))
    order = list(range(len(variants)))
    rng.shuffle(order)
    for new_pos, vi in enumerate(order, start=1):
        bid = f"V-{new_pos:04d}"
        variants[vi]["blind_id"] = bid
        variants[vi]["package"]["variant"] = bid

    # --- write dry-run package files + manifest ---
    if DRYRUN_DIR.exists():
        for old in DRYRUN_DIR.glob("*.yaml"):
            old.unlink()
    DRYRUN_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    manifest = {
        "_warning": "ANSWER KEY — maps blind_id to target/class/expected. NEVER sent to a judge.",
        "generated_utc": now,
        "prompt_sha256": prompt_sha256,
        "mutants_sha256": mutants_sha256,
        "dry_run": True,
        "variants": {},
    }

    # Membership-only sidecar: blind_id -> {target, input_sha256}. Carries NO
    # answer-key labels (no expected_verdict/class/operator/variant_id), so the
    # judge runner can resolve target membership without opening _manifest.yaml.
    targets_membership = {
        "_note": "Membership only (blind_id -> target + input_sha256). NO answer-key "
                 "labels. Safe for run_judge.py; _manifest.yaml remains the answer key.",
        "generated_utc": now,
        "mutants_sha256": mutants_sha256,
        "variants": {},
    }

    for v in variants:
        pkg = v["package"]
        input_sha256 = sha256_text(canonical(pkg))
        out = {
            "meta": {
                "blind_id": v["blind_id"],
                "dry_run": True,
                "prompt_sha256": prompt_sha256,
                "input_sha256": input_sha256,
                "mutants_sha256": mutants_sha256,
                "note": "DRY RUN ONLY. 'package' below is exactly what a judge would "
                        "receive as user content. 'meta' is NOT sent to the judge.",
            },
            "package": pkg,
        }
        (DRYRUN_DIR / f"{v['blind_id']}.yaml").write_text(
            yaml.safe_dump(out, sort_keys=False, allow_unicode=True, width=100),
            encoding="utf-8",
        )
        manifest["variants"][v["blind_id"]] = {
            "target": v["target"],
            "variant_id": v["variant_id"],
            "class": v["class"],
            "operator": v["operator"],
            "expected_verdict": v["expected_verdict"],
            "input_sha256": input_sha256,
        }
        targets_membership["variants"][v["blind_id"]] = {
            "target": v["target"],
            "input_sha256": input_sha256,
        }

    (DRYRUN_DIR / "_manifest.yaml").write_text(
        yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True, width=100),
        encoding="utf-8",
    )
    (DRYRUN_DIR / "_targets.yaml").write_text(
        yaml.safe_dump(targets_membership, sort_keys=False, allow_unicode=True, width=100),
        encoding="utf-8",
    )

    write_report(per_target, prompt_sha256, mutants_sha256, len(variants), now)

    print(f"DRY_RUN_ONLY: wrote {len(variants)} package(s) to "
          f"{DRYRUN_DIR.relative_to(ROOT)} (no model/API called).")
    print(f"  prompt_sha256:  {prompt_sha256}")
    print(f"  mutants_sha256: {mutants_sha256}")
    print(f"  report:         {REPORT.relative_to(ROOT)}")
    return 0


def write_report(per_target, prompt_sha256, mutants_sha256, total, now) -> None:
    lines = [
        "# Mutation report",
        "",
        "_Generated by `scripts/run_mutants.py --dry-run`._",
        "",
        "**Status: DRY_RUN_ONLY** — packages assembled and frozen for inspection; "
        "no model or API was called, and `docs/judge_results/` was not written.",
        "",
        f"- generated_utc: `{now}`",
        f"- prompt_sha256: `{prompt_sha256}`",
        f"- mutants_sha256: `{mutants_sha256}`",
        f"- total packages: **{total}** "
        f"(written to `docs/judge_inputs_dryrun/`, blinded as `V-XXXX`)",
        "",
        "| target | real | discriminative | consistency | operators covered |",
        "|---|---|---|---|---|",
    ]
    for target, c in per_target.items():
        ops = ", ".join(sorted(o for o in c["operators"] if o))
        lines.append(
            f"| {target} | {c['real']} | {c['discriminative']} | {c['consistency']} | {ops} |"
        )
    lines += [
        "",
        "## What a judge would see (per package)",
        "- `source`: source refs, paraphrase, verbatim `body_tex`, informal assumptions",
        "- `lean`: the ambient `variable` line and the statement (declaration name blinded "
        "to `candidate_statement`)",
        "- `formalisation_choices`: neutral modelling notes",
        "- `provable_equiv_lemma`: `null` (no in-Lean biconditional yet)",
        "",
        "## What a judge does NOT see (asserted absent)",
        "- human approval / approver / date, the prior verdict, formaliser rationale",
        "- the mutant's expected label, class, or operator, and the real target name",
        "",
        "> Deferred (NOT done here): real judge execution, `docs/judge_results/<target>.yaml`, "
        "and the discriminative-recall / consistency-false-alarm metrics. Those run only after "
        "these dry-run packages are reviewed.",
        "",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--dry-run", action="store_true",
        help="assemble and write judge input packages for inspection (the only supported mode)",
    )
    args = ap.parse_args()
    if not args.dry_run:
        sys.stderr.write(
            "ERROR: only --dry-run is implemented. Real judge execution is deferred.\n"
        )
        return 2
    try:
        return run_dry()
    except HarnessError as exc:
        sys.stderr.write(f"REFUSED: {exc}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
