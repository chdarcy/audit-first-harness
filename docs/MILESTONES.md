# MILESTONES — implementation history

Chronological log of how the audit-first harness was built, milestone by milestone. This is the
**history**; the **stable design** lives in [`../ARCHITECTURE.md`](../ARCHITECTURE.md) (section
references below point there). Short commit hashes are given for traceability, not as an exhaustive
git history.

Versioning shorthand: **v0.1** = the audit & measurement spine; **v0.2** = the offline formal
gate/pipeline engineering; **v0.3** = the structured-judge source-fidelity evidence pipeline. The
closed-loop controller (ARCHITECTURE §12, §20.1) remains future research.

---

## v0.1 — audit & measurement spine

- **Initial harness** (`7cc9451`). Source cards (`docs/theorem_index.yaml`), the formal-mapping
  bridge (`docs/formal_mapping.yaml`), fidelity reviews + the human-approval *input* gate, blinded
  hash-provenanced mutation packages (`run_mutants.py --dry-run`), the opt-in live judge runner
  (`run_judge.py --execute-api`) + manual import, judge scoring (`score_judge.py`), the textual
  no-sorry check (`check_sorries.py`), Comparator triples with a real run on **PutCallParity**, and
  generated pipeline/validation/mutation reports.
- **First-steps docs** (`d453187`) — spelled out the `source.tex → theorem-card` path for new
  targets.
- **Judge-parsing hardening** (`a494c27`) — malformed-output reporting, verdict recovery, and
  parse-format metrics (ARCHITECTURE §9, §10.2).
- **ARCHITECTURE.md added** (`9ebe5db`) — the design document.

## v0.2 — offline formal gate & pipeline

- **Repo cleanup** before the gate work (`ea6e0d5`).
- **Offline promotion gate** (`e9e2d8c`) — `scripts/gate_decision.py`, a pure offline
  `PROMOTE / BLOCK / REVISE / HUMAN_REVIEW` decision (ARCHITECTURE §11).
- **Target-scoped pipeline runs** (`fe6f887`) — `rebuild_pipeline.py --target` (ARCHITECTURE §20.2).
- **Comparator-status writeback** (`f19ce73`) — explicit `comparator_status` into
  `formal_mapping.yaml`, with an honest sandbox-status vocabulary (ARCHITECTURE §13.4).
- **Kernel axiom audit** (`dbef69e`) — `check_axioms.py`, `#print axioms` ⊆ permitted set, no
  `sorryAx` (ARCHITECTURE §14).
- **Guarded provable-equivalence path** (`33a02fe`) — `PASS_PROVABLE_EQUIV` requires a *built*
  in-Lean equivalence lemma; `check_equivalence.py` (ARCHITECTURE §20.6).
- **TwoAssetMinVar worked target** (`1330531`) — the second worked target (ARCHITECTURE §19).
- **Lean theorem/helper module refactor** (`bf1a8c0`) — short source-facing theorem modules +
  `Helpers.lean` proof-engineering modules (ARCHITECTURE §5.1).
- **GoldIrrationalSqrtTwo reference target** (`092bbd0`) — a public gold-reference fixture wrapping
  Mathlib's `irrational_sqrt_two` (ARCHITECTURE §19.1).

## v0.3 — structured-judge evidence pipeline

- **1a — structured judge schema validator** (`7dae994`) — `validate_judge_schema.py`; the
  `schema_version: "0.3.0"` record and its `VALID / PARTIAL_RECOVERED / INVALID` classification
  (ARCHITECTURE §9.1).
- **1b — structured judge scoring** (`874a787`) — `score_judge.py --structured`; reliability metrics
  over the real/mutant answer key, schema validity reported separately (ARCHITECTURE §10.3).
- **1c — conservative judge-metric gate caps** (`64f1ab1`) — `gate_decision.py --judge-metrics`;
  structured metrics may only cap an otherwise-promotable target to `HUMAN_REVIEW`, never BLOCK or
  PROMOTE (ARCHITECTURE §11.5).
- **2a — structured judge-output export** (`32c5e71`) — `export_structured_judge_results.py`;
  un-blinds blinded judge results via the answer key into validated structured JSON, on the scoring
  side of the blinding boundary (ARCHITECTURE §10.4).
- **2b — offline structured-judge workflow runner** (`ba34aaf`) —
  `run_structured_judge_workflow.py`; chains export → validate → score → (optional) gate over
  existing judge results, offline and deterministic, separate from the formal pipeline
  (ARCHITECTURE §10.5).

## Documentation & recorded evidence

- **Documentation split** (`90ae0b5`) — separated the stable design (`ARCHITECTURE.md`) from this
  chronological log (`MILESTONES.md`); updated the stale "v0.1 experimental" wording to reflect the
  implemented v0.2/v0.3 layers; closed-loop controller still marked future.
- **Architecture gap analysis** (`8ecb2b9`) — added `docs/GAP_ANALYSIS.md`, an audit snapshot of
  what is implemented / partial / future, with a ranked next-step roadmap and acceptance criteria.
- **Recorded Comparator passes for all targets** (`ce5d8f3`) — ran the real Comparator with
  `--writeback-comparator-status` for **PutCallParity**, **TwoAssetMinVar**, and
  **GoldIrrationalSqrtTwo**; all three now record `comparator_status: PASSED_REAL_LANDRUN_BEST_EFFORT`
  (previously `NOT_RUN`). This is **formal Challenge/Solution Comparator evidence only** (kernel
  acceptance of statement equality under a bounded axiom set) — **not** source-`.tex` fidelity
  evidence. The status is conservative: `BEST_EFFORT` because `landrun` runs `--best-effort` and the
  Landlock ABI was not asserted ≥ 5 (ARCHITECTURE §13.4).
- **Structured pipeline status + gate freshness check** — `rebuild_pipeline.py --pipeline-status-out`
  emits a machine-readable `pipeline_status.v0.1` JSON (per-stage status + sha256 fingerprints of the
  target-relevant formal inputs); `gate_decision.py --pipeline-status` consumes it in preference to
  the markdown report, validating schema/target/required stages and **failing closed (BLOCK)** on a
  stale (fingerprint-mismatched), target-mismatched, malformed, or missing status. Closes the
  GAP_ANALYSIS "stale-report" risk for the structured path; the markdown fallback is preserved for
  backward compatibility. Formal stage evidence only — never source fidelity (ARCHITECTURE §11.3).
- **Expanded CI formal-layer coverage** — the `lean-build` CI job now builds **every theorem module
  and every Challenge/Solution triple for all three targets** (not just the PutCallParity triple) and
  runs `check_axioms.py` (kernel/axiom audit, all targets) and `check_equivalence.py` (all
  `NOT_REQUIRED` while every `equivalence: null`). Green CI now catches a broken triple or an axiom
  regression, not just Python-test failures. The **real Comparator** (landrun sandbox) is **not** run
  in CI — its binaries are not installed — so Comparator *acceptance* and `comparator_status`
  writeback stay local/WSL; CI proves the triples *build*, which is formal evidence only, not source
  fidelity. Reduces the GAP_ANALYSIS CI-undercoverage risk.
- **Blinding-boundary regression tests** — `scripts/test_blinding_boundary.py` (in CI) enforces the
  answer-key separation (ARCHITECTURE §9): a **static** guard asserts `run_judge.py` and
  `import_manual_judge_results.py` carry no code-level `_manifest` reference (docstrings excepted) and
  read the membership sidecar `_targets.yaml`; a **hermetic runtime/poison** test assembles fresh
  packages and proves the blinded `--dry-run` output is identical whether `_manifest.yaml` is valid,
  poisoned with contradictory labels, or removed; and a positive check confirms `score_judge.py` /
  `export_structured_judge_results.py` still read `_manifest.yaml` (un-blinding stays scoring/export
  side). Closes the "convention-enforced, not test-enforced" risk before any real judge round.
- **First real judge calibration run** — ran the blinded judge live (opt-in, `--execute-api`) on
  **GoldIrrationalSqrtTwo** (10 packages: 1 real / 7 discriminative / 2 consistency) with
  `openai` / `gpt-4o` @ temperature 0. Result: **discriminative recall 1.0** (all 7 planted defects
  rejected), **consistency false-alarm rate 0.0**, real mapping accepted, **10/10 clean parses**,
  structured schema **VALID 10/10**. The committed `docs/JUDGE_EVIDENCE_SUMMARY.md` records the
  metrics; raw replies / scored / structured artifacts stay gitignored. This is the harness's first
  **empirical judge-reliability** evidence (not theorem truth); the blinded runner read only
  `_targets.yaml`, with un-blinding on the scoring side via `_manifest.yaml`. Also fixed a
  `.gitignore` gap so generated `docs/judge_results/*.json` exports are excluded too.
- **Broadened judge calibration across all targets** — ran the same live, blinded, scored
  calibration (`gpt-4o` @ temp 0, opt-in) on **all three** targets: PutCallParity (6),
  TwoAssetMinVar (9), GoldIrrationalSqrtTwo (10) = **25 packages / 25 API calls**. Aggregate
  **discriminative recall 0.875 (14/16)**, **consistency false-alarm rate 0.0**, all real mappings
  accepted, **25/25 clean parses & schema-VALID**. Per-target recall 0.667 / 0.833 / 1.0 — the judge
  is strong but **imperfect**: it missed `PCP-D2` (swap-variable) and `TAM-D1` (drop-hypothesis),
  which is calibration evidence about the judge (keep automation confidence capped / require human
  review), not a refutation of those mappings. Appended to `docs/JUDGE_EVIDENCE_SUMMARY.md`; raw
  artifacts gitignored; blinding preserved.
- **Source-fidelity review decision layer** — `scripts/source_review_decision.py`, the **pre-proof
  candidate gate** (ARCHITECTURE §11.4), distinct from the post-Comparator promotion gate. It
  consumes the structured judge evidence (the real candidate's verdict + concerns) and the judge's
  calibration over the target's mutants, and emits `SOURCE_REVIEW_PASS / HUMAN_REVIEW / REVISE /
  BLOCK` with an explicit reasons list: real `FAIL` → REVISE; `UNPARSEABLE` / schema-INVALID /
  missing → BLOCK; `WARN` or high/critical concerns → HUMAN_REVIEW; and any calibration imperfection
  (recall < 1.0, a false acceptance, a consistency false alarm, or any invalid/unparseable record)
  caps an otherwise-PASS to HUMAN_REVIEW. This operationalises the judge: a `FAIL`/`WARN` on a real
  mapping blocks/revises *before* hard proof work, and mutant misses cap automation confidence (e.g.
  PutCallParity's real-run recall 0.667 → HUMAN_REVIEW). It is **source-fidelity review evidence,
  not theorem truth**: it never calls a model, never edits Lean or mappings, and never overrides the
  formal layers. No Lean changed; the `AuditHarness/<Target>.lean` + helper-module split (CLAUDE.md,
  §5.1) is preserved as the layout for future targets that this gate decides whether to start.
- **Final architecture completion audit (before Markowitz)** — re-verified `ARCHITECTURE.md`,
  `docs/GAP_ANALYSIS.md`, `README.md`, `CLAUDE.md`, and the implemented scripts against the milestone
  history. Refreshed `GAP_ANALYSIS.md`: the executive summary, the live-judge / promotion-gate rows,
  the §4b/§4c notes, the per-target matrix, Risk #10, and the acceptance criteria no longer claim
  "no committed real judge run" / "the gate still reads a markdown report" / "no target promotes" —
  acceptance criteria **1–3 are satisfied** (CI formal layer, Comparator writeback, real judge runs),
  and the only unmet criterion (a *committed PROMOTE*) is **deliberately** unmet (raw judge evidence
  gitignored; the pre-proof source-fidelity gate holds PutCallParity/TwoAssetMinVar at HUMAN_REVIEW
  given recall < 1.0). `ARCHITECTURE.md` stayed stable apart from one accuracy fix (§11.4 now names
  `source_review_decision.py` as the implemented candidate gate). Honest conclusion: the **audit-first
  harness exists and is exercised end-to-end**, but it is **not** a fully agentic closed-loop system —
  the closed-loop controller, non-LLM signal, multi-judge ensemble, vacuity/unused-hypothesis checks,
  and real Comparator-in-CI remain future/open. No Lean / theorem / Comparator / mapping / mutant /
  prompt changes.
- **Generic source-formalisation records** — added a source-agnostic layer that documents *how an
  informal source claim becomes a proposed formal target* before any theorem card / mapping / Lean:
  `docs/source_formalizations/` (a `template.yaml` skeleton + `README.md`) and
  `scripts/validate_source_formalization.py` (+ unit tests, in CI). A record captures the source
  metadata, informal claim, symbols + intended types, explicit/implicit/standard/omitted assumptions,
  conclusion shape, abstraction & representation choices, ambiguities/risks, and a proof
  decomposition into subtargets — making the **semantic alignment** between informal source and formal
  statement explicit and reviewable up front (the hard part of autoformalisation, beyond Lean
  syntax). The validator checks **completeness/structure only** — never mathematical truth, never the
  source's correctness; it runs no model/API and never reads or edits Lean. It **sits before** the
  theorem card and formal mapping and does not replace them, the fidelity review, or the
  source-fidelity review gate. **Generic infrastructure only: no real source-specific record was
  added (template only), and no external/uploaded source content was read, imported, or encoded.**
- **First content-bearing source intake (Markowitz inventory)** — the first use of the intake layer on
  a real source. Added `docs/source_inventories/` (a generic `README.md` + the content-bearing
  `markowitz_lecture_notes.yaml`, `record_type: source_theorem_inventory`). The inventory triages the
  source into **12 candidate targets** with dependencies, difficulty, and **separately recorded
  source-fidelity vs proof risks**; it recommends a conservative first pass on the **algebraic** layer
  (`MK-000` scaffolding, then `MK-003` — the `D = BC − A² > 0` Cauchy–Schwarz lemma — as the first
  proof target) and explicitly **defers** the probabilistic foundations (`MK-001/002`), the full
  KKT/optimisation uniqueness, and the **CAPM** result (relies on unstated equilibrium economics). The
  central recorded decision is the **probabilistic↔algebraic abstraction boundary**. This is a
  source-reading artifact only — **nothing is proved, mapped, or verified**; no Lean, theorem card,
  mapping, mutant, or Comparator file was created, and the generic source-agnostic
  `docs/source_formalizations/` layer was left untouched. The source TeX is committed at
  `examples/markowitz_lecture_notes/source.tex` and the inventory at
  `docs/source_inventories/markowitz_lecture_notes.yaml` (commit `1b3b6a2`); this was **source intake
  only** (the working-tree root copy `markowitz_lecture_notes.tex` is intentionally left untracked).
- **Refresh docs after Markowitz source intake** — brought the front-matter docs back in sync with the
  repo. Rewrote `README.md` as the current front door (status, the four-layer pipeline, Markowitz
  intake state, how to run checks, how to add a source); updated `ARCHITECTURE.md` §4 to include
  `docs/source_inventories/` before `docs/source_formalizations/` and to distinguish inventory vs
  source-formalisation record vs theorem card vs formal mapping, recording that Markowitz is at the
  source-inventory stage only with `MK-000`/`MK-003` the next (not-yet-created) promoted records;
  added `docs/ROADMAP.md` for the active next steps; and **archived** `docs/GAP_ANALYSIS.md` as a
  historical snapshot (no longer the active roadmap). Docs-only: no Lean, theorem card, mapping,
  mutant, Comparator, script, or source-content change.
- **Markowitz MK-003 theorem-card metadata** — promoted the first Markowitz proof target from its
  `ready_for_card` source-formalisation record into a source-side **theorem card**:
  `docs/theorem_index.yaml` entry `thm:markowitz_lemma_d_positive` (Lemma D positivity — `C>0`,
  `B>0`, `D=BC−A²>0` under SPD `Sigma` and `mu` not proportional to the ones vector). Source-side
  only, following the `auto`/`curated` convention (judge-visible fields kept to clean source maths;
  planning/status in non-judge-visible `notes`). **No `formal_mapping.yaml` entry was added**: a
  draft/unimplemented mapping cannot pass `validate_mapping.py` (which requires an existing Lean
  declaration, Comparator config, and review file, with no draft state). Recorded the proposed —
  **not created** — future target `MarkowitzLemmaDPositive`. No Lean, proof, Comparator, judge
  package, or promotion gate exists for this target; the concrete Lean encoding remains open;
  MK-002 / probabilistic covariance deferred; dual-system uniqueness split off. The smallest
  follow-up (a draft-mapping lifecycle in `validate_mapping.py`) is recorded in `docs/ROADMAP.md`.

---

## Invariants preserved across all milestones

These are design constraints (see ARCHITECTURE.md), repeated here so the history reads against them:

- Formal correctness ≠ source fidelity; judge metrics ≠ theorem truth (§0).
- The GPT judge is a calibrated source-fidelity reviewer, **not** a theorem oracle.
- Live judge/API calls are **opt-in only** (`run_judge.py --execute-api`); nothing else calls a model.
- `run_judge.py` and `import_manual_judge_results.py` stay **blinded** (read `_targets.yaml`, never
  the answer key); un-blinding via `_manifest.yaml` happens only on the scoring/export side.
- `rebuild_pipeline.py` is the **formal** pipeline; the structured-judge workflow is separate.
- Judge metrics can cap to `HUMAN_REVIEW` through the gate but cannot override a formal failure.
- The Comparator compares **Challenge vs Solution**, not `.tex` source vs Lean.
- `PASS_PROVABLE_EQUIV` is guarded by an in-Lean equivalence check.
