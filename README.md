# audit-first-harness

An **audit-first Lean formalisation harness**. It keeps two things separate and makes both auditable:

- **source fidelity** — does the Lean *statement* actually mean what the source claims? (theorem
  cards, mappings, fidelity reviews, mutation + a blinded LLM judge, calibration, a pre-proof
  source-fidelity review gate); and
- **formal correctness** — does the proof actually hold? (`lake build`, a no-sorry scan, a
  kernel/axiom audit, the Lean FRO Comparator's Challenge/Solution equality, and a promotion gate).

These are never conflated: *formal correctness ≠ source fidelity*, and *judge metrics ≠ theorem
truth*. The judge is a calibrated source-fidelity reviewer, **not** a theorem oracle.

For the stable design and boundaries see [`ARCHITECTURE.md`](ARCHITECTURE.md); for active next steps
see [`docs/ROADMAP.md`](docs/ROADMAP.md); for the dated build history see
[`docs/MILESTONES.md`](docs/MILESTONES.md).

## Current status

- **Harness implemented and exercised** on three worked targets — `PutCallParity`,
  `TwoAssetMinVar`, `GoldIrrationalSqrtTwo` (each: built, no-sorry, axiom-audited, real Comparator
  pass recorded, human-approved).
- **Judge calibrated** on those targets (gpt-4o, opt-in): aggregate discriminative recall 0.875,
  false-alarm rate 0.0 — strong but imperfect; see [`docs/JUDGE_EVIDENCE_SUMMARY.md`](docs/JUDGE_EVIDENCE_SUMMARY.md).
- **Generic source-formalisation records** implemented (`docs/source_formalizations/`).
- **First content-bearing source intake done for Markowitz.** It is at the **inventory stage only**:
  a committed source + a candidate-target triage. **No theorem card, formal mapping, Lean proof,
  mutant, or Comparator artifact exists for Markowitz yet, and nothing in the inventory is proved,
  mapped, or verified.**
- **Not** a fully agentic system: the closed-loop controller that would let judge output drive
  statement revision and proof attempts is future research.

## Pipeline

```text
source document
  → source theorem inventory        (docs/source_inventories/ — triage a whole source)
  → per-target source-formalisation record  (docs/source_formalizations/ — one candidate's semantic alignment)
  → theorem card                    (docs/theorem_index.yaml — source-side ledger entry)
  → formal mapping                  (docs/formal_mapping.yaml — source↔Lean bridge + gate/audit state)
  → source-fidelity review / judge evidence   (fidelity_reviews + mutants + blinded judge + source-review gate)
  → Lean proof
  → lake build → no-sorry → axiom audit
  → Comparator (Challenge vs Solution equality)
  → promotion gate
```

The four ledger layers, distinguished:

- **`docs/source_inventories/`** — source-level **triage**, *content-bearing* and *source-specific*:
  one YAML per source listing candidate targets, dependencies, difficulty, and risks, with a
  recommended order. Nothing here is verified.
- **`docs/source_formalizations/`** — per-target **semantic-alignment records** (*generic,
  source-agnostic infrastructure*): how one informal claim becomes a proposed formal target
  (symbols, assumptions, conclusion shape, abstraction choices, ambiguities, proof decomposition).
- **`docs/theorem_index.yaml`** — the **theorem-card ledger** (the source claim, source side only).
- **`docs/formal_mapping.yaml`** — the **source-to-Lean mapping** and its lifecycle/audit state
  (lean declaration, Comparator triple, verdict, `comparator_status`, human approval).

## Markowitz source intake

- **Source:** [`examples/markowitz_lecture_notes/source.tex`](examples/markowitz_lecture_notes/source.tex).
- **Inventory:** [`docs/source_inventories/markowitz_lecture_notes.yaml`](docs/source_inventories/markowitz_lecture_notes.yaml)
  — **12 candidate targets** with separated source-fidelity vs proof risks.
- **Recommended first formal path:** `MK-000` (algebraic scaffolding) then `MK-003`
  (the `D = BC − A² > 0` Cauchy–Schwarz lemma).
- **Deferred:** the probabilistic foundations (L² returns, Cov→PSD bridge) and the CAPM result
  (relies on unstated equilibrium economics). The central recorded decision is the
  probabilistic↔algebraic **abstraction boundary**.
- **No Lean, theorem card, formal mapping, proof, mutant, or Comparator artifact yet.** The next
  proof-facing step is to promote `MK-000` and `MK-003` into per-target source-formalisation records
  (see [`docs/ROADMAP.md`](docs/ROADMAP.md)).

## Running the core checks

All Python checks are offline and call no model:

```bash
python scripts/validate_mapping.py                     # cards ↔ mapping ↔ reviews consistent
python scripts/validate_source_formalization.py        # generic source-formalisation records (structure)
python scripts/test_validate_source_formalization.py   # validator unit tests
python scripts/test_blinding_boundary.py               # judge runner/importer stay blinded
python scripts/test_source_review_decision.py          # pre-proof source-fidelity review decision
python scripts/rebuild_pipeline.py                     # run every non-gated stage, write a report
```

- **Lean build** (`lake build`) is run in CI for all theorem modules and Challenge/Solution triples.
- The **real Comparator** (landrun sandbox + binaries) is **local/WSL and human-gated — not run in
  CI**; CI proves the triples *build*, which is formal evidence only, not source fidelity. See
  [`docs/COMPARATOR.md`](docs/COMPARATOR.md).
- The **judge** is contacted **only** with the explicit opt-in `python scripts/run_judge.py
  --execute-api` (OpenAI; reads `OPENAI_API_KEY` from the environment).

## Adding a new source / target

1. **Add the source** under `examples/<source_id>/source.tex`.
2. **Triage it:** create `docs/source_inventories/<source_id>.yaml` (candidate targets, risks,
   recommended order) — a source-reading artifact, nothing verified.
3. **Promote one candidate** into a per-target record `docs/source_formalizations/<target_id>.yaml`
   (validated by `validate_source_formalization.py`).
4. **Only then** create the theorem card (`docs/theorem_index.yaml`), the formal mapping
   (`docs/formal_mapping.yaml`), the Lean proof (`AuditHarness/<Target>.lean` + a `Helpers.lean`
   proof module, per [`CLAUDE.md`](CLAUDE.md) §5.1 — never weakening the statement), the fidelity
   review, mutants, and the Comparator `Audit/<Target>/` triple. `run_mutants.py` refuses to
   assemble judge packages until the human-approval gate is satisfied.

## What this repo does **not** claim

- ❌ Not automatic theorem extraction — a human transcribes the source claim; no LaTeX auto-parsing.
- ❌ Not automatic proof generation — proofs are written by a human/model agent and **checked by
  Lean** (and optionally the Comparator).
- ❌ The judge is **not** a theorem oracle — its metrics measure judge reliability, not truth, and a
  judge PASS never overrides a formal failure.
- ❌ An inventory (or a source-formalisation record) is **not** verification — it records intent and
  structure, not correctness.
- ❌ The Comparator checks **Challenge vs Solution** statement equality, **not** source-`.tex` vs Lean
  fidelity.

## Scripts

| Script | What it does | Calls a model? |
|---|---|---|
| `run_mutants.py --dry-run` | Assemble blinded judge packages + answer key from the ledger | No |
| `run_judge.py` | `--dry-run` / `--export-manual` / **`--execute-api`** (opt-in) judge runner | Only with `--execute-api` |
| `import_manual_judge_results.py` | Aggregate manually-collected judge replies, with provenance | No |
| `score_judge.py` | Score judge results vs the local answer key; write metrics (incl. `--structured` JSON reliability scoring) | No |
| `export_structured_judge_results.py` | Convert blinded judge results into structured v0.3 JSON records (un-blinds via the answer key) | No |
| `run_structured_judge_workflow.py` | Offline chain export → validate → score → (optional) gate over existing judge results | No |
| `validate_source_formalization.py` | Structural validation of generic source-formalisation records (informal source → proposed formal target; pre-card) | No |
| `validate_mapping.py` | Structural consistency of cards ↔ mapping ↔ reviews | No |
| `check_sorries.py` | Fail if any non-Challenge Lean file contains `sorry`/`admit` | No |
| `check_axioms.py` | Kernel/axiom audit: mapped declarations within `permitted_axioms` (needs Lean) | No |
| `check_equivalence.py` | Verify in-Lean equivalence lemmas for `PASS_PROVABLE_EQUIV` targets (needs Lean) | No |
| `rebuild_pipeline.py` | Orchestrate all stages and write `docs/pipeline_report.md`; `--pipeline-status-out` also emits a machine-readable `pipeline_status.v0.1` JSON | No |
| `gate_decision.py` | Offline promotion decision (PROMOTE/BLOCK/REVISE/HUMAN_REVIEW); optional `--judge-metrics` caps to HUMAN_REVIEW; `--pipeline-status` consumes a fingerprint-checked formal status (fail-closed) | No |
| `source_review_decision.py` | Pre-proof source-fidelity review decision (SOURCE_REVIEW_PASS/HUMAN_REVIEW/REVISE/BLOCK) from structured judge evidence + calibration | No |
| `validate_judge_schema.py` | Validate one structured judge-evidence record (VALID/PARTIAL_RECOVERED/INVALID) | No |

Plus unit tests: `test_judge_parsing.py`, `test_gate_decision.py`, `test_pipeline_status.py`,
`test_blinding_boundary.py`, `test_source_review_decision.py`, `test_validate_source_formalization.py`,
`test_rebuild_pipeline.py`, `test_check_axioms.py`, `test_check_equivalence.py`,
`test_validate_judge_schema.py`, `test_score_judge.py`, `test_structured_judge_output.py`,
`test_structured_judge_workflow.py` (all offline, in CI).

## Requirements

- Lean toolchain `leanprover/lean4:v4.31.0` (via `elan`; pinned in `lean-toolchain`), Mathlib.
- Python 3.10+ with `PyYAML`. `openai` only if you use `run_judge.py --execute-api`.
- The Comparator stage additionally needs the Comparator + `lean4export` + `landrun` binaries
  (Linux/WSL) — see [`docs/COMPARATOR.md`](docs/COMPARATOR.md).

## Docs to read next

- [`ARCHITECTURE.md`](ARCHITECTURE.md) — stable design, boundaries, the pipeline and its gates.
- [`docs/ROADMAP.md`](docs/ROADMAP.md) — the active next steps.
- [`docs/MILESTONES.md`](docs/MILESTONES.md) — dated build history.
- [`docs/JUDGE_EVIDENCE_SUMMARY.md`](docs/JUDGE_EVIDENCE_SUMMARY.md) — recorded judge-reliability evidence.
- [`docs/GAP_ANALYSIS.md`](docs/GAP_ANALYSIS.md) — archived audit snapshot (provenance; no longer the active roadmap).
- [`CLAUDE.md`](CLAUDE.md) — agent instructions and the Lean theorem/helper split convention.
