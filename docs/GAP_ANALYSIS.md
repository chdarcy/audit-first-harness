# GAP_ANALYSIS — archived audit snapshot

> **Status: archived as an active roadmap after `1b3b6a2`.**
> This document is retained for **provenance/history** and is **no longer the authoritative
> current-state roadmap**. For current project status see [`../README.md`](../README.md) and
> [`../ARCHITECTURE.md`](../ARCHITECTURE.md); for active next steps see [`ROADMAP.md`](ROADMAP.md);
> for the dated build history see [`MILESTONES.md`](MILESTONES.md). The assessments below were
> accurate at the time of writing (and were updated through the final completion audit, `c519dc5`);
> later work — the Markowitz source intake (`1b3b6a2`) and this doc refresh — is reflected in
> README/ARCHITECTURE/MILESTONES, not here.

**Type:** audit snapshot (documentation only), now archived. **Baseline commit:** `90ae0b5` (Separate
architecture from milestone history). **Against:** [`../ARCHITECTURE.md`](../ARCHITECTURE.md);
history in [`MILESTONES.md`](MILESTONES.md).

This document audits the repository against the goals in `ARCHITECTURE.md`. It changes no code,
Lean, mappings, mutants, Comparator configs, judge prompts, or generated artifacts, and ran no
model/API. It is a point-in-time assessment; re-run the audit after material changes.

---

## 1. Executive summary

**Have we met the goals in ARCHITECTURE.md?** **Yes, for the current audit-first harness.** The
audit/measurement spine and the structured-judge evidence pipeline are **implemented and exercised**;
the formal layer (build / no-sorry / kernel axiom audit / Comparator / guarded equivalence) is built
and, for all three targets, the **Comparator passes are recorded** in the ledger
(`PASSED_REAL_LANDRUN_BEST_EFFORT`, `ce5d8f3`). The judge has been **run live** (opt-in) on all three
targets and scored (`gpt-4o`: aggregate discriminative recall **0.875**, false-alarm rate **0.0**,
25/25 clean parses — strong but **imperfect**; it missed `PCP-D2` and `TAM-D1`). The judge is now
**operational** as a pre-proof source-fidelity review gate (`source_review_decision.py`), and the
promotion gate consumes a fingerprint-checked structured pipeline status. CI runs the full formal
Lean layer for all targets plus a blinding-boundary regression test.

This **is** an audit-first, anti-drift harness — it audits, reports, scores, and **gates** (both the
pre-proof source-fidelity gate and the post-Comparator promotion gate). It is **not** a fully
agentic anti-drift system: the closed-loop controller that would let judge output *drive* statement
revision and proof attempts remains **future research**, as do a non-LLM alignment signal, a
multi-judge ensemble, and vacuity / unused-hypothesis checks. Honest residuals: the judge is
imperfect (so its accept signal is trust-capped, not authoritative); the **real Comparator run** is
local/WSL only (its binaries are not in CI); and there is no **committed PROMOTE** — by design, since
raw judge evidence is gitignored and the source-review gate correctly requires human review where
calibration is imperfect.

**Ready for Markowitz?** **Yes — Markowitz work may begin now under the guarded audit workflow:** add
each target as the `AuditHarness/<Target>.lean` public theorem module + `Helpers.lean` proof module
(CLAUDE.md / §5.1, never weakening the statement), run the **pre-proof source-fidelity review gate**
before hard proof work, then the formal layers and the promotion gate — with the boundaries below
held throughout (judge ≠ oracle; judge metrics ≠ theorem truth; the source-review gate never edits
Lean; no judge PASS overrides a formal failure).

> **Final completion audit (this milestone).** Re-verified against the implementation and milestone
> history. Since the original baseline snapshot (`8ecb2b9`) these gaps are **closed**: Comparator
> writeback (`ce5d8f3`); structured pipeline status + gate freshness (`9a42747`); expanded formal CI
> (`d31c245`); blinding-boundary regression tests (`663fd19`); the first + broadened real judge
> calibration (`f4e4336`, `598f35f`); and the source-fidelity review decision layer (`73b262b`).
> Still open / future (see §5, §7): a stronger judge / ensemble where recall < 1.0; real
> Comparator-in-CI; the closed-loop controller; and the other §20 research items. The per-row
> annotations below reflect the **current** state.

| Layer | Status |
|---|---|
| Source→Lean traceability (cards / mapping / reviews) | **Implemented** |
| Formal correctness (build, no-sorry, axiom audit, Comparator architecture) | **Implemented** |
| Comparator status writeback (recorded real pass in the ledger) | **Implemented** (all 3 `PASSED_REAL_LANDRUN_BEST_EFFORT`, `ce5d8f3`) |
| Blinded judge packages / manual import / live opt-in | **Implemented** |
| Structured-judge pipeline (schema / scoring / gate caps / export / workflow) | **Implemented** |
| Promotion gate | **Implemented** (+ fingerprint-checked structured pipeline status; pre-proof source-fidelity gate also added) — no committed PROMOTE, by policy |
| Empirical judge reliability (real run scored & committed) | **Broadened to all 3 targets** (gpt-4o: aggregate recall 0.875 / FAR 0.0; per-target 0.667 / 0.833 / 1.0; see `JUDGE_EVIDENCE_SUMMARY.md`) — judge is strong but imperfect; vary models/seeds + grow suites next |
| Closed-loop controller, non-LLM signal, ensemble, vacuity/unused-hyp checks, scaling | **Future research** |

---

## 2. Architecture-goal coverage matrix

Risk = impact if left as-is on the harness's anti-drift claim.

| Architecture goal | Status | Implemented evidence | Remaining gap | Risk | Recommended next action |
|---|---|---|---|---|---|
| Source-to-Lean traceability | Implemented | cards (`theorem_index.yaml`) + mapping (`formal_mapping.yaml`) + reviews for all 3; `validate_mapping` PASS | — | Low | Keep `validate_mapping` in CI (done) |
| Formal correctness layer | Implemented | `lake build` 1823 jobs; pipeline orchestrates build/no-sorry/axiom/equiv/comparator; **CI builds all theorem modules + all 6 triples** | real Comparator stays local/WSL (binaries not in CI) | Low (was Med) | Comparator-in-CI only if toolchain provisioned |
| No-sorry / no-admit enforcement | Implemented | `check_sorries.py` (9 files, Challenges excluded); in CI | textual heuristic only | Low | (covered by axiom audit) |
| Kernel / axiom audit | Implemented | `check_axioms.py`: all 3 ⊆ `{propext,Quot.sound,Classical.choice}`, no `sorryAx`; **now run in CI** | — | Low (was Med) | — |
| Comparator Challenge/Solution architecture | Implemented | triples for all 3; real run returned "okay" for all 3; **CI now builds all 6 Challenge/Solution modules** | real Comparator acceptance still local/WSL (binaries not in CI) | Low (was Med) | Comparator-in-CI only if toolchain provisioned |
| Comparator status writeback | **Implemented** (`ce5d8f3`) | real writeback run; all 3 record `PASSED_REAL_LANDRUN_BEST_EFFORT` | conservative `BEST_EFFORT` (landrun `--best-effort`, ABI not asserted ≥5) | Low | optionally confirm ABI ≥5 for `PASSED_REAL_LANDRUN` |
| Formal mapping ledger | Implemented | `formal_mapping.yaml` (3 targets, verdict/equivalence/comparator_status/approval) | — | Low | — |
| Theorem-card index | Implemented | `theorem_index.yaml` (3 cards) | — | Low | — |
| Fidelity reviews | Implemented | 3 reviews with approval frontmatter; `validate_mapping` cross-checks | approvals are coarse (single bool + name) | Med | Per-rubric-axis / signed reviews |
| Blinded judge package generation | Implemented | `run_mutants --dry-run` → 25 packages; hash provenance; leak checks | — | Low | — |
| Manual judge import | Implemented | `import_manual_judge_results.py` (blinded, hash-checked) | never exercised end-to-end with real replies | Med | One real manual round |
| Live judge opt-in path | Implemented | `run_judge.py --execute-api`; **run live on all 3 (gpt-4o), scored**, evidence in `JUDGE_EVIDENCE_SUMMARY.md` | raw replies gitignored (not committed) | Low (was Med) | broaden models/seeds |
| Structured judge schema | Implemented | `validate_judge_schema.py` + tests | — | Low | — |
| Structured judge scoring | Implemented | `score_judge.py --structured` + tests | only fixture-scored | Med | Score a real run |
| Structured judge metric gate caps | Implemented | `gate_decision.py --judge-metrics` (cap→HUMAN_REVIEW only) + tests | optional path; gate's primary judge signal is still legacy `scored.yaml` | Med | Unify on the structured summary |
| Structured judge-output export | Implemented | `export_structured_judge_results.py` + tests | only fixture-exercised | Low | — |
| Offline structured-judge workflow runner | Implemented | `run_structured_judge_workflow.py` + tests | needs a real `judge_results` input to be useful | Low | — |
| Promotion gate | Implemented | `gate_decision.py` (PROMOTE/BLOCK/REVISE/HUMAN_REVIEW) + tests; `--pipeline-status` consumes a validated, fingerprint-checked `pipeline_status.v0.1` (fail-closed) | markdown remains the unvalidated default when `--pipeline-status` is not passed | Low (was High) | use `--pipeline-status` in promotion runs |
| Target-scoped rebuild pipeline | Implemented | `rebuild_pipeline.py --target` + tests | — | Low | — |
| Guarded PASS_PROVABLE_EQUIV | Implemented | `check_equivalence.py`; gate downgrades bare claims | unexercised (no target uses it; all `equivalence: null`) | Low | Add a target that needs it |
| Worked targets | Implemented | PutCallParity, TwoAssetMinVar | only 2 finance targets | Med | More targets (§7) |
| Gold reference target | Implemented | GoldIrrationalSqrtTwo (wraps Mathlib `irrational_sqrt_two`) | — | Low | — |
| Artifact / generated-output policy | Implemented | `.gitignore` excludes judge_results/promotion/evidence; reports regenerable | reliance on discipline (manual restore) | Low | (optional) make-clean target |
| CI coverage | **Mostly** (was Partial) | Python tests + ledger + dry-run + no-sorry + report; **Lean CI builds all theorem modules + all 6 triples and runs `check_axioms` + `check_equivalence`** | real Comparator run not in CI (binaries unavailable); no real judge path in CI | Low (was High) | Comparator-in-CI if/when toolchain provisioned |
| Closed-loop controller | Future | §12, §20.1 (clearly marked future) | not implemented | n/a (future) | Roadmap item |
| Non-LLM alignment signal | Future | §20.3 | not implemented | n/a | Roadmap item |
| Multi-judge ensemble | Future | §20.8 | not implemented | n/a | Roadmap item |
| Vacuity / unused-hypothesis checks | Future | §20.4, §20.5 | named as risks but unchecked | Med | Roadmap item |
| Markowitz mini-suite scaling | Future | §0.1 | only 3 targets | n/a | Roadmap item |

---

## 3. Target-by-target audit

Legend: ✅ present/passing · ⚠️ present but stale/unrun · ❌ absent.

| Check | PutCallParity | TwoAssetMinVar | GoldIrrationalSqrtTwo |
|---|---|---|---|
| source `.tex` | ✅ `examples/put_call_parity/` | ✅ `examples/two_asset_minvar/` | ✅ `examples/gold_irrational_sqrt_two/` |
| theorem card | ✅ `thm:putcall` | ✅ `thm:two_asset_minvar` | ✅ `thm:gold_irrational_sqrt_two` |
| formal mapping | ✅ verdict PASS | ✅ verdict PASS | ✅ verdict PASS |
| Lean theorem | ✅ `put_call_payoff_parity` | ✅ `two_asset_min_variance_weight` | ✅ `gold_irrational_sqrt_two` |
| helper/theorem split (§5.1) | ✅ `Helpers.lean` | ✅ `Helpers.lean` | ✅ N/A (one-line wrapper; no helper needed) |
| Challenge/Solution/comparator triple | ✅ | ✅ | ✅ |
| Comparator status | ✅ `PASSED_REAL_LANDRUN_BEST_EFFORT` (`ce5d8f3`) | ✅ `PASSED_REAL_LANDRUN_BEST_EFFORT` (`ce5d8f3`) | ✅ `PASSED_REAL_LANDRUN_BEST_EFFORT` (`ce5d8f3`) |
| fidelity review | ✅ approved | ✅ approved | ✅ approved |
| mutant set | ✅ 5 (3 disc / 2 cons) | ✅ 8 (6 / 2) | ✅ 9 (7 / 2) |
| structured-judge compatibility | ✅ answer-key resolves | ✅ | ✅ |
| axiom-audit compatibility | ✅ within permitted | ✅ | ✅ |
| source-fidelity review (pre-proof gate) | ⚠️ HUMAN_REVIEW (real-run recall 0.667) | ⚠️ HUMAN_REVIEW (recall 0.833) | ✅ SOURCE_REVIEW_PASS (recall 1.0) |
| committed PROMOTE | ❌ none, by policy (raw judge evidence gitignored; calibration caps PCP/TAM) | ❌ same | ❌ none committed (Gold is the only PASS candidate) |

**Stale/missing evidence to flag:** the only committed judge artifact is `PutCallParity_preview.yaml`
(a dry-run preview). A local `PutCallParity.yaml`/`_scored.yaml` exists but is **gitignored mock**
from a compatibility test — not real judge data. (As of `ce5d8f3`, all three targets **do** have a
written-back real Comparator pass; what is still missing is a committed real *judge* run.)

---

## 4. Pipeline audit

### 4a. Formal pipeline (`rebuild_pipeline.py`)
- **Does:** orchestrates `card_and_mapping`, `judge_packages`, `build`, `no_sorry`, `axiom_audit`,
  `equivalence_check`, `comparator`; writes `pipeline_report.md`; supports `--target` and
  opt-in `--with-*`; can write back Comparator status (target-scoped).
- **Does not:** run the gated heavy stages (build/comparator/axiom/equiv) by default; they are
  SKIPPED unless flags are passed. CI runs the default → those stages are SKIPPED.
- **Can fail silently:** a SKIPPED stage "never fails the run", so a green default run says little
  about formal correctness. (A stale markdown `pipeline_report.md` consumed downstream is mitigated
  on the gate side by the fingerprint-checked `--pipeline-status` path, §4c.)
- **Improve next:** `--pipeline-status-out` now emits a structured `pipeline_status.v0.1` (per-stage
  status + sha256 input fingerprints); still to do — a CI Lean job that runs build + axiom_audit
  (+ comparator where feasible) for all targets.

### 4b. Structured-judge evidence pipeline (export → validate → score → workflow)
- **Does:** un-blinds judge results into `schema_version 0.3.0` records, validates, scores
  reliability metrics, and chains them offline (`run_structured_judge_workflow.py`). Pure, no API.
- **Does not:** produce anything without an existing `judge_results/<T>.yaml`. The live runs produced
  one (gitignored) for **all three** targets, so the layer has now been **exercised on real data**
  (the structured workflow ran per target; export VALID 6/9/10, recall 0.667 / 0.833 / 1.0).
- **Can fail silently:** if fed an empty/missing results file it (correctly) fails or skips — no
  longer a concern in practice now that real results exist for all three targets.
- **Improve next:** consider making the structured summary the gate's primary judge signal (today the
  gate's primary signal is the legacy `scored.yaml`).

### 4c. Promotion gate (`gate_decision.py`)
- **Does:** deterministic, ordered BLOCK/REVISE/HUMAN_REVIEW/PROMOTE; consumes mapping, review,
  legacy `scored.yaml`, manifest provenance, and formal status; optionally caps on the structured
  summary (`--judge-metrics`).
- **Does:** with `--pipeline-status` it consumes a structured `pipeline_status.v0.1` (schema/target
  validated + sha256 fingerprint-checked for freshness), preferred over the markdown report and
  **failing closed (BLOCK)** on a stale/mismatched/missing status; without it, it parses the markdown
  report (unvalidated fallback).
- **Can fail silently:** only on the **markdown fallback** (when `--pipeline-status` is not passed) —
  it trusts whatever `pipeline_report.md` says. The structured path detects staleness via input
  fingerprints. A `scored.yaml` now exists (gitignored) for all three targets from the live runs; a
  committed PROMOTE is still deliberately **not** produced — raw judge evidence is gitignored by
  policy, and the pre-proof source-fidelity gate (`source_review_decision.py`) caps the imperfect-
  calibration targets (PutCallParity, TwoAssetMinVar) to HUMAN_REVIEW.
- **Improve next:** make `--pipeline-status` the default in promotion runs; optionally extend the
  freshness check to the markdown fallback.

### 4d. Artifact policy
- **Does:** `.gitignore` keeps `judge_results/*.yaml` (except `*_preview.yaml`), `promotion/*.yaml`,
  and `/evidence/` out of commits; reports are regenerable and routinely restored.
- **Does not:** automate cleanup — relies on the operator running `git checkout --` after generating.
- **Improve next:** a `make clean-generated` / script target to restore/remove generated outputs.

### 4e. CI
- **Does:** runs all Python unit tests, `validate_mapping`, `run_mutants --dry-run`,
  `check_sorries`, the default `rebuild_pipeline`, and a Lean job that builds **every theorem module
  and every Challenge/Solution triple for all three targets**, then runs `check_axioms` (kernel/axiom
  audit, all targets) and `check_equivalence` (all `NOT_REQUIRED` while every `equivalence: null`).
- **Does not:** run the **real Comparator** (the `landrun`/`comparator`/`lean4export` binaries are not
  installed in CI) — CI proves the triples *build*, not that the Comparator accepts them; nor does it
  exercise any real judge path.
- **Can fail silently:** Comparator acceptance and `comparator_status` writeback are still local/WSL,
  so a Comparator-only regression (one that still compiles) would not be caught by CI.
- **Improve next:** if/when the Comparator toolchain can be provisioned in CI (or a hermetic shim is
  available), add a real Comparator job; until then it stays local/WSL.

---

## 5. Architectural weaknesses / risks

1. **Comparator "validated but not recorded." — CLOSED by `ce5d8f3`.** Previously all three
   `comparator_status: NOT_RUN` (validated interactively but never written back). A real writeback run
   now records `PASSED_REAL_LANDRUN_BEST_EFFORT` for all three, so the ledger reflects the verified
   formal pass. (Residual: the status is conservative `BEST_EFFORT`; it is formal Challenge/Solution
   evidence only, not source fidelity.) **(was High → resolved)**
2. **Infrastructure-rich, evidence-poor judging. — REDUCED (broadened to all targets).** Real
   (opt-in) rounds were run across all three targets with `gpt-4o` @ temp 0 (25 packages):
   **aggregate discriminative recall 0.875 (14/16)**, **consistency false-alarm rate 0.0**, all real
   mappings accepted, **25/25 clean parses & schema-VALID** (see `JUDGE_EVIDENCE_SUMMARY.md`; raw
   artifacts gitignored). Per-target recall 0.667 / 0.833 / 1.0. The central claim ("the judge can
   catch planted defects") now has multi-target empirical support — **but the judge is imperfect**:
   it missed `PCP-D2` (swap-variable) and `TAM-D1` (drop-hypothesis). That is calibration evidence
   about the *judge* (keep automation confidence capped / require human review), not a refutation of
   those mappings. Residual: one model / temperature / round, small mutation suites — vary
   models/seeds and grow suites before generalising. **(was High → Med, pending breadth + a stronger
   judge or ensemble)**
3. **Gate consumes a markdown report. — REDUCED.** By default `gate_decision.py` still parses
   `pipeline_report.md`, but `--pipeline-status` now consumes a structured `pipeline_status.v0.1`
   that is schema/target-validated and **sha256 fingerprint-checked for freshness**, failing closed
   (BLOCK) on any stale / mismatched / missing status. Residual: the markdown path remains the
   unvalidated default when `--pipeline-status` is not passed. **(was High → low for the structured path)**
4. **Two parallel judge representations.** The legacy blinded `scored.yaml` (per-`blind_id`) and the
   v0.3 structured JSON coexist; the gate's primary judge signal is still legacy, with the structured
   summary as an optional cap. This is functional but risks UX/maintenance fragmentation and two
   code paths to keep in sync. **(Med)**
5. **Coarse human approval.** Approval is a single `human_approved: true` + a reviewer-name string in
   mapping and review frontmatter. No per-axis sign-off, no signature, no enforced reviewer identity.
   A rubber-stamp is indistinguishable from a careful review. **(Med)**
6. **Small, single-author mutation suites** (3/6/7 discriminative). Adequate as a smoke test, thin as
   a benchmark; no inter-rater design and limited operator diversity. **(Med)**
7. **Vacuity / unused-hypothesis risks uncovered.** §1 and §20.4/§20.5 name these drift modes, but
   nothing checks for them; a vacuous or hypothesis-padded statement could pass today. **(Med)**
8. **Blinding boundary is convention-enforced, not test-enforced. — CLOSED.** `test_blinding_boundary.py`
   (in CI) now enforces it: a static guard asserts `run_judge.py`/`import_manual_judge_results.py`
   contain no code-level `_manifest` reference (docstrings excepted) and reference `_targets.yaml`;
   a hermetic runtime test assembles fresh packages and proves the blinded `--dry-run` output is
   identical whether `_manifest.yaml` is valid, poisoned with contradictory labels, or removed; and
   a positive check confirms `score_judge`/`export` still read `_manifest`. A future edit that leaks
   the answer key into the runner/importer now fails CI. **(was Low–Med → resolved)**
9. **CI under-covers the formal layer. — REDUCED.** CI now builds every theorem module and all six
   Challenge/Solution modules for all three targets and runs `check_axioms` + `check_equivalence`, so
   a broken triple or an axiom regression is caught. Residual: the **real Comparator** (landrun
   sandbox) is not run in CI — its binaries are not installed — so Comparator *acceptance* and
   `comparator_status` writeback remain local/WSL. **(was High → Low; Comparator-in-CI still open)**
10. **ARCHITECTURE.md post-split stability:** good. The version/diary wording was removed; remaining
    forward-looking statements (§20 future items, §12/§20.1 closed loop) are accurately marked future.
    (§11.3's structured pipeline status is now **implemented**, `9a42747`.) Re-verified in this final
    audit: ARCHITECTURE.md needs **no edits** — its "current" claims still hold and the closed-loop
    controller is correctly future. No material stale "current" claims found. **(Low)**

---

## 6. What is genuinely complete (treat as done unless bugs appear)

- The ledger triad (cards ↔ mapping ↔ reviews) and `validate_mapping`.
- Blinded mutation package assembly with hash provenance and leak/whitelist checks.
- The structured-judge **code** layer: schema validator, scorer, gate caps, exporter, workflow
  runner — all with green unit tests and clean separation from the formal pipeline.
- The promotion-gate **decision logic** (ordered rules; conservative judge caps; never lets judge
  metrics override a formal failure).
- The Lean library + Comparator **triples** (they build; real Comparator accepts all three).
- The kernel axiom audit and the no-sorry check.
- The guarded `PASS_PROVABLE_EQUIV` mechanism (code + tests), even though unexercised by a target.
- The documentation split (`ARCHITECTURE.md` stable; `MILESTONES.md` chronological).
- Artifact policy via `.gitignore`.

---

## 7. What is not complete

**Must do before claiming a robust audit harness:**
- ~~Write back a real `comparator_status` for each target~~ — **done** (`ce5d8f3`; all three record
  `PASSED_REAL_LANDRUN_BEST_EFFORT`).
- ~~Run the judge for real once, score it, and record discriminative-recall / FAR~~ — **done and
  broadened to all 3 targets** (gpt-4o: aggregate recall 0.875, FAR 0.0, 25/25 clean parses; misses
  on `PCP-D2` / `TAM-D1`; `JUDGE_EVIDENCE_SUMMARY.md`). Broaden across models / seeds next.
- ~~Make judge results operational in the workflow (real-mapping `FAIL`/`WARN` blocks/revises before
  proof work; mutant misses cap automation confidence and trigger review/stronger calibration)~~ —
  **done** (`scripts/source_review_decision.py`, the pre-proof candidate gate, §11.4): emits
  `SOURCE_REVIEW_PASS / HUMAN_REVIEW / REVISE / BLOCK` with reasons; `FAIL`→REVISE,
  `UNPARSEABLE`/INVALID→BLOCK, `WARN`/high-critical→HUMAN_REVIEW, and any calibration imperfection
  caps an otherwise-PASS to HUMAN_REVIEW (source-fidelity evidence only; never edits Lean, never
  calls a model, never overrides formal checks). Still open: wire it into a one-command target
  workflow and a stronger judge / ensemble for the targets where recall < 1.0.
- ~~Emit a structured `pipeline_status.json` and have the gate consume it with a freshness check.~~ —
  **done** (`rebuild_pipeline.py --pipeline-status-out` / `gate_decision.py --pipeline-status`,
  sha256 fingerprint-checked, fail-closed).
- ~~Expand CI to build all Comparator triples and run the axiom audit.~~ — **done** (CI builds all
  theorem modules + 6 triples and runs `check_axioms` + `check_equivalence`; real Comparator stays
  local/WSL).

**Should do before scaling targets:**
- Strengthen human approval (per-axis / signed) and grow mutation suites.
- Decide the canonical judge representation (legacy vs structured) and converge the gate on it.
- ~~Add a test that enforces the blinding boundary (no `_manifest` access in runner/importer).~~ —
  **done** (`scripts/test_blinding_boundary.py`, static + runtime/poison, in CI).
- ~~Structurally represent the informal-source → theorem-card bridge for hard multi-step targets.~~ —
  **done** (`docs/source_formalizations/` + `scripts/validate_source_formalization.py`): a generic,
  source-agnostic **source-formalisation record** captures symbols, assumptions, conclusion shape,
  abstraction choices, ambiguities, and a proof decomposition *before* the theorem card / mapping.
  The validator checks **completeness and structure only** — **mathematical correctness still
  requires the human fidelity review and the source-fidelity review gate**; it asserts no truth, runs
  no model, and edits no Lean. (No real record committed yet — template only.)

**Future research (as ARCHITECTURE.md states):**
- Closed-loop controller; non-LLM (FormalAlign-style) signal; multi-judge ensemble;
  vacuity & unused-hypothesis checks; dependency-graph blueprint; Markowitz mini-suite.

**Nice to have:**
- `make clean-generated`; a one-command "audit a target" wrapper; a target needing real
  `PASS_PROVABLE_EQUIV` to exercise that path.

---

## 8. Recommended next milestones (ranked)

1. **Comparator-status writeback for all targets.** *Why:* unblocks PROMOTE; makes the ledger
   truthful. *Files:* `docs/formal_mapping.yaml` (writeback output), evidence (gitignored). *Risk:*
   Med. *Type:* Python-run + data (uses existing `--writeback`; no logic change).
2. **Structured `pipeline_status.json` + gate consumption with freshness check. — DONE.**
   Implemented as `rebuild_pipeline.py --pipeline-status-out` (`pipeline_status.v0.1`, sha256 input
   fingerprints) and `gate_decision.py --pipeline-status` (validated, fingerprint-checked,
   fail-closed). The markdown fallback is preserved for backward compatibility.
3. **Expand CI for the formal layer. — DONE.** CI builds all theorem modules + all 6
   Challenge/Solution triples and runs `check_axioms` + `check_equivalence`. (Real Comparator-in-CI
   remains out of scope until its toolchain can be provisioned.)
4. **One real judge round, scored and recorded. — DONE (first round).** GoldIrrationalSqrtTwo ×
   gpt-4o @ temp 0: recall 1.0, FAR 0.0, 10/10 clean parses (`JUDGE_EVIDENCE_SUMMARY.md`; raw
   artifacts gitignored). Next: broaden across targets / models / seeds.
5. **Blinding-boundary regression test. — DONE.** `scripts/test_blinding_boundary.py` (static guard +
   hermetic runtime/poison test) turns the answer-key separation into a CI-enforced invariant.
6. **Converge the gate on one judge representation.** *Why:* remove the legacy/structured fork.
   *Files:* `gate_decision.py`, `score_judge.py`, tests. *Risk:* Med. *Type:* Python
   (behaviour-affecting — needs its own alignment pass).
7. **Vacuity / unused-hypothesis linters.** *Why:* close named drift modes (§20.4/§20.5). *Files:*
   new `scripts/` + tests + ARCHITECTURE note. *Risk:* Med. *Type:* Python + Lean-adjacent.
8. **Strengthen human approval (per-axis / signed reviews).** *Why:* approvals are too coarse.
   *Files:* review template, `validate_mapping.py`, reviews. *Risk:* Med. *Type:* docs + Python.
9. **Grow/diversify mutation suites.** *Why:* a thicker judge benchmark. *Files:* `docs/mutants/*`.
   *Risk:* Low. *Type:* data.
10. **Add a 4th target exercising `PASS_PROVABLE_EQUIV`.** *Why:* the guarded equivalence path is
    untested by any real target. *Files:* full target set. *Risk:* Med. *Type:* Lean + data.

---

## 9. Acceptance criteria

The harness can honestly be claimed to **meet its current architecture goals** when, for each
enabled target:

1. `lake build`, `check_sorries`, and `check_axioms` pass **in CI** (not just locally). **— satisfied:
   CI builds all theorem modules + all 6 triples and runs `check_sorries` + `check_axioms` for all
   targets. (Real Comparator acceptance remains local/WSL.)**
2. The Comparator has been run with writeback and the ledger records a **real** pass
   (`comparator_status` ∈ the real-landrun set, not `NOT_RUN`). **— satisfied for the current three
   targets (`ce5d8f3`: `PASSED_REAL_LANDRUN_BEST_EFFORT`); must hold for any new target.**
3. A **real** judge run (opt-in) has been scored, with discriminative-recall and false-alarm-rate
   recorded, demonstrating the judge catches the planted defects (not just that the plumbing runs).
   **— satisfied across all 3 targets (gpt-4o: aggregate recall 0.875, FAR 0.0; misses on PCP-D2 /
   TAM-D1); should be repeated across models/seeds with larger suites for a robust claim.**
4. `gate_decision.py` consumes a **fresh, structured** formal-status input and emits a defensible
   decision; at least one target reaches **PROMOTE** under genuine (non-mock) evidence. *(The
   structured, fingerprint-checked input is now implemented via `--pipeline-status`; the open part is
   reaching PROMOTE on real judge evidence with all formal stages actually run.)*
5. `validate_mapping` is green and the artifact policy holds (no generated evidence committed).

Criteria **1, 2, and 3 are now satisfied** (CI formal layer `d31c245`; Comparator writeback
`ce5d8f3`; real judge runs scored across all three targets `f4e4336`/`598f35f`). Criterion 4's
*structured, fingerprint-checked* input is implemented (`9a42747`); the only unmet part is a
**committed PROMOTE on real judge evidence**, which is **deliberately not produced** — raw judge
artifacts are gitignored by policy, and the pre-proof source-fidelity gate correctly holds the
imperfect-calibration targets (PutCallParity, TwoAssetMinVar) at HUMAN_REVIEW. The accurate claim is
therefore: *"an audit-first harness with a complete formal and structured-judge layer, exercised
end-to-end on three targets — recorded real Comparator passes, real judge calibration (aggregate
recall 0.875, imperfect), and an operational pre-proof source-fidelity gate — but **not** a fully
agentic closed-loop system, and with no committed PROMOTE by policy."* The closed-loop controller,
non-LLM signal, and multi-judge ensemble remain future research regardless.
