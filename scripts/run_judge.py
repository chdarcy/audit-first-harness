#!/usr/bin/env python3
"""One-target judge runner for the audit-first pipeline.

By default **no model is called**: --dry-run verifies/previews packages and --export-manual
writes manual request files. A real model is contacted **only** with the explicit opt-in
flag --execute-api (OpenAI provider), which reads OPENAI_API_KEY from the environment.

Answer-key separation is the whole point of this script:
  - it reads docs/judge_inputs_dryrun/_targets.yaml (membership only: blind_id -> target,
    input_sha256), NOT _manifest.yaml (the answer key with expected verdicts);
  - it sends, in a real run, only each package's `package` block to the model;
  - it never reads or records expected_verdict / class / operator.

Integrity: before any model call it re-checks prompt_sha256, mutants_sha256, and each
package's input_sha256, and re-runs the package whitelist / forbidden-token checks.

The enabled targets are the keys under `targets:` in docs/formal_mapping.yaml (no target name
is hard-coded). If --target is omitted and exactly one target exists, it is used.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
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

# Reuse the exact assembly-time constants and checks so the two scripts cannot drift.
import run_mutants as rm

ROOT = rm.ROOT
DRYRUN_DIR = rm.DRYRUN_DIR
TARGETS_FILE = DRYRUN_DIR / "_targets.yaml"
JUDGE_PROMPT = rm.JUDGE_PROMPT
MUTANTS_DIR = rm.MUTANTS_DIR
RESULTS_DIR = ROOT / "docs" / "judge_results"
REQUESTS_DIR = ROOT / "docs" / "judge_requests"

# Membership sidecar must carry nothing but these per-variant keys.
MEMBERSHIP_KEYS = {"target", "input_sha256"}

# Status banners.
STATUS_DRY = "DRY_RUN_ONLY_NO_MODEL_CALLED"
STATUS_EXPORT = "MANUAL_EXPORT_NO_MODEL_CALLED"
STATUS_API = "API_EXECUTION_COMPLETE"

# The only provider wired up for real execution.
API_PROVIDERS = {"openai"}


def fail(msg: str) -> int:
    sys.stderr.write(f"ERROR: {msg}\n")
    return 1


def check_target(target: str) -> str | None:
    """Return an error message if `target` is not an enabled mapping target, else None."""
    allowed = rm.load_allowed_targets()
    if target not in allowed:
        return (f"target {target!r} is not a target in formal_mapping.yaml; "
                f"enabled targets: {sorted(allowed)}")
    return None


def resolve_target(arg_target: str | None) -> str | None:
    """Default --target to the sole mapping target when there is exactly one."""
    if arg_target:
        return arg_target
    allowed = sorted(rm.load_allowed_targets())
    return allowed[0] if len(allowed) == 1 else None


def recompute_mutants_sha256() -> str:
    h = hashlib.sha256()
    for mf in sorted(MUTANTS_DIR.glob("*.yaml")):
        h.update(mf.name.encode("utf-8"))
        h.update(b"\0")
        h.update(mf.read_bytes())
        h.update(b"\0")
    return h.hexdigest()


def run_dry(target: str, provider: str, model: str, temperature: float, force: bool) -> int:
    err = check_target(target)
    if err:
        return fail(err)

    if not TARGETS_FILE.exists():
        return fail(
            f"{TARGETS_FILE.relative_to(ROOT)} not found; run "
            f"`python scripts/run_mutants.py --dry-run` first"
        )
    membership = yaml.safe_load(TARGETS_FILE.read_text(encoding="utf-8")) or {}
    variants = membership.get("variants") or {}

    # Defensive: the membership sidecar must not leak answer-key fields.
    for bid, entry in variants.items():
        extra = set(entry.keys()) - MEMBERSHIP_KEYS
        if extra:
            return fail(f"_targets.yaml entry {bid} has non-membership keys {sorted(extra)}")

    # Freeze the prompt + mutant set and check they match what packages were built from.
    prompt_sha256 = rm.sha256_bytes(JUDGE_PROMPT.read_bytes())
    mutants_sha256 = recompute_mutants_sha256()
    if membership.get("mutants_sha256") != mutants_sha256:
        return fail(
            "mutants_sha256 mismatch between docs/mutants and _targets.yaml; "
            "regenerate dry-run packages"
        )

    selected = sorted(bid for bid, e in variants.items() if e.get("target") == target)
    if not selected:
        return fail(f"no blind IDs for target {target}")

    checked = []
    for bid in selected:
        pkg_path = DRYRUN_DIR / f"{bid}.yaml"
        if not pkg_path.exists():
            return fail(f"package file missing for {bid}: {pkg_path.relative_to(ROOT)}")
        doc = yaml.safe_load(pkg_path.read_text(encoding="utf-8")) or {}
        meta = doc.get("meta") or {}
        pkg = doc.get("package") or {}

        # 1. whitelist + forbidden-token checks (same as assembly time)
        try:
            rm.assert_package_clean(pkg, target_name=target)
        except rm.HarnessError as exc:
            return fail(f"{bid}: package failed leak/whitelist check: {exc}")

        # 2. prompt hash must match the package's recorded one
        if meta.get("prompt_sha256") != prompt_sha256:
            return fail(f"{bid}: prompt_sha256 mismatch (judge prompt changed since build)")

        # 3. mutants hash must match
        if meta.get("mutants_sha256") != mutants_sha256:
            return fail(f"{bid}: mutants_sha256 mismatch (mutants changed since build)")

        # 4. recompute input_sha256 over the package block and cross-check 3 ways
        recomputed = rm.sha256_text(rm.canonical(pkg))
        if recomputed != meta.get("input_sha256"):
            return fail(f"{bid}: input_sha256 mismatch vs package meta")
        if recomputed != variants[bid].get("input_sha256"):
            return fail(f"{bid}: input_sha256 mismatch vs _targets.yaml")

        checked.append({"blind_id": bid, "input_sha256": recomputed})

    # Write a preview manifest — NO answer-key fields, NO model output.
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    preview_path = RESULTS_DIR / f"{target}_preview.yaml"
    if preview_path.exists() and not force:
        return fail(
            f"{preview_path.relative_to(ROOT)} exists; pass --force to overwrite"
        )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    preview = {
        "status": "DRY_RUN_ONLY_NO_MODEL_CALLED",
        "target": target,
        "provider": provider,
        "model": model,
        "temperature": temperature,
        "prompt_sha256": prompt_sha256,
        "mutants_sha256": mutants_sha256,
        "generated_utc": now,
        "note": "Preview of the packages a judge would receive. No model/API was called, "
                "and no answer-key labels are included. Real results would go in "
                f"docs/judge_results/{target}.yaml (not created here).",
        "selected": checked,
    }
    preview_path.write_text(
        yaml.safe_dump(preview, sort_keys=False, allow_unicode=True, width=100),
        encoding="utf-8",
    )

    print(f"DRY_RUN_ONLY_NO_MODEL_CALLED: verified {len(checked)} {target} package(s).")
    print(f"  provider/model: {provider} / {model} (temperature {temperature})")
    print(f"  prompt_sha256:  {prompt_sha256}")
    print(f"  mutants_sha256: {mutants_sha256}")
    print(f"  preview:        {preview_path.relative_to(ROOT)}")
    print("  No model/API was called. Real execution is opt-in via --execute-api.")
    return 0


def _request_markdown(bid: str, provenance_yaml: str, prompt_sha256: str,
                      system_prompt_text: str, input_sha256: str, canonical_pkg: str) -> str:
    """Render one manual judge-request file. The system prompt is embedded between
    plain-text markers (not a code fence) so its own ```yaml block survives verbatim;
    the user package is the exact, hashed input in a single yaml fence."""
    parts = [
        f"# Manual judge request — {bid}",
        "",
        f"status: {STATUS_EXPORT}",
        "",
        "This is a manual judge-request package. No model or API was called to create it.",
        "See `README.md` in this directory for the exact procedure.",
        "",
        "## Provenance (reference only — do NOT paste this block to the judge)",
        "",
        "```yaml",
        provenance_yaml.rstrip("\n"),
        "```",
        "",
        "## System message (paste verbatim as the judge's system prompt)",
        "",
        "Everything between the two markers below is the exact frozen system prompt "
        f"(prompt hash `{prompt_sha256}`). Paste the text between the markers, not the "
        "markers themselves.",
        "",
        "<<<BEGIN-SYSTEM-PROMPT",
        system_prompt_text.rstrip("\n"),
        "END-SYSTEM-PROMPT>>>",
        "",
        "## User message (paste verbatim as the judge's user message — strict YAML)",
        "",
        f"The YAML below is the exact input hashed as `{input_sha256}`. Paste it "
        "verbatim as the user message.",
        "",
        "```yaml",
        canonical_pkg.rstrip("\n"),
        "```",
        "",
    ]
    return "\n".join(parts)


def run_export_manual(target: str, provider: str, model: str, temperature: float) -> int:
    """Export the exact (system prompt + user package) pairs a judge would receive for
    one target, one Markdown file per blind ID, for manual use in an external model/UI.
    No model/API is called; provider/model/temperature are recorded as intended
    provenance only. Reads _targets.yaml (membership), never _manifest.yaml (answer key)."""
    err = check_target(target)
    if err:
        return fail(err)

    if not TARGETS_FILE.exists():
        return fail(
            f"{TARGETS_FILE.relative_to(ROOT)} not found; run "
            f"`python scripts/run_mutants.py --dry-run` first"
        )
    membership = yaml.safe_load(TARGETS_FILE.read_text(encoding="utf-8")) or {}
    variants = membership.get("variants") or {}
    for bid, entry in variants.items():
        extra = set(entry.keys()) - MEMBERSHIP_KEYS
        if extra:
            return fail(f"_targets.yaml entry {bid} has non-membership keys {sorted(extra)}")

    prompt_sha256 = rm.sha256_bytes(JUDGE_PROMPT.read_bytes())
    mutants_sha256 = recompute_mutants_sha256()
    if membership.get("mutants_sha256") != mutants_sha256:
        return fail(
            "mutants_sha256 mismatch between docs/mutants and _targets.yaml; "
            "regenerate dry-run packages"
        )

    selected = sorted(bid for bid, e in variants.items() if e.get("target") == target)
    if not selected:
        return fail(f"no blind IDs for target {target}")

    system_prompt_text = JUDGE_PROMPT.read_text(encoding="utf-8")
    out_dir = REQUESTS_DIR / target
    out_dir.mkdir(parents=True, exist_ok=True)

    written = []
    for bid in selected:
        pkg_path = DRYRUN_DIR / f"{bid}.yaml"
        if not pkg_path.exists():
            return fail(f"package file missing for {bid}: {pkg_path.relative_to(ROOT)}")
        doc = yaml.safe_load(pkg_path.read_text(encoding="utf-8")) or {}
        meta = doc.get("meta") or {}
        pkg = doc.get("package") or {}

        # Same integrity + leak checks as the dry-run path.
        try:
            rm.assert_package_clean(pkg, target_name=target)
        except rm.HarnessError as exc:
            return fail(f"{bid}: package failed leak/whitelist check: {exc}")
        if meta.get("prompt_sha256") != prompt_sha256:
            return fail(f"{bid}: prompt_sha256 mismatch (judge prompt changed since build)")
        if meta.get("mutants_sha256") != mutants_sha256:
            return fail(f"{bid}: mutants_sha256 mismatch (mutants changed since build)")
        canonical_pkg = rm.canonical(pkg)
        recomputed = rm.sha256_text(canonical_pkg)
        if recomputed != meta.get("input_sha256"):
            return fail(f"{bid}: input_sha256 mismatch vs package meta")
        if recomputed != variants[bid].get("input_sha256"):
            return fail(f"{bid}: input_sha256 mismatch vs _targets.yaml")

        # Provenance carries ONLY whitelisted/provenance fields — no answer-key labels.
        provenance = {
            "status": STATUS_EXPORT,
            "blind_id": bid,
            "provider": provider,
            "model": model,
            "temperature": temperature,
            "prompt_sha256": prompt_sha256,
            "input_sha256": recomputed,
            "mutants_sha256": mutants_sha256,
        }
        prov_yaml = yaml.safe_dump(provenance, sort_keys=False, allow_unicode=True, width=100)
        md = _request_markdown(bid, prov_yaml, prompt_sha256, system_prompt_text,
                               recomputed, canonical_pkg)
        (out_dir / f"{bid}.md").write_text(md, encoding="utf-8")
        written.append(bid)

    print(f"{STATUS_EXPORT}: wrote {len(written)} request file(s) to {out_dir.relative_to(ROOT)}")
    print(f"  provider/model: {provider} / {model} (temperature {temperature}) [provenance only]")
    print(f"  prompt_sha256:  {prompt_sha256}")
    print(f"  mutants_sha256: {mutants_sha256}")
    print(f"  blind IDs:      {', '.join(written)}")
    print("  No model/API was called. Paste each request into the chosen judge, then save the")
    print(f"  strict-YAML reply under docs/judge_responses_manual/{target}/<blind_id>.yaml.")
    return 0


def _yaml_candidates(text: str):
    """Yield progressively-cleaned variants of a model response to try as strict YAML.

    Handles strict YAML, a full ```yaml ... ``` fenced block, and a stray leading
    language tag / opening fence on its own line (e.g. a bare 'yaml' line, which some
    models emit) with an optional trailing fence."""
    yield text
    s = text.strip()
    # A fenced code block anywhere: ```yaml ... ``` (language tag optional).
    m = re.search(r"```[ \t]*[A-Za-z0-9_-]*[ \t]*\r?\n(.*?)\r?\n?```", s, re.DOTALL)
    if m:
        yield m.group(1)
    # A leading bare language tag / opening fence on its own line (no closing fence),
    # e.g. "```yaml", "yaml", or "yml": drop it plus any trailing blank/fence lines.
    lines = s.splitlines()
    if lines:
        first = lines[0].strip().strip("`").strip().lower()
        if first in ("yaml", "yml", ""):
            rest = lines[1:]
            while rest and rest[-1].strip().strip("`") == "":
                rest.pop()
            yield "\n".join(rest)


def _parse_judge_yaml(text: str):
    """Return (parsed_mapping_or_None, parse_error_or_None)."""
    if not isinstance(text, str) or not text.strip():
        return None, "empty model response"
    err = "no parseable YAML mapping found"
    for cand in _yaml_candidates(text):
        if not cand or not cand.strip():
            continue
        try:
            obj = yaml.safe_load(cand)
        except yaml.YAMLError as exc:
            err = f"YAML parse error: {exc}"
            continue
        if isinstance(obj, dict):
            return obj, None
        err = f"parsed YAML is {type(obj).__name__}, expected a mapping"
    return None, err


# The judge verdict is a closed enum (kept in sync with score_judge.ALL_VERDICTS). Longest
# alternatives first so PASS does not shadow PASS_EQUIV / PASS_PROVABLE_EQUIV.
_JUDGE_VERDICTS = ("PASS_PROVABLE_EQUIV", "PASS_EQUIV", "PASS", "WARN", "FAIL", "OUT_OF_SCOPE")
_VERDICT_LINE_RE = re.compile(
    r"(?m)^[ \t]*verdict[ \t]*:[ \t]*[\"']?(" + "|".join(_JUDGE_VERDICTS) + r")[\"']?[ \t]*$"
)


def _recover_verdict(text):
    """Best-effort recovery of the verdict when the full YAML will not parse (e.g. a model
    emits an unquoted ': ' inside a free-text field, which breaks the document but leaves the
    top-level `verdict:` enum line intact). Returns the verdict string only if exactly one
    distinct enum value is present on its own line; otherwise None. Callers always retain the
    original raw_output and parse_error, and flag the record with recovered_verdict, so the
    salvage is fully auditable and never masks a genuinely verdict-less response."""
    if not isinstance(text, str):
        return None
    distinct = set(_VERDICT_LINE_RE.findall(text))
    if len(distinct) == 1:
        return next(iter(distinct))
    return None


def _judge_fields(raw_output):
    """Return (judge_output, judge_verdict, parse_error, recovered_verdict) for one response.
    On a clean parse: judge_output is the mapping, recovered_verdict is False. If the YAML will
    not parse but a single unambiguous `verdict:` line is present, judge_verdict is that
    recovered value, parse_error is retained, and recovered_verdict is True."""
    parsed, parse_error = _parse_judge_yaml(raw_output or "")
    if parse_error is None:
        verdict = parsed.get("verdict") if isinstance(parsed, dict) else None
        return parsed, verdict, parse_error, False
    recovered = _recover_verdict(raw_output or "")
    return None, recovered, parse_error, recovered is not None


def run_reparse(target: str) -> int:
    """Re-extract verdicts from raw_output already saved in docs/judge_results/<target>.yaml.
    Calls no API and changes no raw_output; only re-runs the YAML parser to (re)populate
    judge_verdict / judge_output / parse_error per record. Lets us recover from a parser
    bug without re-spending API calls."""
    err = check_target(target)
    if err:
        return fail(err)
    path = RESULTS_DIR / f"{target}.yaml"
    if not path.exists():
        return fail(f"{path.relative_to(ROOT)} not found; run --execute-api first")
    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    records = doc.get("results") or []
    if not records:
        return fail(f"{path.relative_to(ROOT)} has no results to reparse")
    n_ok = n_recovered = n_err = 0
    for rec in records:
        parsed, verdict, perr, recovered = _judge_fields(rec.get("raw_output") or "")
        rec["judge_output"] = parsed
        rec["judge_verdict"] = verdict
        rec["parse_error"] = perr
        rec["recovered_verdict"] = recovered
        bid = rec.get("blind_id")
        if perr and verdict is None:
            n_err += 1
            print(f"  {bid}: PARSE_ERROR ({perr})")
        elif recovered:
            n_recovered += 1
            print(f"  {bid}: {verdict} (verdict recovered from malformed YAML; parse_error retained)")
        else:
            n_ok += 1
            print(f"  {bid}: {verdict}")
    path.write_text(
        yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=100), encoding="utf-8"
    )
    print(f"REPARSE_COMPLETE: updated {len(records)} record(s) in {path.relative_to(ROOT)}")
    print(f"  parsed OK: {n_ok}, recovered: {n_recovered}, unrecoverable parse errors: {n_err}")
    if n_err == 0:
        print(f"  Next: python scripts/score_judge.py --target {target}")
    return 0


def _call_openai(client, model: str, system_text: str, user_text: str, temperature) -> str:
    """One judge call via the OpenAI Responses API. store=False so the prompt/package are
    not retained server-side. A temperature of None omits the parameter entirely (some
    reasoning models reject it). Returns the model's text output."""
    kwargs = dict(model=model, instructions=system_text, input=user_text, store=False)
    if temperature is not None:
        kwargs["temperature"] = temperature
    resp = client.responses.create(**kwargs)
    return resp.output_text


def run_execute_api(target: str, provider: str, model: str, temperature: float, force: bool,
                    omit_temperature: bool = False) -> int:
    """OPT-IN real execution. Calls the judge model once per blind ID for one target and
    writes docs/judge_results/<target>.yaml. Reads _targets.yaml (membership) only, never
    _manifest.yaml (the answer key). The API key comes from OPENAI_API_KEY in the env.
    With omit_temperature, the temperature parameter is not sent (for models that reject it)."""
    eff_temperature = None if omit_temperature else temperature
    err = check_target(target)
    if err:
        return fail(err)
    if provider not in API_PROVIDERS:
        return fail(f"provider {provider!r} is not supported; only {sorted(API_PROVIDERS)}")

    if not TARGETS_FILE.exists():
        return fail(
            f"{TARGETS_FILE.relative_to(ROOT)} not found; run "
            f"`python scripts/run_mutants.py --dry-run` first"
        )
    membership = yaml.safe_load(TARGETS_FILE.read_text(encoding="utf-8")) or {}
    variants = membership.get("variants") or {}
    for bid, entry in variants.items():
        extra = set(entry.keys()) - MEMBERSHIP_KEYS
        if extra:
            return fail(f"_targets.yaml entry {bid} has non-membership keys {sorted(extra)}")

    prompt_sha256 = rm.sha256_bytes(JUDGE_PROMPT.read_bytes())
    mutants_sha256 = recompute_mutants_sha256()
    if membership.get("mutants_sha256") != mutants_sha256:
        return fail(
            "mutants_sha256 mismatch between docs/mutants and _targets.yaml; "
            "regenerate dry-run packages"
        )

    selected = sorted(bid for bid, e in variants.items() if e.get("target") == target)
    if not selected:
        return fail(f"no blind IDs for target {target}")

    out_path = RESULTS_DIR / f"{target}.yaml"
    if out_path.exists() and not force:
        return fail(f"{out_path.relative_to(ROOT)} exists; pass --force to overwrite")

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return fail("OPENAI_API_KEY is not set in the environment; export it before --execute-api")

    try:
        from openai import OpenAI
    except ModuleNotFoundError:
        return fail("the 'openai' package is required for --execute-api (python -m pip install openai)")
    client = OpenAI(api_key=api_key)

    system_text = JUDGE_PROMPT.read_text(encoding="utf-8")

    results = []
    n_ok = n_recovered = n_parse_err = 0
    for bid in selected:
        pkg_path = DRYRUN_DIR / f"{bid}.yaml"
        if not pkg_path.exists():
            return fail(f"package file missing for {bid}: {pkg_path.relative_to(ROOT)}")
        doc = yaml.safe_load(pkg_path.read_text(encoding="utf-8")) or {}
        meta = doc.get("meta") or {}
        pkg = doc.get("package") or {}

        # Re-verify integrity + leak checks immediately before the call.
        try:
            rm.assert_package_clean(pkg, target_name=target)
        except rm.HarnessError as exc:
            return fail(f"{bid}: package failed leak/whitelist check: {exc}")
        if meta.get("prompt_sha256") != prompt_sha256:
            return fail(f"{bid}: prompt_sha256 mismatch (judge prompt changed since build)")
        if meta.get("mutants_sha256") != mutants_sha256:
            return fail(f"{bid}: mutants_sha256 mismatch (mutants changed since build)")
        canonical_pkg = rm.canonical(pkg)
        input_sha256 = rm.sha256_text(canonical_pkg)
        if input_sha256 != meta.get("input_sha256"):
            return fail(f"{bid}: input_sha256 mismatch vs package meta")
        if input_sha256 != variants[bid].get("input_sha256"):
            return fail(f"{bid}: input_sha256 mismatch vs _targets.yaml")

        ran_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        try:
            raw_output = _call_openai(client, model, system_text, canonical_pkg, eff_temperature)
        except Exception as exc:  # network/API errors must not lose prior results
            return fail(
                f"{bid}: API call failed ({type(exc).__name__}: {exc}); "
                f"no results written. Re-run after resolving the error."
            )

        parsed, judge_verdict, parse_error, recovered = _judge_fields(raw_output)
        if parse_error and judge_verdict is None:
            n_parse_err += 1
            print(f"  {bid}: PARSE_ERROR ({parse_error})")
        elif recovered:
            n_recovered += 1
            print(f"  {bid}: {judge_verdict} (verdict recovered from malformed YAML; parse_error retained)")
        else:
            n_ok += 1
            print(f"  {bid}: {judge_verdict}")

        results.append({
            "blind_id": bid,
            "input_sha256": input_sha256,
            "judge_verdict": judge_verdict,
            "judge_output": parsed,
            "raw_output": raw_output,
            "parse_error": parse_error,
            "recovered_verdict": recovered,
            "provenance": {
                "provider": provider,
                "model": model,
                "temperature": eff_temperature,
                "prompt_sha256": prompt_sha256,
                "input_sha256": input_sha256,
                "mutants_sha256": mutants_sha256,
                "ran_utc": ran_utc,
                "de_anchored": True,
                "mode": "api",
            },
        })

    out_doc = {
        "status": STATUS_API,
        "target": target,
        "mode": "api",
        "de_anchored": True,
        "provider": provider,
        "model": model,
        "temperature": eff_temperature,
        "prompt_sha256": prompt_sha256,
        "mutants_sha256": mutants_sha256,
        "ran_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "results": results,
    }
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        yaml.safe_dump(out_doc, sort_keys=False, allow_unicode=True, width=100), encoding="utf-8"
    )
    print(f"{STATUS_API}: wrote {len(results)} record(s) to {out_path.relative_to(ROOT)}")
    print(f"  provider/model: {provider} / {model} (temperature {temperature})")
    print(f"  parsed OK: {n_ok}, recovered: {n_recovered}, unrecoverable parse errors: {n_parse_err}")
    print(f"  Next: python scripts/score_judge.py --target {target}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--target", default=None,
                    help="mapping target (defaults to the sole target if only one exists)")
    ap.add_argument("--provider", help="required for --dry-run/--export-manual/--execute-api")
    ap.add_argument("--model", help="required for --dry-run/--export-manual/--execute-api")
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--dry-run", action="store_true",
                    help="prepare and verify packages, then write a preview manifest")
    ap.add_argument("--export-manual", action="store_true",
                    help="write one manual judge-request file per blind ID (no model called)")
    ap.add_argument("--execute-api", action="store_true",
                    help="OPT-IN: actually call the judge model via the API (OPENAI_API_KEY)")
    ap.add_argument("--force", action="store_true",
                    help="overwrite an existing preview/results file")
    ap.add_argument("--omit-temperature", action="store_true",
                    help="do not send the temperature parameter (for models that reject it, e.g. o3)")
    ap.add_argument("--reparse", action="store_true",
                    help="re-extract verdicts from already-saved raw_output (no API call)")
    args = ap.parse_args()

    target = resolve_target(args.target)
    if not target:
        sys.stderr.write(
            "ERROR: --target is required (more than one target in formal_mapping.yaml).\n"
        )
        return 2

    if args.reparse:
        return run_reparse(target)

    if (args.execute_api or args.export_manual or args.dry_run) and not (args.provider and args.model):
        sys.stderr.write("ERROR: --provider and --model are required for this mode.\n")
        return 2

    if args.execute_api:
        return run_execute_api(target, args.provider, args.model, args.temperature,
                               args.force, args.omit_temperature)

    if args.export_manual:
        return run_export_manual(target, args.provider, args.model, args.temperature)

    if args.dry_run:
        return run_dry(target, args.provider, args.model, args.temperature, args.force)

    sys.stderr.write(
        "ERROR: no execution mode selected. Re-run with --dry-run, --export-manual, "
        "or --execute-api.\n"
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
