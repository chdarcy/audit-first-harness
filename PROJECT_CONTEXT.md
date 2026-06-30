# PROJECT_CONTEXT.md — Audit-First Lean Formalisation Harness

**Single source of truth** for this repository: design, architecture, current status, invariants, the
implemented pipeline, Markowitz state, roadmap, open blockers, milestone history, the Comparator
procedure, and agent operating rules. **Current as of `d302eb6`** (Add Markowitz MK-003 theorem-card
metadata).

Short entrypoints defer here: [`README.md`](README.md) (front door) and [`CLAUDE.md`](CLAUDE.md)
(agent instructions). Generated evidence/reports (`docs/JUDGE_EVIDENCE_SUMMARY.md`,
`docs/pipeline_report.md`, `docs/validation_report.md`, `docs/mutation_report.md`) are referenced,
not merged. The Lean theorem/helper-split rule is **also** enforced at the point of writing Lean — see
the header of `AuditHarness.lean` — so it is seen without having to open this file (§7.1, §30).

---

## 1. What this repo is

An **audit-first Lean formalisation harness** — a repository-level workflow for **traceable
formalisation**. Its job is to structure, test, and record the path from a source theorem to a Lean
theorem so that a human or model agent cannot silently prove the *wrong* theorem. The central risk:

> Lean can prove a theorem that is formally valid but not the theorem the source intended.

It is reusable infrastructure for hard, multi-step formalisation projects. It provides: a minimal
Lean/Lake project; source `.tex` examples; source inventories and source-formalisation records;
theorem-card / mapping / review / mutation templates; the judge prompt + package generation; opt-in
live judge execution, scoring, and parse/structured metrics; a no-sorry scan and kernel/axiom audit;
the Comparator Challenge/Solution layout; pipeline report generation; the pre-proof source-fidelity
review gate and the post-Comparator promotion gate; and human-gated build/Comparator stages. It
deliberately keeps the source side, formal side, review side, and judge-evaluation side **separate**.

## 2. What this repo is not

- ❌ Not an automatic LaTeX parser / theorem extractor — a human transcribes the source claim.
- ❌ Not an automatic Lean proof generator or autonomous proof-search system — proofs are written by a
  human/model agent and **checked by Lean** (and optionally the Comparator).
- ❌ Not a guarantee the LLM judge is correct, and **not** a replacement for human mathematical review,
  Lean, or the Comparator. Model output is **untrusted until validated**.
- ❌ An inventory / source-formalisation record / theorem card is **not** verification — it records
  intent and structure, not correctness.
- ❌ The Comparator checks **Challenge vs Solution** statement equality, **not** source-`.tex` vs Lean.
- ❌ **Not** yet a fully agentic anti-drift system: the closed-loop controller that would let judge
  output *drive* statement revision and proof attempts is **future research** (§24).

## 3. Core invariants

**Two boundaries kept sharp:**

1. **Formal correctness ≠ source fidelity.** Lean build, no-sorry, the `#print axioms` audit, and the
   Comparator establish *formal proof correctness* and *formal statement equality* (the audited
   Challenge statement is exactly what the Solution proves, under a bounded axiom set). They do **not**
   establish that the Lean statement matches the source. Source→Lean fidelity is the job of source
   inventories, source-formalisation records, theorem cards, the mapping, fidelity reviews, the LLM
   judge, mutation scoring, and human review. **The Comparator compares Challenge vs Solution, not
   `.tex` vs Lean.**
2. **Judge metrics ≠ theorem truth.** Mutation recall and the consistency false-alarm rate measure
   **judge reliability, not theorem truth**. A judge that misses a planted defect tells you the
   *judge* is imperfect on that defect class; it does **not** tell you the real mapping is wrong.

**Operating invariants:**

3. The GPT judge is a **calibrated source-fidelity reviewer, not a theorem oracle**; a judge PASS
   never overrides a formal failure (in the promotion gate it can only cap to `HUMAN_REVIEW`).
4. Live judge/API calls are **opt-in only** (`run_judge.py --execute-api`); nothing else calls a model.
5. **Blinding boundary:** `run_judge.py` and `import_manual_judge_results.py` read the membership
   sidecar `_targets.yaml`, never the answer key; un-blinding via `_manifest.yaml` happens only on the
   scoring/export side (enforced by `scripts/test_blinding_boundary.py` in CI).
6. `rebuild_pipeline.py` is the **formal** pipeline; the structured-judge workflow is separate.
7. `PASS_PROVABLE_EQUIV` is guarded by an in-Lean equivalence check (`scripts/check_equivalence.py`).
8. The **source-fidelity review gate** (`scripts/source_review_decision.py`) is **pre-proof and
   non-mutating**: it never edits Lean and never overrides formal checks.
9. **Public theorem / helper split** (§7.1): the source-facing theorem stays readable in
   `AuditHarness/<Target>.lean`; proof machinery goes in a helper module. **Never weaken a statement
   to ease a proof.**
10. The closed-loop controller, a non-LLM (FormalAlign-style) alignment signal, a multi-judge
    ensemble, and vacuity / unused-hypothesis checks remain **future research** (§25).

## 4. Design principle

The system must never treat successful Lean compilation as sufficient evidence of source fidelity. A
formally proved statement can still be wrong w.r.t. the source if: an assumption was dropped or
strengthened; a conclusion was weakened; a variable was swapped; a denominator/positivity condition
was omitted; uniqueness was claimed in the source but only non-strict optimality was proved; a
theorem over all reals was formalised only on a sub-domain; a geometric statement was replaced by a
squared algebraic one without recording the equivalence; the statement became vacuous via
contradictory hypotheses; or an unused hypothesis gives false coverage. The pipeline therefore tracks
`source claim → inventory → source-formalisation record → theorem card → candidate Lean statement →
fidelity review/judge → proof → Comparator audit → promotion decision`.

## 5. Implemented scope and current pipeline

The harness is built in layers: two **implemented and in use**, one **future research**.

**Implemented — audit & formal pipeline:** source cards (`docs/theorem_index.yaml`), the
formal-mapping bridge (`docs/formal_mapping.yaml`), fidelity reviews + the human-approval *input*
gate, blinded hash-provenanced mutation packages (`run_mutants.py --dry-run`), the opt-in live judge
runner (`run_judge.py --execute-api`) + manual import, judge scoring (`score_judge.py`) with
parse-format metrics, the no-sorry check (`check_sorries.py`) and kernel/axiom audit (§16,
`check_axioms.py`), Comparator triples with a real run demonstrated end-to-end, the guarded
`PASS_PROVABLE_EQUIV` equivalence check (`check_equivalence.py`), target-scoped pipeline runs +
Comparator-status writeback, the structured `pipeline_status.v0.1` JSON + fingerprint-checked gate
freshness, and the offline **promotion gate** (`gate_decision.py`, §13).

**Implemented — source-intake & structured-judge evidence pipeline (source-fidelity side):** the
two-layer source intake (§8: `docs/source_inventories/` + `docs/source_formalizations/`); the
structured judge-evidence schema + validator (§11.1); structured scoring (§12.3); conservative gate
caps (§13.5); structured-output export (§12.4); an offline workflow runner (§12.5); and the pre-proof
source-fidelity review gate (`source_review_decision.py`, §14). This side only *produces, validates,
scores, gates, and reviews* source-fidelity evidence; it never runs the judge by itself and never
overrides a formal result.

**Future — the closed-loop controller (§24):** letting judge output *directly drive* statement
revision and proof attempts is **not yet implemented**. Today the harness **audits, reports, scores,
and gates** — judge output does not yet drive construction.

Intended pipeline:

```text
source.tex
  → source_inventories/<id>.yaml    (triage a whole source; content-bearing, source-specific)
  → source_formalizations/<id>.yaml (per-target semantic alignment; generic schema)
  → theorem_index.yaml              (theorem card; source side only)
  → formal_mapping.yaml             (source↔Lean bridge + lifecycle/audit state)
  → fidelity_reviews/<Target>.md    (human review)  +  judge package → fidelity judge → score vs mutants
  → candidate fidelity gate (pre-proof; source_review_decision.py)
  → Lean proof → lake build → no-sorry → kernel/axiom audit
  → Audit/<Target>/{Challenge,Solution}.lean + comparator.json → Comparator real-landrun check
  → pipeline report → promotion decision (gate_decision.py)
```

Key scripts (all offline / model-free unless noted):

| Script | Role |
|---|---|
| `run_mutants.py --dry-run` | Assemble blinded judge packages + answer key |
| `run_judge.py` | `--dry-run` / `--export-manual` / **`--execute-api`** (opt-in, OpenAI) judge runner |
| `import_manual_judge_results.py` | Aggregate manual judge replies (blinded) |
| `score_judge.py` | Score judge results vs the answer key (+ `--structured` reliability scoring) |
| `export_structured_judge_results.py` | Un-blind blinded results into structured `v0.3` JSON |
| `run_structured_judge_workflow.py` | Offline export → validate → score → (optional) gate |
| `validate_judge_schema.py` | Validate one structured judge-evidence record |
| `validate_source_formalization.py` | Structural validation of source-formalisation records |
| `validate_mapping.py` | Structural consistency of cards ↔ mapping ↔ reviews |
| `check_sorries.py` / `check_axioms.py` / `check_equivalence.py` | No-sorry / kernel-axiom audit / provable-equivalence (need Lean) |
| `rebuild_pipeline.py` | Formal pipeline orchestration; `--pipeline-status-out` emits `pipeline_status.v0.1` JSON |
| `gate_decision.py` | Promotion decision (PROMOTE/BLOCK/REVISE/HUMAN_REVIEW); `--judge-metrics` caps; `--pipeline-status` fingerprint-checked, fail-closed |
| `source_review_decision.py` | **Pre-proof** source-fidelity review (SOURCE_REVIEW_PASS/HUMAN_REVIEW/REVISE/BLOCK) |

CI runs all Python unit suites + ledger/source-formalisation validation, and a `lean-build` job that
builds every theorem module and all Challenge/Solution triples then runs `check_axioms` +
`check_equivalence`. The **real Comparator** (landrun sandbox + binaries) is **local/WSL,
human-gated, and not run in CI** — CI proves the triples *build* (formal evidence only, not source
fidelity).

## 6. Source-fidelity vs formal correctness boundary

The two are never conflated. The Comparator + formal layer certify that the *Solution* proves exactly
the audited *Challenge* statement under a bounded axiom set — statement equality + a kernel-accepted
proof. Whether that statement faithfully captures the **source** claim is a separate axis handled by
the source-side ledger (inventory → record → card), the human fidelity review, the blinded judge +
mutation calibration, and the pre-proof source-fidelity review gate. **Judge evidence is reliability
evidence about the judge, never a theorem-truth certificate.** Reading a missed discriminative mutant:
it is **not** a harness failure — it is calibration evidence that the judge has a weakness; it should
reduce automation confidence / require human review; it is **not** proof the real mapping is wrong.

## 7. Repository layout

```text
audit-first-harness/
├── PROJECT_CONTEXT.md            # canonical (this file)
├── README.md                     # short front door
├── CLAUDE.md                     # short agent entrypoint
├── lean-toolchain  lakefile.toml  lake-manifest.json  requirements.txt
├── AuditHarness.lean             # library umbrella (imports each target; carries the §7.1 rule header)
├── AuditHarness/
│   ├── <Target>.lean             # public source-facing theorem module
│   └── <Target>/Helpers.lean     # proof-engineering helpers (e.g. PutCallParity/, TwoAssetMinVar/)
├── Audit/
│   ├── Template/                 # Challenge/Solution/comparator.json skeletons (*.template)
│   └── <Target>/                 # Challenge.lean / Solution.lean / comparator.json
├── examples/<source_id>/source.tex
├── docs/
│   ├── theorem_index.yaml        # source ledger (theorem cards; source side only)
│   ├── formal_mapping.yaml       # source ↔ Lean bridge + lifecycle/audit state
│   ├── source_inventories/       # content-bearing source triage (+ README)
│   ├── source_formalizations/    # generic per-target semantic-alignment records (+ template + README)
│   ├── fidelity_reviews/<Target>.md
│   ├── mutants/<Target>.yaml
│   ├── judge_prompts/judge_v1.md # frozen, hashed fidelity-judge system prompt
│   ├── templates/                # card / mapping / review / mutants templates
│   ├── judge_inputs_dryrun/      # generated: V-*.yaml + _manifest.yaml (answer key) + _targets.yaml (membership)
│   ├── judge_requests/  judge_results/   # generated manual exports / real+scored results
│   ├── JUDGE_EVIDENCE_SUMMARY.md # committed judge-reliability evidence (raw artifacts gitignored)
│   └── validation_report.md  mutation_report.md  pipeline_report.md   # generated
└── scripts/                      # the harness + unit tests (see §5)
```

(Note: the Comparator how-to formerly in `docs/COMPARATOR.md` is now §15.3 below; the former
`ARCHITECTURE.md` / `docs/MILESTONES.md` / `docs/ROADMAP.md` / `docs/GAP_ANALYSIS.md` are consolidated
into this file.)

### 7.1 Lean module readability convention (the public theorem / helper split)

For nontrivial targets, keep the **source-facing theorem statement** in a short public module and push
proof-engineering detail into a sibling helper module. The mapped declaration in `formal_mapping.yaml`
must point to the **final source-facing theorem** in the public module, never to an internal helper.

```text
AuditHarness/<Target>.lean         # public, source-facing: imports helpers; final mapped theorem; short readable proof
AuditHarness/<Target>/Helpers.lean # internal: definitions, algebraic identities, technical/minimality lemmas, ring/field_simp/linarith
```

A declaration's fully-qualified name is fixed by its **namespace, not its file**, so moving a
`def`/lemma into a helper module (same `namespace`) keeps its name — and the Comparator triple,
mutants, and mapping — unchanged. Comparator `Challenge`/`Solution` files import the public module (or
the `AuditHarness` umbrella), not internal helpers. **Never weaken a theorem statement to simplify its
proof; add helper lemmas instead.** `PutCallParity` and `TwoAssetMinVar` follow this convention. **This
rule is repeated as a header comment in `AuditHarness.lean`** so any agent adding a Lean target sees it
at the authoring site.

## 8. Core ledger & source-intake files

For **hard, multi-step sources** the front of the pipeline has two source-intake layers, distinct from
the ledger that follows:

- **Source theorem inventory** (`docs/source_inventories/<id>.yaml`, `record_type:
  source_theorem_inventory`): the first reading/triage pass over a whole source — *content-bearing,
  source-specific*; enumerates candidate targets with dependencies, difficulty, separated
  source-fidelity vs proof risks, a recommended order, and what to defer. Intentionally **not**
  validated by `validate_source_formalization.py` (kept separate so the generic layer stays
  source-agnostic). Nothing in it is proved or verified.
- **Source-formalisation record** (`docs/source_formalizations/<target_id>.yaml`, `record_type:
  source_formalization`, validated by `validate_source_formalization.py`): a per-target
  semantic-alignment record — symbols, assumptions, conclusion shape, abstraction choices,
  ambiguities, proof decomposition. *Generic, source-agnostic infrastructure*; review statuses
  `draft | ready_for_card | needs_human_review | approved`.

Then the ledger:

- **`docs/theorem_index.yaml`** — the **source-side theorem ledger for active / selected targets**
  (an entry is created when a target enters formalisation and is referenced by a `formal_mapping`).
  It is **not** mandatory for every pre-Lean record — **the canonical pre-Lean source-fidelity card is
  the source-formalisation record** above. Each entry (`thm:<key>`) has an
  `auto` block (source-extracted / verbatim-style: `env`, `title`, `line_start/line_end`,
  `equation_labels`, `body_tex`, optional per-entry `source_file`) and a `curated` block (hand-written
  `paraphrase`, `informal_assumptions`, `notes`). Only `auto.body_tex`, `curated.paraphrase`, and
  `curated.informal_assumptions` are judge-visible — keep answer-key language (verdicts,
  "discriminative"/"consistency", approvals) **out** of those three. No Lean names, proof status,
  Comparator configs, judge verdicts, or mutation labels here.
- **`docs/formal_mapping.yaml`** — the **post-Lean source-to-Lean bridge** for implemented /
  near-implemented targets only (created once a Lean declaration exists or is stable — **not** pre-Lean
  planning, and **no** draft formal-mapping lifecycle): which source claim → which Lean
  declaration/module; the Comparator triple; `verdict`; `equivalence` (null / provable_equiv lemma);
  `comparator_status`; `review` path; `state`; `human_approved`. `permitted_axioms`:
  `{propext, Quot.sound, Classical.choice}`. No full mathematics or prose review here.
- **`docs/fidelity_reviews/<Target>.md`** — the human-readable semantic review, with YAML frontmatter
  (target, source_refs, lean_declaration, verdict, a rubric A–G, judge block, `human_approved` +
  approver) and a plain-English body detailed enough to justify the mapping.
- **`docs/mutants/<Target>.yaml`** — the judge-calibration file: the real statement, meaning-preserving
  (consistency) variants expected to pass, defect-injecting (discriminative) variants expected to
  fail, expected labels, operators, notes. Never sent to the judge directly; `run_mutants.py` blinds.

## 9. Blinded judge package design

`run_mutants.py --dry-run` reads the card, mapping, review, and mutants; enforces the human-approval
gate; creates one package per variant; blinds with deterministic shuffled IDs (`V-0001`…); renames the
Lean theorem to a neutral candidate name; writes judge-visible packages, a local `_manifest.yaml`
answer key, and a membership-only `_targets.yaml`. The judge sees only: the source claim, the candidate
Lean statement, ambient info, and the allowed verdict enum. The judge must **not** see: the expected
verdict, mutant class, operator, human approval, the answer key, or whether a package is real or
mutated.

## 10. Judge prompt

`docs/judge_prompts/judge_v1.md` is a frozen, hashed adversarial formalisation-fidelity reviewer. It
compares source vs Lean assumptions, conclusion, variable correspondence, quantifier scope, possible
vacuity, formula shape, and representation choices. Verdict enum:
`PASS | PASS_EQUIV | PASS_PROVABLE_EQUIV | WARN | FAIL | OUT_OF_SCOPE`. Output must be strict YAML (no
code fences, no prose outside YAML, quoted short scalars, block scalars for rationale, no unquoted
`: ` in scalars, exactly one top-level `verdict:`). The parser stays defensive regardless.

## 11. Judge output parsing and recovery

`run_judge.py` owns judge execution and output parsing: keep `raw_output` unchanged; parse strict YAML
when possible; on failure recover only a single unambiguous top-level `verdict:` (set
`recovered_verdict: true`, `judge_output: null`, preserve `parse_error`); never fabricate
`rationale`/`detected_issues`/`equivalence_argument`; multiple conflicting or absent verdicts ⇒
unrecoverable. Tested in `test_judge_parsing.py`.

### 11.1 Structured judge-evidence schema

A structured record (`schema_version: "0.3.0"`) carries `target`, `source_ref`, `candidate_id`,
`verdict` (`PASS | PASS_EQUIV | PASS_PROVABLE_EQUIV | WARN | FAIL | UNPARSEABLE`), `confidence` ∈ [0,1],
typed `concerns` (type/severity/description + optional evidence), `summary`, `requires_human_review`.
`scripts/validate_judge_schema.py` is a pure, offline validator classifying a record `VALID`,
`PARTIAL_RECOVERED`, or `INVALID`; it calls no model, reads no answer key, and makes no promotion
decision. Validation is schema-shape only; a `verdict: PASS` here never overrides build / no-sorry /
axiom audit / Comparator / equivalence.

## 12. Scoring the judge

`score_judge.py` compares judge results against `_manifest.yaml` (local only; the answer key is never
sent to the model).

- **12.1 Fidelity classification metrics:** `real_mapping_agreement_exact/_bucket`,
  `discriminative_recall`, `consistency_false_alarm_rate`, `overall_bucket_accuracy`, `per_operator`
  rates. Real mapping + consistency mutants should be accepted; discriminative mutants should be
  rejected. **These measure judge reliability, not theorem truth.**
- **12.2 Parse-format metrics:** `parsed_clean_count`, `recovered_verdict_count`,
  `unrecoverable_parse_error_count`, `malformed_yaml_rate` (0.0 ideal; unrecoverable errors should
  block automated promotion).
- **12.3 Structured scoring** (`--structured`): scores stored `0.3.0` JSON against the answer key,
  validating each record first. Buckets: accept `{PASS, PASS_EQUIV, PASS_PROVABLE_EQUIV}`, reject
  `{WARN, FAIL}`; `UNPARSEABLE`/`INVALID` excluded from accept/reject rates and counted separately.
  Emits schema-quality rates, reliability metrics, concern counts, and per-target/per-concern
  breakdowns. Makes no promotion decision.
- **12.4 Structured export** (`export_structured_judge_results.py`): pure, offline converter on the
  *scoring* side of the answer-key boundary — joins blinded results to `_manifest.yaml` + the mapping
  and emits validated `0.3.0` records. Un-blinding lives **here**, never in `run_judge.py`/
  `import_manual_judge_results.py`. Never fabricates judge content (`OUT_OF_SCOPE`/absent/unrecoverable
  → `UNPARSEABLE`; confidence + concern-severity mappings documented in the script).
- **12.5 Offline workflow** (`run_structured_judge_workflow.py`): chains export → schema validation →
  structured scoring → optional conservative gate, deterministically and offline; does **not** run the
  judge; deliberately separate from `rebuild_pipeline.py`.

## 13. Promotion decision policy

A **machine-readable promotion gate** (`scripts/gate_decision.py`) turns existing formal + fidelity
artifacts into one `PROMOTE / BLOCK / REVISE / HUMAN_REVIEW` decision. Pure, offline, idempotent — no
API, never runs the judge, only consumes artifacts.

- **13.1 Global vs local:** *local* = does this mapping's formal + fidelity evidence pass (build,
  no-sorry, axiom audit, Comparator, real-mapping verdict, provenance/hash, human approval, review)?
  *global* = how reliable is the judge over the mutant set? **Global judge-calibration metrics must
  not, by themselves, hard-block** a target whose real mapping and formal checks pass — they cap
  confidence and force HUMAN_REVIEW; never BLOCK on their own.
- **13.2 Decision rules (ordered):** (1) **BLOCK** on any hard formal/integrity failure (build fail;
  no-sorry/axiom fail; Comparator fail; provenance/hash mismatch; unrecoverable judge parse error;
  missing approval/review; mapped declaration missing). (2) **REVISE/HUMAN_REVIEW** when the real
  mapping is judged `FAIL`/`WARN` with no human override. (3) **HUMAN_REVIEW / lower confidence** when
  formal checks pass and the real mapping is accepted but judge calibration is weak. (4) **PROMOTE**
  when all formal gates pass, the real mapping is accepted, and judge confidence is high.
- **13.3 Inputs/Output:** consumes `formal_mapping.yaml`, `fidelity_reviews/<T>.md`,
  `judge_results/<T>_scored.yaml`, `_manifest.yaml` provenance, and the formal status — preferably a
  structured `pipeline_status.v0.1` JSON (`rebuild_pipeline.py --pipeline-status-out`, consumed via
  `--pipeline-status`): target-scoped, schema/target/required-stage validated, sha256
  fingerprint-checked, **fail-closed (BLOCK)** on stale/mismatched/missing; markdown report is the
  unvalidated fallback. Writes `docs/promotion/<Target>.yaml` only; never edits the mapping/reviews/
  mutants; refuses overwrite without `--force`.
- **13.4 Comparator-status policy:** not all `PASSED_*` are equal (see §15.2). `PASSED_FAKE_LANDRUN`
  caps confidence → HUMAN_REVIEW; `PASSED_REAL_LANDRUN_BEST_EFFORT` is intermediate.
- **13.5 Conservative structured-judge caps** (`--judge-metrics <summary.json>`): a *global* signal
  that may **only cap an otherwise-PROMOTE target to HUMAN_REVIEW** (never BLOCK/PROMOTE, never upgrade
  a non-PROMOTE formal decision). Caps when, for the target, `schema_valid_rate < 1.0`, `invalid_rate
  > 0`, `unparseable_rate > 0`, `discriminative_recall < 1.0`, `false_acceptance_rate_discriminative >
  0`, `false_rejection_rate_consistency > 0`, or high/critical concerns > 0. Records
  `judge_metrics_status`, a `judge_metric_cap` object, and a "reliability evidence, not theorem truth"
  disclaimer.

## 14. Candidate (pre-proof) gate vs promotion gate

Two gates, never conflated:

- **Candidate fidelity gate (pre-proof) — IMPLEMENTED as `scripts/source_review_decision.py`.** Decides
  whether the statement/mapping is faithful enough to be *worth proving*, from structured judge
  evidence + the judge's calibration. Emits `SOURCE_REVIEW_PASS / HUMAN_REVIEW / REVISE / BLOCK` with a
  reasons list; never touches formal status, never edits Lean, never calls a model. A `REVISE` means
  "fix the statement before spending effort on a proof."
- **Final promotion gate (post-Comparator) — `gate_decision.py` (§13).** Decides whether an *already
  proved and Comparator-checked* target may be promoted; additionally consumes build / no-sorry /
  axiom-audit / Comparator results.

They are separate scripts because the available inputs differ (the pre-proof call has no
build/Comparator results yet).

## 15. Comparator architecture & procedure

The Comparator validates **formal statement equality + kernel acceptance** — not source fidelity.

### 15.1 Triple shape
Each target has `Audit/<Target>/{Challenge.lean, Solution.lean, comparator.json}`:
- **Challenge.lean** — *Mathlib-only* (never `import Mathlib`; import only needed modules); copies the
  minimal definitions to state the theorem into the `AuditHarness.StatementAudit` namespace; states it
  with `:= by sorry`; no project imports.
- **Solution.lean** — imports the project library; repeats the identical statement; proves it by
  delegating (`exact _root_.<lib_thm> args`; `_root_.` escapes the same-named `StatementAudit`
  theorem). If the statement mentions a project `structure`/`class`/`inductive`, repack via the
  anonymous constructor (a copied structure is a fresh, non-defeq type).
- **comparator.json** — `challenge_module`, `solution_module`, `theorem_names`, `permitted_axioms`
  (`propext`, `Quot.sound`, `Classical.choice`), `enable_nanoda`.

Success prints `Your solution is okay!`. **Restated:** the Comparator compares Challenge vs Solution
(statement equality + kernel acceptance under permitted axioms), **not** `.tex` vs Lean.

### 15.2 Sandbox status vocabulary
The Comparator runs Challenge build + `lean4export` inside a `landrun` (Landlock) sandbox, invoked
with `--best-effort`; under WSL the kernel often exposes only Landlock **ABI 3** and the sandbox
**degrades** rather than failing. Record the achieved mode honestly in `comparator_status`:

```text
PASSED_REAL_LANDRUN              # full Landlock sandbox
PASSED_REAL_LANDRUN_BEST_EFFORT  # real landrun, degraded/unverified ABI / best-effort
PASSED_FAKE_LANDRUN              # scripts/fake-landrun.sh shim — NOT sandboxed
SKIPPED_COMPARATOR_TOOL_UNAVAILABLE
FAILED_COMPARATOR
```

`PASSED_FAKE_LANDRUN` is **not** a real sandbox and must never be treated as a high-confidence pass.
Where possible also record the Landlock ABI / kernel in the evidence bundle and
`promotion_decision.provenance`.

### 15.3 Running the Comparator (local / WSL; human-gated)
This stage is **human-gated** in `rebuild_pipeline.py` (run with `--with-comparator`) and the sandbox
is **Linux-only**. Build the triple on any platform:

```bash
lake build Audit.PutCallParity.Challenge Audit.PutCallParity.Solution
# Challenge emits an expected `sorry` warning; Solution must build clean.
```

One-time setup (Linux/WSL): build the Comparator, a version-matched `lean4export` (matching this
project's Lean version), and `landrun`; point the harness at them:

```bash
export COMPARATOR_BIN="$HOME/tools/comparator/.lake/build/bin/comparator"
export COMPARATOR_LEAN4EXPORT="$HOME/tools/lean4export/.lake/build/bin/lean4export"
export COMPARATOR_LANDRUN="$HOME/tools/landrun/landrun"   # real Landlock sandbox
```

Run a single target, or let the pipeline drive every target and record the result:

```bash
lake env "$COMPARATOR_BIN" Audit/PutCallParity/comparator.json
# or:
python scripts/rebuild_pipeline.py --with-build --with-comparator
```

If the three `COMPARATOR_*` binaries are unset or the platform is not Linux, the pipeline records
`SKIPPED_COMPARATOR_TOOL_UNAVAILABLE` (the `comparator.json` configs are still existence-checked).
`landrun` needs a Linux kernel ≥ 5.13 with `CONFIG_SECURITY_LANDLOCK=y`; a `fake-landrun.sh` shim
(unsandboxed, insecure) can stand in for local dev only.

## 16. No-sorry and kernel/axiom audit

`check_sorries.py` fails if any non-Challenge Lean file contains `sorry`/`admit`/`sorryAx`; it skips
`Audit/*/Challenge.lean` and `Audit/Template/*.template` (Challenge files intentionally use `sorry`).
The textual scan is a heuristic, so `check_axioms.py` adds a kernel-backed check: for each mapped
declaration, `#print axioms` ⊆ `{propext, Quot.sound, Classical.choice}` and no `sorryAx`.

## 17. Artifact and evidence policy

Four tiers: **Source** (committed, reviewed as code: scripts, prompts, templates, README/
PROJECT_CONTEXT, `requirements.txt`, source `.tex`, Lean source, Audit templates, tests, ledger
YAMLs); **Fixtures** (committed but deliberately regenerated: seeded `judge_inputs_dryrun/V-*.yaml`,
`_manifest.yaml`, `_targets.yaml`); **Evidence** (a reproducible record of a real run, captured
intentionally, with provenance); **Disposable** (everything else generated locally; not committed).
Rules: do **not** mix hardening/source commits with evidence-run commits; evidence-run commits may
include generated artifacts intentionally, with a message that says so; if the prompt/mutants change,
regenerate or exclude stale dry-run artifacts; keep `docs/judge_results/*` and `docs/promotion/*` out
of generic commits (gitignored; `*_preview.yaml` is the committed exception).

## 18. Environment and cache policy

Do not commit: `.lake/`, `.elan/`, `.venv/`, `__pycache__/`, `*.pyc`, `.oai_key`, `*.key`, `.env`, the
Comparator/landrun/lean4export binaries, or WSL build dirs. Commit reproducibility metadata:
`lean-toolchain`, `lakefile.toml`, `lake-manifest.json`, `requirements.txt`. Reproduce with
`lake exe cache get && lake build && python -m pip install -r requirements.txt`. The root
`markowitz_lecture_notes.tex` is intentionally **untracked** (the canonical copy is committed at
`examples/markowitz_lecture_notes/source.tex`); do not commit the root copy.

## 19. API key policy

The live judge reads `OPENAI_API_KEY` from the environment. Never print or log the key; inspect only
non-empty presence/length if needed; never commit `.oai_key`/`.env`; real model calls require explicit
`--execute-api`; no script calls a model by default.

## 20. Worked targets

Three targets are fully worked (built, no-sorry, kernel-axiom-audited, real Comparator pass recorded,
human-approved):

| Target | Lean declaration | Comparator status |
|---|---|---|
| `PutCallParity` | `put_call_payoff_parity` (`max (S-K) 0 - max (K-S) 0 = S - K`) | `PASSED_REAL_LANDRUN_BEST_EFFORT` |
| `TwoAssetMinVar` | `two_asset_min_variance_weight` (non-strict global min over **all** real weights, denom > 0; no uniqueness) | `PASSED_REAL_LANDRUN_BEST_EFFORT` |
| `GoldIrrationalSqrtTwo` | `gold_irrational_sqrt_two : Irrational (√2)` (thin wrapper over Mathlib `irrational_sqrt_two`) | `PASSED_REAL_LANDRUN_BEST_EFFORT` |

`TwoAssetMinVar` is the finance-relevant fidelity-stress target (algebraic proof, easy to mutate:
numerator/denominator/sign/domain/`≤`-vs-`=` traps). `GoldIrrationalSqrtTwo` is a public,
known-correct gold-reference fixture, not an original finance theorem.

**Judge calibration** (opt-in, `gpt-4o` @ temp 0, 25 packages across the three targets): aggregate
discriminative recall **0.875**, false-alarm rate **0.0**, 25/25 clean parses — strong but
**imperfect** (missed `PCP-D2`, `TAM-D1`). See `docs/JUDGE_EVIDENCE_SUMMARY.md`. Raw judge artifacts
gitignored; only the summary is committed. *If the judge misses a mutant, infrastructure passed and
the benchmark found a judge weakness — it is not a "smoke-test failure".*

## 21. Current Markowitz state

The Markowitz source (`examples/markowitz_lecture_notes/source.tex`) is at the **theorem-card** stage
for its first target:

- source committed at `examples/markowitz_lecture_notes/source.tex`;
- inventory exists at `docs/source_inventories/markowitz_lecture_notes.yaml` (12 candidate targets);
- MK-000 and MK-003 source-formalisation records exist and are `ready_for_card`
  (`docs/source_formalizations/markowitz_mk000_setup_algebraic.yaml`,
  `…/markowitz_mk003_lemma_D_positive.yaml`);
- MK-003 theorem card exists as `thm:markowitz_lemma_d_positive` in `docs/theorem_index.yaml`;
- no `formal_mapping.yaml` entry exists yet;
- no Lean declaration/module exists yet;
- no proof exists yet;
- no Comparator artifact exists yet;
- no judge package exists yet;
- no promotion gate has run;
- concrete Lean encoding remains open;
- no `formal_mapping.yaml` entry is created yet **by design**: `formal_mapping.yaml` is for
  implemented or near-implemented Lean targets, not pre-Lean planning. **No draft formal-mapping
  lifecycle will be added now**; the mapping entry follows the Lean scaffold.

MK-003 (Lemma D positivity) is the first proof target: for SPD `Σ` (`n > 0`) and `μ` not proportional
to the ones vector, with `A = 1ᵀΣ⁻¹μ`, `B = μᵀΣ⁻¹μ`, `C = 1ᵀΣ⁻¹1`, `D = BC − A²`, then `C > 0`,
`B > 0`, `D > 0`. The public/source-facing theorem stays **Markowitz-shaped**; an abstract
inner-product / Gram-determinant lemma (`⟨x,x⟩⟨y,y⟩ − ⟨x,y⟩² > 0` for independent `x,y`, instantiated
`x=μ, y=1`) is only a **proposed** proof helper, not the public statement. MK-002, the probabilistic
covariance construction, and CAPM remain **deferred**; the 2×2 dual-system uniqueness is **split off**
from MK-003 (positivity only). The source Lemma D *statement* advertises `C>0` and `D>0`; `B>0` is a
proof subclaim surfaced explicitly in the records.

## 22. Roadmap / next steps

1. **Next Markowitz step: explore a direct Lean representation / scaffold for
   `MarkowitzLemmaDPositive` — not more YAML.** No draft formal-mapping lifecycle will be added.
2. Keep structural metadata close to Lean, but do **not** add a `formal_mapping.yaml` entry until a
   Lean declaration exists: it is for implemented or near-implemented (post-Lean) targets, not
   pre-Lean planning.
3. Decide concrete Lean encoding (Mathlib Matrix/vector directly vs a wrapper / bilinear-form /
   inner-product abstraction that still exposes the Markowitz-shaped statement).
4. Create Lean theorem scaffold (`AuditHarness/MarkowitzLemmaDPositive.lean` + a `Helpers.lean`).
5. Prove and run build / no-sorry / kernel-axiom audit.
6. Add source-fidelity review / mutants / judge package.
7. Add Comparator triple and promotion-gate evidence.

Then iterate down the inventory sequence (MK-007 two-fund, MK-004 frontier, MK-005 parabola, MK-006
GMVP, MK-008 risk-free/CML, MK-009 one-fund/tangency); MK-010/MK-011 (Sharpe/CAPM) deferred.

## 23. Open blockers

- **Formal-mapping entry for Markowitz is intentionally deferred to post-Lean — not a blocker.**
  `validate_mapping.py` requires every target to have a Lean declaration, Comparator config, and review
  file. We are **not** adding a draft/`NOT_IMPLEMENTED` lifecycle; `formal_mapping.yaml` is for
  implemented or near-implemented Lean targets. **Do not force a mapping entry before the
  Lean/review/Comparator artifacts exist;** the entry follows the Lean scaffold.
- **Concrete Lean encoding for MK-003 is open** (a design decision, deferred to the card/mapping stage).
- **Residual (informational):** several non-`.md` files (`docs/formal_mapping.yaml` comments and some
  `scripts/*.py` docstrings) still cite `ARCHITECTURE.md §§`; those `§` numbers now map to sections of
  this file. Repointing them is a future cleanup (out of scope when those files are not otherwise
  being edited).
- **Future research (not blockers):** closed-loop controller; non-LLM alignment signal; multi-judge
  ensemble; vacuity / unused-hypothesis checks; real Comparator-in-CI (binaries not in CI).

## 24. Closed-loop agentic workflow (future)

Current MVP: `candidate exists → judge reports → human interprets`. Target architecture:
`source.tex → agent writes card → proposes Lean statement → judge reviews mapping → if FAIL/WARN
revise card/statement/mapping → repeat until PASS or human override → attempt proof → build →
Comparator → promotion decision`. Discipline: don't start proof search until a card + mapping exist;
run the judge before a long proof; on a mismatch, revise the statement rather than force a proof; if
the statement changes, regenerate the Comparator triple; record every override in the fidelity review.
**Today the gate *emits* an actionable `REVISE`; a human acts on it — automating that step is the
future controller.**

## 25. Future improvements

- **Closed-loop controller** (§24) — judge output drives revise/prove/block/promote/review.
- `--target` support in `rebuild_pipeline.py` — **implemented** (per-target runs; no-arg = all targets).
- **FormalAlign-style non-LLM second signal** — embedding/alignment/certainty score as a heterogeneous
  second opinion.
- **Kernel-backed vacuity checks** and an **unused-hypothesis linter** — catch vacuous statements /
  source-critical hypotheses unused by the proof (→ review).
- **`PASS_PROVABLE_EQUIV`** — **implemented as a guarded path**: legitimate only with a supplied,
  *built* in-Lean equivalence lemma verified by `check_equivalence.py`; else downgrade to `PASS_EQUIV`
  / HUMAN_REVIEW.
- **Theorem dependency graph** (blueprint-style nodes/`depends_on`) for large projects (Markowitz).
- **Multi-judge ensemble** — gate on consensus/disagreement when a single judge has low recall.
- **Blueprint/orchestration exploration note.** We ran a bounded design/mockup and scratch-spike
  exploration of LeanArchitect and LeanMarathon. LeanArchitect was structurally promising as a
  Lean-side declaration/DAG/status extractor, but the expected near-term reduction was modest,
  Mathlib/toolchain coexistence was not yet proven for this repo, and it does not supply
  source-fidelity evidence. LeanMarathon overlaps with the closed-loop orchestration problem (§24) but
  is intentionally not duplicated or adopted here: it is heavier operational infrastructure and does
  not replace this repo's audit layer. Current policy: use the ideas where helpful, keep
  source-fidelity and audit evidence in this harness, and do not add either dependency unless a later
  targeted spike justifies it.

## 26. Milestone history (condensed; short commit hashes)

- **v0.1 — audit & measurement spine** (`7cc9451` …): source cards, formal-mapping bridge,
  human-approval input gate, blinded hash-provenanced mutation packages, opt-in judge runner + manual
  import, judge scoring, no-sorry check, Comparator triples (PutCallParity), generated reports;
  judge-parsing hardening (`a494c27`).
- **v0.2 — offline formal gate & pipeline:** promotion gate (`e9e2d8c`), target-scoped pipeline
  (`fe6f887`), Comparator-status writeback (`f19ce73`), kernel axiom audit (`dbef69e`), guarded
  provable-equivalence (`33a02fe`), `TwoAssetMinVar` (`1330531`), theorem/helper module refactor
  (`bf1a8c0`), `GoldIrrationalSqrtTwo` (`092bbd0`).
- **v0.3 — structured-judge evidence pipeline:** schema validator (`7dae994`), structured scoring
  (`874a787`), conservative gate caps (`64f1ab1`), structured export (`32c5e71`), offline workflow
  runner (`ba34aaf`).
- **Documentation & recorded evidence:** doc split (`90ae0b5`); gap analysis (`8ecb2b9`); recorded real
  Comparator passes for all three targets (`ce5d8f3`); structured `pipeline_status.json` + gate
  freshness (`9a42747`); expanded formal CI (`d31c245`); blinding-boundary regression tests
  (`663fd19`); first real judge calibration (`f4e4336`); broadened calibration to all targets
  (`598f35f`); source-fidelity review decision layer (`73b262b`); final completion audit (`c519dc5`).
- **Source-intake layer & Markowitz:** generic source-formalisation records (`fac6b7c`);
  target-agnostic validator tests (`d3d22bf`); first content-bearing intake — Markowitz inventory
  (`1b3b6a2`); docs refresh (`c981bd9`); MK-000/MK-003 records (`44bff82`); review-notes revision
  (`e991d89`); records `ready_for_card` (`552ac50`); MK-003 theorem-card metadata (`d302eb6`); this
  consolidation into `PROJECT_CONTEXT.md`.

## 27. Minimal command sequences

```bash
# Generic non-API validation
python scripts/validate_mapping.py
python scripts/validate_source_formalization.py
python scripts/check_sorries.py
python scripts/run_mutants.py --dry-run
python scripts/rebuild_pipeline.py
lake build

# Full local build + Comparator (Linux/WSL; see §15.3 for COMPARATOR_* env)
python scripts/rebuild_pipeline.py --with-build --with-comparator

# Live judge (only when explicitly approved)
python scripts/run_mutants.py --dry-run
python scripts/run_judge.py --target <Target> --provider openai --model gpt-4o --temperature 0 --execute-api
python scripts/score_judge.py --target <Target> --force
```

## 28. Success criteria (a promotable target)

The audit/formal layer is working when, on a fresh theorem (as on `TwoAssetMinVar`): a fresh `.tex`
source is added; a theorem card is written; a Lean statement is proposed; the judge reviews the
candidate **before** proof search; a gate decision is produced (a rejected candidate yields `REVISE`
with actionable reasons); the accepted statement is proved in Lean; the Comparator passes
real-landrun; and the report records card / mapping / review / judge result / mutation reliability /
build+no-sorry / Comparator status / promotion decision. That is where the judgement layer informs
construction rather than only reporting. (Automatic agent-driven revision after `REVISE` is the future
controller, §24.)

## 29. Research grounding and references

Design borrows established ideas; unverifiable names are deliberately omitted.
- **Traceable informal↔formal structure:** Lean blueprints (`leanblueprint`,
  <https://github.com/PatrickMassot/leanblueprint>); LeanArchitect (2026,
  <https://arxiv.org/abs/2601.22554>) — closer to Lean→blueprint sync than `.tex`→Lean extraction
  (this harness uses hand-curated cards).
- **Autoformalization & proof automation:** Goedel-Prover / V2
  (<https://arxiv.org/abs/2502.07640>, <https://arxiv.org/abs/2508.03613>); ProofBridge (2025,
  <https://arxiv.org/abs/2510.15681>) — warns of judge-in-the-loop Goodharting.
- **Fidelity / alignment evaluation (the judge layer):** FormalAlign (ICLR 2025,
  <https://arxiv.org/abs/2410.10135>); Reliable Evaluation & Benchmarks for Statement
  Autoformalization (EMNLP 2025, <https://aclanthology.org/2025.emnlp-main.907/>) — even human-written
  formal statements contain semantic errors (motivates audit-first); Symbolic equivalence + semantic
  consistency (<https://arxiv.org/abs/2410.20936>); Epistemic Ensemble of LLM Judges (2025,
  <https://arxiv.org/abs/2506.10903>) — supports §25 ensemble + "judge ≠ certificate"; Do LLMs Game
  Formalization? (2026, <https://arxiv.org/abs/2604.19459>) — vacuity/premise-manipulation failures.
- **Judge-reliability methodology:** mutation testing (DeMillo–Lipton–Sayward 1978; Jia & Harman,
  IEEE TSE 2011) — applied to a *judge*; the equivalent-mutant problem ≈ our "consistency false alarm".
- **Formal anchor:** Lean FRO Comparator (<https://github.com/leanprover/comparator>); lean-eval
  (<https://github.com/leanprover/lean-eval>); lean4checker (<https://github.com/leanprover/lean4checker>).

## 30. Agent operating rules

- **Read this file first.** It is canonical and current as of `d302eb6`.
- Preserve the **source-fidelity vs formal-correctness** boundary and **judge-metrics ≠ theorem
  truth** (§3). Do **not** overclaim proof / mapping / Comparator / judge / promotion status.
- Do **not** create Lean files or formal mappings unless the task explicitly asks.
- Keep **live judge/API calls opt-in** (`run_judge.py --execute-api` only); never auto-call a model;
  never print/inspect API key values.
- Preserve the **blinding boundary** (§3.5) and the **pre-proof, non-mutating** source-review gate.
- Preserve the **public theorem / helper split** (§7.1) — also pinned in `AuditHarness.lean`'s header;
  never weaken a theorem statement to ease a proof.
- If a Lean statement changes, update the card / mapping / review / mutants / Comparator triple
  together; never change theorem statements or expected mutant labels silently.
- Treat Lean build success as *formal* success, Comparator success as *statement-audit* success, and
  judge success as *evidence* — none of them as source-fidelity certificates.
- Commits are **approval-gated**: do not commit/push until the user approves; touch exactly the files a
  task names; restore generated reports (`docs/{validation,mutation,pipeline}_report.md`,
  `docs/judge_inputs_dryrun/`) rather than committing churn; keep hardening commits separate from
  evidence-run commits.
