# GAP_ANALYSIS — architecture audit

**Type:** audit snapshot (documentation only). **Baseline commit:** `90ae0b5` (Separate architecture
from milestone history). **Against:** [`../ARCHITECTURE.md`](../ARCHITECTURE.md);
history in [`MILESTONES.md`](MILESTONES.md).

This document audits the repository against the goals in `ARCHITECTURE.md`. It changes no code,
Lean, mappings, mutants, Comparator configs, judge prompts, or generated artifacts, and ran no
model/API. It is a point-in-time assessment; re-run the audit after material changes.

---

## 1. Executive summary

**Have we met the goals in ARCHITECTURE.md?** **Mostly implemented** for the audit/measurement
spine and the structured-judge evidence pipeline; **partially implemented** at the *completion /
evidence* level (no committed real judge run; the gate still reads a markdown report); **future
research** for the closed-loop controller and the second-signal/scaling items, exactly as the
document states.

The harness has the **infrastructure** for an audit-first, anti-drift workflow and demonstrates it
end-to-end on three targets. The honest gaps are not missing machinery but **unexercised
completion** (the judge pipeline has never been run against a real model and committed) and **CI
under-coverage** of the Lean-dependent checks. As a result, **no target is currently PROMOTE-ready**
through the gate, and we have strong evidence the *plumbing* works but little evidence the *judge*
detects defects on real model output.

> **Post-audit update (commit `ce5d8f3`).** Since this snapshot, the **Comparator-status writeback**
> gap is **closed**: a real Comparator run was performed with `--writeback-comparator-status` for all
> three targets, and the ledger now records `comparator_status: PASSED_REAL_LANDRUN_BEST_EFFORT`
> (previously `NOT_RUN`) — formal Challenge/Solution evidence only, not source fidelity. **Only this
> gap is closed.** Promotion is still blocked by the lack of a committed real judge run, the gate's
> reliance on the markdown `pipeline_report.md` (no `pipeline_status.json`), and CI formal-layer
> under-coverage. The cells/rows below are annotated where `ce5d8f3` changed the status; everything
> else stands as of the baseline.

| Layer | Status |
|---|---|
| Source→Lean traceability (cards / mapping / reviews) | **Implemented** |
| Formal correctness (build, no-sorry, axiom audit, Comparator architecture) | **Implemented** |
| Comparator status writeback (recorded real pass in the ledger) | **Implemented** (all 3 `PASSED_REAL_LANDRUN_BEST_EFFORT`, `ce5d8f3`) |
| Blinded judge packages / manual import / live opt-in | **Implemented** |
| Structured-judge pipeline (schema / scoring / gate caps / export / workflow) | **Implemented** |
| Promotion gate | **Implemented** (but reads markdown report; no target promotable yet) |
| Empirical judge reliability (real run scored & committed) | **Not implemented** |
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
| Live judge opt-in path | Implemented | `run_judge.py --execute-api` (opt-in, key from env) | never run / no committed evidence | Med | One real (opt-in) run, score it |
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
| promotion readiness | ❌ blocked: no committed real judge `scored.yaml` (Comparator now recorded) | ❌ same | ❌ same |

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
- **Does not:** produce anything without an existing `judge_results/<T>.yaml` — and none exists for
  real targets. It is exercised only on fixtures.
- **Can fail silently:** if fed an empty/missing results file it (correctly) fails or skips, but
  there is currently nothing real to feed it, so the layer's value is unproven on real data.
- **Improve next:** run it on one real (opt-in) judge round; consider making the structured summary
  the gate's primary judge signal (today the gate's primary signal is the legacy `scored.yaml`).

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
  fingerprints. Missing `scored.yaml` ⇒ BLOCK (safe), so no target promotes today.
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
2. **Infrastructure-rich, evidence-poor judging.** The full judge stack exists, but there is **no
   committed real judge run**. We have not measured discriminative recall / false-alarm rate on
   actual model output; we have only proven the plumbing on synthetic fixtures. The central
   empirical claim ("the judge can catch planted defects") is **unvalidated**. **(High)**
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
8. **Blinding boundary is convention-enforced, not test-enforced.** This session verified that
   `run_judge.py`/`import_manual_judge_results.py` read `_targets.yaml` only and never `_manifest`,
   while `score_judge`/`export` read `_manifest`. But there is no automated guard asserting the
   runner/importer never reference the answer key; a future edit could leak it. **(Low–Med)**
9. **CI under-covers the formal layer. — REDUCED.** CI now builds every theorem module and all six
   Challenge/Solution modules for all three targets and runs `check_axioms` + `check_equivalence`, so
   a broken triple or an axiom regression is caught. Residual: the **real Comparator** (landrun
   sandbox) is not run in CI — its binaries are not installed — so Comparator *acceptance* and
   `comparator_status` writeback remain local/WSL. **(was High → Low; Comparator-in-CI still open)**
10. **ARCHITECTURE.md post-split stability:** good. The version/diary wording was removed; remaining
    forward-looking statements (§11.3 "future structured pipeline JSON", §20 future items, §12/§20.1
    closed loop) are accurately marked future. No material stale "current" claims found. **(Low)**

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
- Run the judge for real once (opt-in), score it, and record discriminative-recall / FAR — i.e.
  produce *evidence the judge works*, not just infrastructure.
- ~~Emit a structured `pipeline_status.json` and have the gate consume it with a freshness check.~~ —
  **done** (`rebuild_pipeline.py --pipeline-status-out` / `gate_decision.py --pipeline-status`,
  sha256 fingerprint-checked, fail-closed).
- ~~Expand CI to build all Comparator triples and run the axiom audit.~~ — **done** (CI builds all
  theorem modules + 6 triples and runs `check_axioms` + `check_equivalence`; real Comparator stays
  local/WSL).

**Should do before scaling targets:**
- Strengthen human approval (per-axis / signed) and grow mutation suites.
- Decide the canonical judge representation (legacy vs structured) and converge the gate on it.
- Add a test that enforces the blinding boundary (no `_manifest` access in runner/importer).

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
4. **One real judge round, scored and recorded.** *Why:* first empirical evidence the judge detects
   defects. *Files:* gitignored judge artifacts + a committed summary/metric snapshot doc. *Risk:*
   Med (opt-in API). *Type:* run + docs.
5. **Blinding-boundary regression test.** *Why:* turn the answer-key separation from convention into
   an enforced invariant. *Files:* a new `scripts/test_*` + CI line. *Risk:* Low. *Type:* Python.
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
4. `gate_decision.py` consumes a **fresh, structured** formal-status input and emits a defensible
   decision; at least one target reaches **PROMOTE** under genuine (non-mock) evidence. *(The
   structured, fingerprint-checked input is now implemented via `--pipeline-status`; the open part is
   reaching PROMOTE on real judge evidence with all formal stages actually run.)*
5. `validate_mapping` is green and the artifact policy holds (no generated evidence committed).

Criterion 2 is now satisfied for the three current targets (`ce5d8f3`). Until criteria 1, 3, and 4
hold, the accurate claim is: *"an audit-first harness with a complete formal and structured-judge
**infrastructure**, demonstrated end-to-end with recorded real Comparator passes, but not yet
exercised to a recorded PROMOTE on real judge evidence."* The closed-loop controller remains future
research regardless.
