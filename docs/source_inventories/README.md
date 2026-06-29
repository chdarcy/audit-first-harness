# Source theorem inventories

Content-bearing **source-intake** artifacts. A *source theorem inventory* is the first reading pass
over a real source document: it enumerates the candidate results to formalise, classifies their
dependencies, difficulty, and risks, marks what to defer, and recommends a formalisation order.

## What an inventory is — and is not

- It **is** a source-reading artifact. Inventories are allowed to be **source-specific** (they name
  the actual theorems/objects of the source), unlike the generic, source-agnostic
  `docs/source_formalizations/` layer.
- It is **not** a proof, a theorem card, a formal mapping, or a verification. **Nothing in an
  inventory is mathematically verified**; an entry recording a result does not assert it is true,
  proved, or correctly formalised. It records *what is in the source* and *how hard / risky* a
  faithful formalisation looks.
- Creating an inventory makes **no Lean**, no theorem cards, no mappings, no mutants, and calls **no
  model/API**.

## Where it sits

```
source document
  → source theorem inventory        ← this directory (intake / triage)
  → (per-target) source-formalisation record   (docs/source_formalizations/)
  → theorem card (docs/theorem_index.yaml)
  → formal mapping (docs/formal_mapping.yaml)
  → source-fidelity review decision (scripts/source_review_decision.py)
  → Lean proof → Comparator / axiom / no-sorry / promotion gate
```

An inventory **precedes** the per-target source-formalisation records: it decides *which* targets are
worth turning into records and proofs, and in what order. Promoting any inventory entry into a real
target (card / mapping / Lean) is a separate, explicitly-approved step.

## Schema

Each inventory is a YAML file `<source_id>.yaml` with `record_type: source_theorem_inventory`
(`schema_version 0.1.0`): a `source` block, a `global_context` (domain, main objects, standing
assumptions, notation), a list of `candidate_targets` (each with role, informal statement,
dependencies, likely formalisation level, difficulty, **source-fidelity risks** and **proof risks**
recorded separately, and a recommended status), a `recommended_sequence`, an
`out_of_scope_for_first_pass` list, and `audit` metadata (`content_bearing: true`).

These files are **not** validated by `scripts/validate_source_formalization.py` (which validates only
the generic `record_type: source_formalization`); they are intentionally kept in a separate directory
so the generic source-formalisation infrastructure stays source-agnostic.
