# audit-first-harness

An **audit-first Lean formalisation harness**. It keeps **source fidelity** (does the Lean statement
mean what the source claims?) separate from **formal correctness** (does the proof hold?), and makes
both auditable: theorem cards, mappings, fidelity reviews, mutation + a blinded LLM judge on the
source side; `lake build`, a no-sorry scan, a kernel/axiom audit, the Lean FRO Comparator, and a
promotion gate on the formal side. *Formal correctness ≠ source fidelity; judge metrics ≠ theorem
truth.*

## Canonical documentation

**[`PROJECT_CONTEXT.md`](PROJECT_CONTEXT.md) is the single source of truth** — architecture, current
status, the implemented pipeline, invariants, Markowitz state, roadmap, open blockers, milestone
history, and agent rules. Read it first. Agents should also read [`CLAUDE.md`](CLAUDE.md). This README
is a front door only and is **not** the detailed roadmap.

## Running the core checks

All Python checks are offline and call no model:

```bash
python scripts/validate_mapping.py                     # cards ↔ mapping ↔ reviews consistent
python scripts/validate_source_formalization.py        # source-formalisation records (structure)
python scripts/test_validate_source_formalization.py   # validator unit tests
python scripts/test_blinding_boundary.py               # judge runner/importer stay blinded
python scripts/test_source_review_decision.py          # pre-proof source-fidelity review decision
python scripts/rebuild_pipeline.py                     # run every non-gated stage, write a report
```

Lean build runs in CI (`lake build`). The real Comparator is local/WSL and human-gated (see
[`PROJECT_CONTEXT.md`](PROJECT_CONTEXT.md) §15.3 for the run procedure). The judge is contacted
**only** with the explicit opt-in `python scripts/run_judge.py --execute-api`.

## Requirements

- Lean toolchain `leanprover/lean4:v4.31.0` (via `elan`; pinned in `lean-toolchain`), Mathlib.
- Python 3.10+ with `PyYAML`. `openai` only if you use `run_judge.py --execute-api`.
- The Comparator stage needs the Comparator + `lean4export` + `landrun` binaries (Linux/WSL).
