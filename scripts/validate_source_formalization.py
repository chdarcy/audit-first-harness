#!/usr/bin/env python3
"""Structural validator for generic source-formalisation records.

A *source-formalisation record* documents how an informal source claim becomes a proposed formal
target — its symbols, assumptions, conclusion shape, abstraction choices, ambiguities, and proof
decomposition — **before** any theorem card, formal mapping, fidelity review, or Lean proof exists.
It sits at the front of the pipeline:

    source document / claim
      -> source-formalisation record   (this layer)
      -> theorem card (docs/theorem_index.yaml)
      -> formal mapping (docs/formal_mapping.yaml)
      -> source-fidelity review decision (scripts/source_review_decision.py)
      -> Lean proof
      -> Comparator / axiom / no-sorry / promotion gate

This validator checks **completeness and structure only** — never mathematical truth, never the
source's correctness, and never whether the proposed formalisation is *right* (that is the job of the
human fidelity review and the source-fidelity review gate downstream). It is generic, source-
agnostic infrastructure: it does not read, import, or encode any external source content; it does not
call a model/API; and it does not edit or read Lean. Records live under
`docs/source_formalizations/`; `template.yaml` is a placeholder skeleton (checked structurally, not
for content), and every other `*.yaml` is treated as a real record and held to the full checks.

Exit code 0 if there are no errors, 1 otherwise. Warnings do not fail the run.
"""
from __future__ import annotations

import sys
from pathlib import Path

try:
    import yaml
except ModuleNotFoundError:
    sys.stderr.write("ERROR: PyYAML is required. Install it with: python -m pip install pyyaml\n")
    sys.exit(2)

ROOT = Path(__file__).resolve().parent.parent
RECORDS_DIR = ROOT / "docs" / "source_formalizations"
TEMPLATE_NAME = "template.yaml"

SCHEMA_VERSION = "0.1.0"
RECORD_TYPE = "source_formalization"

# Enumerations.
AMBIGUITY_STATUS = {"unresolved", "resolved", "needs_human_review"}
REVIEW_STATUS = {"draft", "ready_for_card", "needs_human_review", "approved"}
THEOREM_ROLE = {"setup", "lemma", "theorem", "corollary", "definition", "example"}
# `source_kind` is open-ended; these are the suggested values (a non-listed kind is a warning).
KNOWN_SOURCE_KINDS = {"paper", "lecture_notes", "textbook", "note", "problem_sheet"}

# Required top-level keys (must be present on every record, including the template skeleton).
TOP_LEVEL = [
    "schema_version", "record_type", "source", "informal_claim", "symbols", "assumptions",
    "conclusion", "formalization_choices", "ambiguities", "proof_decomposition", "target_links",
    "review", "audit",
]


def _nonempty(value) -> bool:
    """True if a scalar/collection carries real content (not None / "" / blank / empty list/dict)."""
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() != ""
    if isinstance(value, (list, dict)):
        return len(value) > 0
    return True


def _any_listed(d: dict, keys) -> bool:
    """True if any of `keys` in dict `d` maps to a non-empty list containing a non-empty entry."""
    for k in keys:
        v = d.get(k)
        if isinstance(v, list) and any(_nonempty(x) for x in v):
            return True
    return False


def validate_record(doc, label: str, *, real: bool):
    """Validate one record's structure. `real=False` is the placeholder template: keys must be
    present and any *filled-in* enum must be valid, but blank placeholder content is allowed.
    Returns (errors, warnings) as lists of human-readable strings prefixed with `label`."""
    errors: list[str] = []
    warnings: list[str] = []

    def err(msg: str) -> None:
        errors.append(f"{label}: {msg}")

    def warn(msg: str) -> None:
        warnings.append(f"{label}: {msg}")

    if not isinstance(doc, dict):
        return [f"{label}: top-level YAML is not a mapping"], warnings

    # 1. all top-level keys present
    for key in TOP_LEVEL:
        if key not in doc:
            err(f"missing required top-level field '{key}'")

    # 2. record_type / schema_version
    if doc.get("record_type") != RECORD_TYPE:
        err(f"record_type must be '{RECORD_TYPE}', got {doc.get('record_type')!r}")
    if real and not _nonempty(doc.get("schema_version")):
        err("schema_version must be a non-empty string")

    # 3. enum fields are validated whenever non-blank (template included)
    role = (doc.get("informal_claim") or {}).get("theorem_role") if isinstance(doc.get("informal_claim"), dict) else None
    if _nonempty(role) and role not in THEOREM_ROLE:
        err(f"informal_claim.theorem_role '{role}' not in {sorted(THEOREM_ROLE)}")
    rev_status = (doc.get("review") or {}).get("status") if isinstance(doc.get("review"), dict) else None
    if _nonempty(rev_status) and rev_status not in REVIEW_STATUS:
        err(f"review.status '{rev_status}' not in {sorted(REVIEW_STATUS)}")
    ambiguities = doc.get("ambiguities")
    if isinstance(ambiguities, list):
        for i, a in enumerate(ambiguities):
            if isinstance(a, dict) and _nonempty(a.get("status")) and a.get("status") not in AMBIGUITY_STATUS:
                err(f"ambiguities[{i}].status '{a.get('status')}' not in {sorted(AMBIGUITY_STATUS)}")
    src = doc.get("source")
    if isinstance(src, dict) and _nonempty(src.get("source_kind")) and src.get("source_kind") not in KNOWN_SOURCE_KINDS:
        warn(f"source.source_kind '{src.get('source_kind')}' is not one of the suggested kinds {sorted(KNOWN_SOURCE_KINDS)}")

    # The template skeleton stops here: structure + enum-shape only, no content requirements.
    if not real:
        return errors, warnings

    # 4. source metadata (real records)
    if not isinstance(src, dict):
        err("source must be a mapping")
    else:
        if not _nonempty(src.get("source_id")):
            err("source.source_id is required (a stable identifier for the source)")
        if not _nonempty(src.get("source_kind")):
            err("source.source_kind is required (e.g. paper, lecture_notes, textbook, note)")

    # 5. informal claim
    ic = doc.get("informal_claim")
    if not isinstance(ic, dict):
        err("informal_claim must be a mapping")
    else:
        if not _nonempty(ic.get("statement")):
            err("informal_claim.statement is required")
        if not _nonempty(ic.get("theorem_role")):
            err("informal_claim.theorem_role is required")

    # 6. symbols — at least one with a source_symbol
    symbols = doc.get("symbols")
    if not isinstance(symbols, list) or not symbols:
        err("symbols must be a non-empty list (at least one symbol)")
    elif not any(isinstance(s, dict) and _nonempty(s.get("source_symbol")) for s in symbols):
        err("at least one symbol must have a non-empty 'source_symbol'")

    # 7. assumptions — at least one explicit/implicit/derived assumption
    assumptions = doc.get("assumptions")
    if not isinstance(assumptions, dict):
        err("assumptions must be a mapping")
    elif not _any_listed(assumptions, ("explicit", "implicit", "derived_or_standard")):
        err("assumptions must list at least one explicit, implicit, or derived_or_standard assumption")

    # 8. conclusion
    conclusion = doc.get("conclusion")
    if not isinstance(conclusion, dict):
        err("conclusion must be a mapping")
    elif not _nonempty(conclusion.get("informal")):
        err("conclusion.informal is required")

    # 9. formalization choices — at least one abstraction level or representation choice
    fc = doc.get("formalization_choices")
    if not isinstance(fc, dict):
        err("formalization_choices must be a mapping")
    elif not (_nonempty(fc.get("abstraction_level")) or _any_listed(fc, ("representation_choices",))):
        err("formalization_choices must record an abstraction_level or at least one representation_choice")

    # 10. ambiguities / risks — at least one documented ambiguity OR source-fidelity risk
    audit = doc.get("audit") if isinstance(doc.get("audit"), dict) else {}
    has_ambiguity = isinstance(ambiguities, list) and any(
        isinstance(a, dict) and _nonempty(a.get("issue")) for a in ambiguities)
    has_risk = _any_listed(audit, ("source_fidelity_risks",))
    if not (has_ambiguity or has_risk):
        err("at least one ambiguity (with an 'issue') or one audit.source_fidelity_risks entry is required")

    # 11. proof decomposition — a strategy and at least one well-formed subtarget
    pd = doc.get("proof_decomposition")
    if not isinstance(pd, dict):
        err("proof_decomposition must be a mapping")
    else:
        if not _nonempty(pd.get("strategy")):
            err("proof_decomposition.strategy is required")
        subs = pd.get("subtargets")
        if not isinstance(subs, list) or not subs:
            err("proof_decomposition.subtargets must be a non-empty list")
        elif not any(isinstance(s, dict) and _nonempty(s.get("id")) and _nonempty(s.get("informal_goal")) for s in subs):
            err("at least one proof subtarget must have an 'id' and an 'informal_goal'")

    # 12. target_links — present as a mapping, but may be blank during early stages
    if not isinstance(doc.get("target_links"), dict):
        err("target_links must be a mapping (it may be left blank during the early source-formalisation stage)")

    # 13. review block — must carry a status
    rev = doc.get("review")
    if not isinstance(rev, dict):
        err("review must be a mapping")
    elif not _nonempty(rev.get("status")):
        err("review.status is required (draft, ready_for_card, needs_human_review, approved)")

    return errors, warnings


def validate_dir(directory: Path):
    """Validate every record under `directory`. Returns (errors, warnings, n_real, n_template)."""
    errors: list[str] = []
    warnings: list[str] = []
    if not directory.exists():
        warnings.append(f"{directory}: directory does not exist (nothing to validate)")
        return errors, warnings, 0, 0

    n_real = 0
    n_template = 0
    for path in sorted(directory.glob("*.yaml")):
        label = path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else path.as_posix()
        try:
            doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            errors.append(f"{label}: YAML parse error: {exc}")
            continue
        is_template = path.name == TEMPLATE_NAME
        e, w = validate_record(doc, label, real=not is_template)
        errors.extend(e)
        warnings.extend(w)
        if is_template:
            n_template += 1
        else:
            n_real += 1
    return errors, warnings, n_real, n_template


def main() -> int:
    directory = RECORDS_DIR
    if len(sys.argv) > 1:
        directory = Path(sys.argv[1])
    errors, warnings, n_real, n_template = validate_dir(directory)
    for w in warnings:
        print(f"WARN: {w}")
    for e in errors:
        print(f"ERROR: {e}")
    where = directory.relative_to(ROOT).as_posix() if directory.is_relative_to(ROOT) else str(directory)
    if errors:
        print(f"\nFAIL: {len(errors)} error(s) in {where} "
              f"({n_real} real record(s), {n_template} template).")
        return 1
    print(f"\nPASS: {where} structurally consistent "
          f"({n_real} real record(s), {n_template} template; {len(warnings)} warning(s)).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
