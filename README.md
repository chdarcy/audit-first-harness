# Audit-First Formalisation Harness

**v0.1 — experimental.**

A small, human-driven harness for **checking the fidelity of a Lean formalisation against its
source claim**. It is the extracted, domain-neutral machinery from a Markowitz portfolio-theory
formalisation, reduced to an MVP and shipped with a single self-contained example
(put–call payoff parity).

For the design, roadmap, and v0.1 / v0.2 / v0.3 scope, see [`ARCHITECTURE.md`](ARCHITECTURE.md).

## What this is

The harness supports an *audit-first* workflow: before trusting that a Lean theorem says what a
source document claims, you assemble a paper trail and stress-test it.

1. **Theorem card** — transcribe a source claim into `docs/theorem_index.yaml` (source side only).
2. **Mapping** — link the claim to a Lean declaration and its Comparator triple in
   `docs/formal_mapping.yaml`, with a lifecycle state and a human-approval gate.
3. **Fidelity review** — a human writes and signs off a structured review in
   `docs/fidelity_reviews/<Target>.md`.
4. **Mutation + blinded judge** — `docs/mutants/<Target>.yaml` defines meaning-preserving and
   defect-injecting variants; the harness assembles **blinded** packages that an adversarial
   LLM "fidelity judge" can score, with the answer key held back. Discriminative-recall and
   consistency-false-alarm metrics tell you whether the judge can actually catch defects.
5. **Comparator audit** — the [Lean FRO Comparator](https://github.com/leanprover/comparator)
   independently re-elaborates a *Mathlib-only* statement of the theorem and has the Lean kernel
   confirm a delegating proof closes exactly that statement under a permitted axiom set.

## What this is NOT

- ❌ **Not a general automatic LaTeX → Lean translator or solver.** Nothing here converts a
  source document into Lean. A human (optionally assisted by a model) writes the Lean.
- ❌ **It does not guarantee autonomous proof generation.** Proof attempts are driven by a
  human/model agent and **checked by Lean** (and, optionally, by the Comparator). The harness
  audits and stress-tests an existing formalisation; it does not promise to produce one.
- ❌ **Not autonomous fidelity certification.** Every mapping passes through an explicit
  human-approval gate before any judge or mutation run; the LLM judge is **opt-in and off by
  default**.

## Layout

```
AuditHarness/            minimal Lean library (the put–call parity smoke-test theorem)
Audit/Template/          Challenge/Solution/comparator.json templates (*.template; not built)
Audit/PutCallParity/     a real, buildable Comparator triple for the example
scripts/                 the harness (see below)
docs/judge_prompts/      judge_v1.md — the frozen, hashed fidelity-judge system prompt
docs/templates/          theorem-card / mapping / review / mutants templates
docs/theorem_index.yaml  source ledger (example: thm:putcall)
docs/formal_mapping.yaml source <-> Lean bridge (example: PutCallParity)
docs/fidelity_reviews/   per-target reviews (example: PutCallParity.md)
docs/mutants/            per-target mutation test cases (example: PutCallParity.yaml)
examples/put_call_parity/source.tex   the example source document
```

## Scripts

| Script | What it does | Calls a model? |
|---|---|---|
| `run_mutants.py --dry-run` | Assemble blinded judge packages + answer key from the ledger | No |
| `run_judge.py` | `--dry-run` / `--export-manual` / **`--execute-api`** (opt-in) judge runner | Only with `--execute-api` |
| `import_manual_judge_results.py` | Aggregate manually-collected judge replies, with provenance | No |
| `score_judge.py` | Score judge results vs the local answer key; write metrics | No |
| `validate_mapping.py` | Structural consistency of cards ↔ mapping ↔ reviews | No |
| `check_sorries.py` | Fail if any non-Challenge Lean file contains `sorry`/`admit` | No |
| `check_axioms.py` | Kernel/axiom audit: mapped declarations within `permitted_axioms` (needs Lean) | No |
| `check_equivalence.py` | Verify in-Lean equivalence lemmas for `PASS_PROVABLE_EQUIV` targets (needs Lean) | No |
| `rebuild_pipeline.py` | Orchestrate all stages and write `docs/pipeline_report.md` | No |
| `gate_decision.py` | Offline promotion decision (PROMOTE/BLOCK/REVISE/HUMAN_REVIEW) → `docs/promotion/<Target>.yaml` | No |
| `test_judge_parsing.py` | Unit tests for judge-output YAML parsing / verdict recovery | No |
| `test_gate_decision.py` | Unit tests for the promotion-decision policy | No |
| `test_rebuild_pipeline.py` | Unit tests for the pipeline `--target` plumbing | No |
| `test_check_axioms.py` | Unit tests for the axiom-audit parser/classifier | No |
| `test_check_equivalence.py` | Unit tests for the provable-equivalence validator | No |

The judge is **never** contacted unless you explicitly pass `--execute-api` (OpenAI provider,
reads `OPENAI_API_KEY` from the environment).

## Quick start

```bash
lake exe cache get          # fetch Mathlib oleans (first time)
lake build                  # build the example library (proves put_call_payoff_parity)

python scripts/validate_mapping.py        # cards <-> mapping <-> reviews consistent
python scripts/run_mutants.py --dry-run   # assemble blinded judge packages (no model)
python scripts/check_sorries.py           # no incomplete proofs in the library
python scripts/rebuild_pipeline.py        # run every (non-gated) stage, write a report
```

The Comparator stage is human-gated; see [`docs/COMPARATOR.md`](docs/COMPARATOR.md) and run
`python scripts/rebuild_pipeline.py --with-build --with-comparator` once the Comparator
binaries are built (Linux/WSL).

## Adding your own target

1. **Add the source.** Put your `.tex` source under `examples/<target>/source.tex` (or
   `docs/source/<target>.tex`).
2. **Transcribe a theorem card.** Manually transcribe/extract the relevant theorem into
   `docs/theorem_index.yaml` using `docs/templates/theorem_card.template.yaml` (the harness does
   not auto-parse LaTeX — a human copies the claim across, source side only).
3. **Continue the pipeline.** Add the mapping, fidelity review, mutants, the Lean proof, and the
   Comparator `Audit/<Target>/` triple by copying the templates in `docs/templates/` and
   `Audit/Template/`; set the mapping's `state: HUMAN_APPROVED` and `human_approved: true` (and
   the matching review frontmatter), then re-run the quick-start checks. `run_mutants.py` refuses
   to assemble packages until the human-approval gate is satisfied.

## Requirements

- Lean toolchain `leanprover/lean4:v4.31.0` (via `elan`; pinned in `lean-toolchain`).
- Python 3.10+ with `PyYAML`. `openai` only if you use `run_judge.py --execute-api`.
- The Comparator stage additionally needs the Comparator + `lean4export` + `landrun` binaries
  (Linux/WSL) — see `docs/COMPARATOR.md`.
