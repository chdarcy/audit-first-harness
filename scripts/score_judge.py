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
import json
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

# Reuse the structured-schema validator (milestone 1a) rather than duplicating schema logic.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import validate_judge_schema as vjs  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = ROOT / "docs" / "judge_results"
MANIFEST = ROOT / "docs" / "judge_inputs_dryrun" / "_manifest.yaml"
MUTATION_REPORT = ROOT / "docs" / "mutation_report.md"
FORMAL_MAPPING = ROOT / "docs" / "formal_mapping.yaml"
MUTANTS_DIR = ROOT / "docs" / "mutants"

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


def parse_format_counts(records: list[dict]) -> dict:
    """Generic output-format health metrics, derived only from the judge result records.

    A record is `clean` when it carried no parse_error; `recovered` when it had a parse_error
    but a single verdict line was salvaged (recovered_verdict truthy); `unrecoverable` when it
    had a parse_error and no verdict could be recovered. Records that predate the parse_error /
    recovered_verdict fields (e.g. some manually-imported replies) default to clean. Target-
    agnostic: it inspects only per-record fields, never the answer key or any target name."""
    clean = recovered = unrecoverable = 0
    for r in records:
        if not r.get("parse_error"):
            clean += 1
        elif r.get("recovered_verdict"):
            recovered += 1
        else:
            unrecoverable += 1
    total = len(records)
    malformed = recovered + unrecoverable
    return {
        "parsed_clean_count": clean,
        "recovered_verdict_count": recovered,
        "unrecoverable_parse_error_count": unrecoverable,
        "malformed_yaml_rate": round(malformed / total, 4) if total else 0.0,
    }


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
        "Output-format health (parse of the raw judge replies):",
        "",
        f"- parsed_clean_count: **{m['parse_format']['parsed_clean_count']}**",
        f"- recovered_verdict_count: **{m['parse_format']['recovered_verdict_count']}**",
        f"- unrecoverable_parse_error_count: "
        f"**{m['parse_format']['unrecoverable_parse_error_count']}**",
        f"- malformed_yaml_rate: **{m['parse_format']['malformed_yaml_rate']}**",
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


# ===================================================================================
# Structured judge scoring (v0.3 milestone 1b) — see ARCHITECTURE.md §10.3.
#
# Scores stored *structured* judge-result JSON files (schema_version 0.3.0, §9.1) against the
# existing real/mutant answer key. It REUSES validate_judge_schema.py for schema validation and
# measures judge **reliability** only. It is offline, makes no promotion decision, and never lets a
# judge verdict override a formal-layer result (Lean build / no-sorry / axiom audit / Comparator /
# guarded equivalence). Buckets: accept = ACCEPT; reject = REJECT; UNPARSEABLE / schema-INVALID are
# parse/schema failures counted separately and excluded from the accept/reject rates.
# ===================================================================================

def build_structured_answer_key(mutants_dir: Path) -> dict:
    """{target: {candidate_id: class}} read from docs/mutants/*.yaml (read-only answer key).

    The real statement's candidate_id is 'real' (and, as an alias, the file's
    `real_statement_ref`); each mutant `id` maps to its declared `class`
    (`discriminative` / `consistency`)."""
    key: dict[str, dict[str, str]] = {}
    for mf in sorted(mutants_dir.glob("*.yaml")):
        doc = yaml.safe_load(mf.read_text(encoding="utf-8")) or {}
        target = doc.get("target")
        if not target:
            continue
        t = key.setdefault(target, {})
        t["real"] = "real"
        ref = doc.get("real_statement_ref")
        if isinstance(ref, str) and ref:
            t[ref] = "real"
        for m in doc.get("mutants") or []:
            if isinstance(m, dict) and m.get("id") and m.get("class"):
                t[str(m["id"])] = str(m["class"])
    return key


def structured_bucket(verdict: str | None) -> str:
    """accept / reject / parse_fail. UNPARSEABLE (and None/unexpected) are parse/schema failures."""
    if verdict in ACCEPT:
        return "accept"
    if verdict in REJECT:
        return "reject"
    return "parse_fail"


def score_one_structured(rec, answer_key: dict) -> dict:
    """Classify + bucket a single structured record against the answer key (pure)."""
    if isinstance(rec, dict):
        st = vjs.classify_record(rec)
        target = rec.get("target") if isinstance(rec.get("target"), str) else None
        cand = rec.get("candidate_id") if isinstance(rec.get("candidate_id"), str) else None
        concerns = rec.get("concerns") if isinstance(rec.get("concerns"), list) else []
    else:  # a load error placeholder, etc.
        st, target, cand, concerns = {"status": vjs.INVALID, "verdict": None}, None, None, []

    status = st["status"]
    verdict = st.get("verdict")
    cls = answer_key.get(target, {}).get(cand, "unknown") if target else "unknown"
    vb = structured_bucket(verdict)
    usable = status in (vjs.VALID, vjs.PARTIAL_RECOVERED) and vb in ("accept", "reject")
    hi = sum(1 for c in concerns
             if isinstance(c, dict) and c.get("severity") in ("high", "critical"))
    ctypes = [c.get("type") for c in concerns if isinstance(c, dict) and c.get("type")]
    return {
        "target": target, "candidate_id": cand, "class": cls,
        "schema_status": status, "verdict": verdict, "verdict_bucket": vb,
        "usable": usable, "is_unparseable": verdict == "UNPARSEABLE",
        "high_critical_concerns": hi, "concern_types": ctypes,
    }


def _rate(num: int, den: int):
    """Rounded rate, or None when the denominator is zero (no usable examples)."""
    return round(num / den, 4) if den else None


def _aggregate(entries: list[dict]) -> dict:
    total = len(entries)
    valid = sum(1 for e in entries if e["schema_status"] == vjs.VALID)
    partial = sum(1 for e in entries if e["schema_status"] == vjs.PARTIAL_RECOVERED)
    invalid = sum(1 for e in entries if e["schema_status"] == vjs.INVALID)
    unparseable = sum(1 for e in entries if e["is_unparseable"])

    by_class: dict[str, dict] = {}
    for e in entries:
        d = by_class.setdefault(
            e["class"], {"n": 0, "usable": 0, "accept": 0, "reject": 0, "parse_fail": 0})
        d["n"] += 1
        if e["usable"]:
            d["usable"] += 1
            d[e["verdict_bucket"]] += 1
        else:
            d["parse_fail"] += 1

    def c(name):
        return by_class.get(name, {"n": 0, "usable": 0, "accept": 0, "reject": 0, "parse_fail": 0})
    disc, cons, real = c("discriminative"), c("consistency"), c("real")

    concern_types: dict[str, int] = {}
    for e in entries:
        for t in e["concern_types"]:
            concern_types[t] = concern_types.get(t, 0) + 1

    return {
        "totals": {
            "total": total,
            "schema_valid": valid,
            "partial_recovered": partial,
            "invalid": invalid,
            "unparseable": unparseable,
            "schema_valid_rate": _rate(valid, total),
            "partial_recovered_rate": _rate(partial, total),
            "invalid_rate": _rate(invalid, total),
            "unparseable_rate": _rate(unparseable, total),
        },
        "reliability": {
            "discriminative_recall": _rate(disc["reject"], disc["usable"]),
            "false_acceptance_rate_discriminative": _rate(disc["accept"], disc["usable"]),
            "consistency_accept_rate": _rate(cons["accept"], cons["usable"]),
            "false_rejection_rate_consistency": _rate(cons["reject"], cons["usable"]),
            "real_accept_rate": _rate(real["accept"], real["usable"]),
        },
        "counts_by_class": by_class,
        "high_critical_concern_count": sum(e["high_critical_concerns"] for e in entries),
        "concern_types": concern_types,
    }


def score_structured_records(records: list, answer_key: dict) -> dict:
    """Score structured judge records against the answer key (pure, offline).

    Measures judge reliability: does the judge accept the real & consistency variants and reject
    the discriminative mutants? Makes no promotion decision."""
    entries = [score_one_structured(r, answer_key) for r in records]
    summary = _aggregate(entries)
    summary["expected_schema_version"] = vjs.SCHEMA_VERSION
    targets = sorted({e["target"] for e in entries if e["target"]})
    summary["per_target"] = {
        t: _aggregate([e for e in entries if e["target"] == t]) for t in targets
    }
    summary["per_record"] = entries
    return summary


def load_structured_records(path: Path) -> list:
    """Load structured records from a JSON file or a directory of *.json files.

    Each file may hold a single record, a list of records, or a {'results': [...]} mapping.
    A file that is not valid JSON contributes one placeholder that scores as INVALID/unknown."""
    files = sorted(path.glob("*.json")) if path.is_dir() else [path]
    records: list = []
    for f in files:
        try:
            obj = json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            records.append({"_load_error": str(f)})
            continue
        if isinstance(obj, list):
            records.extend([o for o in obj if isinstance(o, dict)])
        elif isinstance(obj, dict) and isinstance(obj.get("results"), list):
            records.extend([o for o in obj["results"] if isinstance(o, dict)])
        elif isinstance(obj, dict):
            records.append(obj)
    return records


def run_structured(args) -> int:
    path = Path(args.structured)
    if not path.exists():
        return fail(f"structured path not found: {path}")
    mutants_dir = Path(args.mutants_dir) if args.mutants_dir else MUTANTS_DIR
    answer_key = build_structured_answer_key(mutants_dir)
    records = load_structured_records(path)
    if not records:
        print("No structured judge records found; nothing to score.")
        return 0
    summary = score_structured_records(records, answer_key)
    summary["scored_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    summary["note"] = ("judge-reliability metrics only; not theorem truth and not a promotion "
                       "decision (see ARCHITECTURE.md §10.3)")
    text = json.dumps(summary, indent=2, sort_keys=True)
    if args.structured_out:
        outp = Path(args.structured_out)
        outp.parent.mkdir(parents=True, exist_ok=True)
        outp.write_text(text + "\n", encoding="utf-8")
        print(f"SCORED (structured): {outp}")
    print(text)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--target", default=None,
                    help="mapping target (defaults to the sole target if only one exists)")
    ap.add_argument("--force", action="store_true", help="overwrite an existing *_scored.yaml")
    ap.add_argument("--results", help="override path to <target>.yaml (testing)")
    ap.add_argument("--out", help="override path to <target>_scored.yaml (testing)")
    ap.add_argument("--report", help="override path to mutation_report.md (testing)")
    ap.add_argument("--manifest", help="override path to _manifest.yaml (testing)")
    ap.add_argument("--structured", metavar="PATH",
                    help="v0.3 1b: score stored structured judge-result JSON (file or directory) "
                         "against the real/mutant answer key; offline, makes no promotion decision")
    ap.add_argument("--structured-out", metavar="PATH",
                    help="optional path to write the structured-scoring JSON summary")
    ap.add_argument("--mutants-dir", help="override docs/mutants directory (testing)")
    args = ap.parse_args()

    # v0.3 1b structured-scoring path is fully separate from the legacy blinded path below.
    if args.structured:
        return run_structured(args)

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

    parse_format = parse_format_counts([rec_by_bid[bid] for bid in sorted(expected_ids)])

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
            "parse_format": parse_format,
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
    pf = mx["parse_format"]
    print(f"  parsed_clean / recovered / unrecoverable: "
          f"{pf['parsed_clean_count']} / {pf['recovered_verdict_count']} / "
          f"{pf['unrecoverable_parse_error_count']}")
    print(f"  malformed_yaml_rate:           {pf['malformed_yaml_rate']}")
    print(f"  report section updated:        {report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
