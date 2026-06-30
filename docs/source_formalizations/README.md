# Source-formalisation records

Generic, source-agnostic infrastructure for **hard, multi-step Lean formalisation projects**.

A *source-formalisation record* documents **how an informal source claim becomes a proposed formal
target** — before any theorem card, formal mapping, fidelity review, or Lean proof exists. The hard
part of autoformalisation is not generating Lean syntax; it is the **semantic alignment** between the
informal source and the formal statement. This layer makes that alignment explicit and reviewable up
front: the symbols and their intended types, the explicit/implicit/standard assumptions (and the ones
*deliberately not* assumed), the conclusion's shape, the abstraction and representation choices, the
ambiguities and source-fidelity risks, and a proof decomposition into subtargets.

## Where it sits

```
source document / claim
  → source-formalisation record        ← this layer (docs/source_formalizations/)
  → theorem card                        (docs/theorem_index.yaml)
  → formal mapping                      (docs/formal_mapping.yaml)
  → source-fidelity review decision     (scripts/source_review_decision.py)
  → Lean proof
  → Comparator / axiom / no-sorry / promotion gate
```

It **sits before** theorem cards and formal mappings and does **not** replace them, the fidelity
reviews, or the source-fidelity review decision gate. Source interpretation, theorem-card creation,
formal mapping, and proof generation stay separate stages; this record is the first, capturing the
interpretation decisions so later stages (and a human reviewer) can audit them.

## What it is — and is not

- It is **source-fidelity infrastructure**, not a theorem oracle. It records *intent and structure*;
  it makes **no claim of mathematical truth** and does not assert the formalisation is correct — that
  is the job of the human fidelity review and the source-fidelity review gate downstream.
- It **never runs a model/API** and **never edits or reads Lean**. Linking a record to a Lean module
  happens later (in `target_links`), and the Lean linkage is checked by `validate_mapping.py`, not
  here.

## Files

- `template.yaml` — the generic skeleton. Copy it to `<source_id>.yaml` for a real record. The
  template is checked for **structure only** (placeholders allowed); real records must fill in the
  required content.
- `<source_id>.yaml` — a real record (none are committed yet; this directory currently holds only the
  template).

## Validation

`python scripts/validate_source_formalization.py` checks **completeness and structure** of every
record in this directory (and `python scripts/test_validate_source_formalization.py` unit-tests the
validator). It verifies the required top-level and nested fields, the allowed enum values
(`record_type`, `review.status`, `ambiguities[].status`, `informal_claim.theorem_role`), and — for
real records — that there is at least one symbol, one assumption, a conclusion, a formalisation
choice, an ambiguity or risk, and a proof subtarget. It deliberately does **not** check mathematical
correctness, the truth of the source, or whether the proposed formalisation is the *right* one.
`target_links` is **optional**: a pre-Lean record may **omit it entirely** (the validator no longer
requires it; if present it must still be a mapping), and it is filled only once the Lean exists.

These records **guard source fidelity, not Lean structure**: the structural fields (`target_links`'
Lean module/declaration/mapping id, and a subtarget's `depends_on` / `proposed_lean_declaration`) are
**optional** and meant to be filled only once the Lean exists — do **not** invent a Lean declaration
name, module, or dependency DAG pre-Lean. `formal_mapping.yaml` is created **after** a Lean
declaration exists (for implemented or near-implemented targets), not as pre-Lean planning; there is
**no** draft formal-mapping lifecycle.
