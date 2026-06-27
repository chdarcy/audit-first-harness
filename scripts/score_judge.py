#!/usr/bin/env python3
"""Score judge results for one target against the local answer key.

Reads docs/judge_results/<target>.yaml (written by run_judge.py --execute-api or by
import_manual_judge_results.py) and joins it, by blind_id, to the answer key
docs/judge_inputs_dryrun/_manifest.yaml — locally, never sent to a model. Writes
docs/judge_results/<target>_scored.yaml and appends/replaces a "Judge results — <target>"
section in docs/mutation_report.md.

Guarantees:
  - it calls no model/API;
  - it never modifies formal_mapping.yaml or docs/fidelity_reviews/;
  - if real results do not exist yet it is a safe no-op (prints a deferral message, writes
    nothing, exits 0);
  - it refuses to overwrite <target>_scored.yaml unless --force is passed.

Bucketing: accept = {PASS, PASS_EQUIV, PASS_PROVABLE_EQUIV}; reject = {WARN, FAIL};
OUT_OF_SCOPE is neither and therefore counts as incorrect for these tests.

The expected per-target record count is derived from the answer key (no hard-coded count).
The --results/--out/--report/--manifest overrides exist for testing; with no overrides the
canonical repo paths are used.
"""
from __future__ import annotations

import argparse
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
RESULTS_DIR = ROOT / "docs" / "judge_results"
MANIFEST = ROOT / "docs" / "judge_inputs_dryrun" / "_manifest.yaml"
MUTATION_REPORT = ROOT / "docs" / "mutation_report.md"
FORMAL_MAPPING = ROOT / "docs" / "formal_mapping.yaml"

ACCEPT = {"PASS", "PASS_EQUIV", "PASS_PROVABLE_EQUIV"}
REJECT = {"WARN", "FAIL"}
ALL_VERDICTS = ACCEPT | REJECT | {"OUT_OF_SCOPE"}


def fail(msg: str) -> int:
    sys.stderr.write(f"ERROR: {msg}\n")
    return 1


def load_allowed_targets() -> set[str]:
    """Enabled targets are the keys under `targets:` in formal_mapping.yaml."""
    doc = yaml.safe_load(FORMAL_MAPPING.read_text(encoding="utf-8")) or {}
    return set((doc.get("targets") or {}).keys())


def bucket(verdict: str | None) -> str:
    if verdict in ACCEPT:
        return "accept"
    if verdict in REJECT:
        return "reject"
    return "neither"  # OUT_OF_SCOPE or anything unexpected -> never matches accept/reject


def extract_records(doc) -> list[dict]:
    """Normalise the results document to a list of record dicts. Supports a top-level list,
    a {'results': [...]} mapping, or a {blind_id: record} mapping."""
    if isinstance(doc, list):
        return [r for r in doc if isinstance(r, dict)]
    if isinstance(doc, dict):
        if isinstance(doc.get("results"), list):
            return [r for r in doc["results"] if isinstance(r, dict)]
        recs = []
        for key, val in doc.items():
            if isinstance(val, dict) and any(
                k in val for k in ("judge_verdict", "judge_output", "response")
            ):
                r = dict(val)
                r.setdefault("blind_id", key)
                recs.append(r)
        return recs
    return []


def record_verdict(rec: dict) -> str | None:
    if rec.get("judge_verdict"):
        return rec["judge_verdict"]
    out = rec.get("judge_output") or rec.get("response")
    if isinstance(out, dict):
        return out.get("verdict")
    return None


def build_report_section(target: str, scored: dict) -> str:
    m = scored["metrics"]
    lines = [
        f"## Judge results — {target}",
        "",
        f"_Scored {scored['scored_utc']} by `scripts/score_judge.py` against the local "
        f"answer key (`_manifest.yaml`); no model was called during scoring._",
        "",
        f"- real_mapping_agreement_exact: **{m['real_mapping_agreement_exact']}**",
        f"- real_mapping_agreement_bucket: **{m['real_mapping_agreement_bucket']}**",
        f"- discriminative_recall: **{m['discriminative_recall']}** "
        f"({m['counts']['discriminative']} discriminative mutant(s))",
        f"- consistency_false_alarm_rate: **{m['consistency_false_alarm_rate']}** "
        f"({m['counts']['consistency']} consistency mutant(s))",
        f"- overall_bucket_accuracy: **{m['overall_bucket_accuracy']}** "
        f"(over {m['counts']['total']} variants)",
        "",
        "| blind_id | class | operator | expected | judge | bucket_match | exact_match |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in scored["per_variant"]:
        lines.append(
            f"| {r['blind_id']} | {r['class']} | {r['operator']} | "
            f"{r['expected_verdict']} | {r['judge_verdict']} | "
            f"{r['bucket_match']} | {r['exact_match']} |"
        )
    lines.append("")
    return "\n".join(lines)


def update_report(report_path: Path, target: str, section_md: str) -> None:
    begin = f"<!-- BEGIN judge-results:{target} -->"
    end = f"<!-- END judge-results:{target} -->"
    block = f"{begin}\n{section_md}\n{end}\n"
    existing = report_path.read_text(encoding="utf-8") if report_path.exists() else ""
    if begin in existing and end in existing:
        pre = existing[: existing.index(begin)]
        post = existing[existing.index(end) + len(end):]
        new = pre + block + post.lstrip("\n")
    else:
        sep = "" if existing.endswith("\n\n") or not existing else ("\n" if existing.endswith("\n") else "\n\n")
        new = existing + sep + "\n" + block
    report_path.write_text(new, encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--target", default=None,
                    help="mapping target (defaults to the sole target if only one exists)")
    ap.add_argument("--force", action="store_true", help="overwrite an existing *_scored.yaml")
    ap.add_argument("--results", help="override path to <target>.yaml (testing)")
    ap.add_argument("--out", help="override path to <target>_scored.yaml (testing)")
    ap.add_argument("--report", help="override path to mutation_report.md (testing)")
    ap.add_argument("--manifest", help="override path to _manifest.yaml (testing)")
    args = ap.parse_args()

    allowed = load_allowed_targets()
    target = args.target or (sorted(allowed)[0] if len(allowed) == 1 else None)
    if not target:
        return fail("--target is required (more than one target in formal_mapping.yaml).")
    if target not in allowed:
        return fail(f"target {target!r} is not in formal_mapping.yaml; enabled: {sorted(allowed)}.")

    results_path = Path(args.results) if args.results else RESULTS_DIR / f"{target}.yaml"
    out_path = Path(args.out) if args.out else RESULTS_DIR / f"{target}_scored.yaml"
    report_path = Path(args.report) if args.report else MUTATION_REPORT
    manifest_path = Path(args.manifest) if args.manifest else MANIFEST

    # No-results behaviour: safe no-op.
    if not results_path.exists():
        print("No real judge results found; scoring deferred.")
        print(f"  (expected at {results_path} once real responses are imported)")
        return 0

    if out_path.exists() and not args.force:
        return fail(f"{out_path} already exists; pass --force to overwrite")

    manifest_doc = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    man = manifest_doc.get("variants") or {}
    if not man:
        return fail(f"answer key {manifest_path} has no 'variants'")
    man_prompt = manifest_doc.get("prompt_sha256")
    man_mut = manifest_doc.get("mutants_sha256")

    results_doc = yaml.safe_load(results_path.read_text(encoding="utf-8")) or {}
    records = extract_records(results_doc)

    expected_ids = {bid for bid, v in man.items() if v.get("target") == target}
    expected_count = len(expected_ids)

    # ---- validation -----------------------------------------------------
    errors: list[str] = []
    rec_by_bid: dict[str, dict] = {}
    for r in records:
        bid = r.get("blind_id")
        if not bid:
            errors.append("a record is missing 'blind_id'")
            continue
        if bid in rec_by_bid:
            errors.append(f"{bid}: duplicate record")
            continue
        rec_by_bid[bid] = r
        if bid not in man:
            errors.append(f"{bid}: blind_id not present in answer key")
            continue
        if man[bid].get("target") != target:
            errors.append(f"{bid}: belongs to target {man[bid].get('target')!r}, not {target}")
        if r.get("input_sha256") != man[bid].get("input_sha256"):
            errors.append(f"{bid}: input_sha256 does not match answer key")
        jv = record_verdict(r)
        if jv not in ALL_VERDICTS:
            errors.append(f"{bid}: judge_verdict {jv!r} not one of {sorted(ALL_VERDICTS)}")
        if not r.get("provenance"):
            errors.append(f"{bid}: missing provenance")

    seen = set(rec_by_bid)
    if seen != expected_ids:
        missing = sorted(expected_ids - seen)
        extra = sorted(seen - expected_ids)
        if missing:
            errors.append(f"missing {target} variants: {missing}")
        if extra:
            errors.append(f"unexpected variants for {target}: {extra}")
    if len(records) != expected_count:
        errors.append(f"expected exactly {expected_count} {target} records, got {len(records)}")

    # provenance hash consistency (if the results carry hashes, they must match the key)
    res_prompt = results_doc.get("prompt_sha256") if isinstance(results_doc, dict) else None
    res_mut = results_doc.get("mutants_sha256") if isinstance(results_doc, dict) else None
    if res_prompt and man_prompt and res_prompt != man_prompt:
        errors.append("results prompt_sha256 does not match answer key")
    if res_mut and man_mut and res_mut != man_mut:
        errors.append("results mutants_sha256 does not match answer key")

    if errors:
        for e in errors:
            print(f"ERROR: {e}")
        print(f"\nFAIL: {len(errors)} validation error(s); nothing written.")
        return 1

    # ---- scoring --------------------------------------------------------
    rows = []
    for bid in sorted(expected_ids):
        m = man[bid]
        jv = record_verdict(rec_by_bid[bid])
        ev = m.get("expected_verdict")
        eb, jb = bucket(ev), bucket(jv)
        rows.append({
            "blind_id": bid,
            "variant_id": m.get("variant_id"),
            "class": m.get("class"),
            "operator": m.get("operator"),
            "expected_verdict": ev,
            "judge_verdict": jv,
            "expected_bucket": eb,
            "judge_bucket": jb,
            "bucket_match": jb == eb,
            "exact_match": jv == ev,
        })

    real = next((r for r in rows if r["class"] == "real"), None)
    disc = [r for r in rows if r["class"] == "discriminative"]
    cons = [r for r in rows if r["class"] == "consistency"]
    if real is None or not disc or not cons:
        return fail("answer key is missing a real / discriminative / consistency variant")

    disc_recall = sum(1 for r in disc if r["judge_bucket"] == "reject") / len(disc)
    cons_far = sum(1 for r in cons if r["judge_bucket"] == "reject") / len(cons)
    overall = sum(1 for r in rows if r["bucket_match"]) / len(rows)

    per_operator: dict[str, dict] = {}
    for r in rows:
        d = per_operator.setdefault(
            r["operator"], {"class": r["class"], "n": 0, "exact_match": 0, "bucket_match": 0}
        )
        d["n"] += 1
        d["exact_match"] += int(r["exact_match"])
        d["bucket_match"] += int(r["bucket_match"])

    scored = {
        "target": target,
        "prompt_sha256": man_prompt,
        "mutants_sha256": man_mut,
        "scored_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "metrics": {
            "real_mapping_agreement_exact": bool(real["exact_match"]),
            "real_mapping_agreement_bucket": bool(real["bucket_match"]),
            "discriminative_recall": round(disc_recall, 4),
            "consistency_false_alarm_rate": round(cons_far, 4),
            "overall_bucket_accuracy": round(overall, 4),
            "counts": {
                "real": 1,
                "discriminative": len(disc),
                "consistency": len(cons),
                "total": len(rows),
            },
            "per_operator": per_operator,
        },
        "per_variant": rows,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        yaml.safe_dump(scored, sort_keys=False, allow_unicode=True, width=100), encoding="utf-8"
    )
    update_report(report_path, target, build_report_section(target, scored))

    mx = scored["metrics"]
    print(f"SCORED: {out_path}")
    print(f"  real_mapping_agreement_exact:  {mx['real_mapping_agreement_exact']}")
    print(f"  real_mapping_agreement_bucket: {mx['real_mapping_agreement_bucket']}")
    print(f"  discriminative_recall:         {mx['discriminative_recall']}")
    print(f"  consistency_false_alarm_rate:  {mx['consistency_false_alarm_rate']}")
    print(f"  overall_bucket_accuracy:       {mx['overall_bucket_accuracy']}")
    print(f"  report section updated:        {report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
