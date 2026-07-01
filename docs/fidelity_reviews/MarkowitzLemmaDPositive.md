---
target: MarkowitzLemmaDPositive
source_refs: [thm:markowitz_lemma_d_positive]
source_labels: [lem:D]
lean_declaration: markowitz_lemma_D_positive
verdict: PASS
rubric:
  A_assumptions: match
  B_conclusion: stronger_with_note
  C_quantifiers: match
  D_variables: match
  E_vacuity: non_vacuous
  F_direction: source_supported_strengthening
  G_units_form: match
judge:
  model: null
  version: null
  temperature: null
  prompt_sha256: null
  de_anchored: null
  ran_utc: null
  saw: null
  did_not_see: null
mutation_results: null
human_approved: true
human_approver: Christopher Darcy
human_approved_utc: "2026-07-01T20:55:14Z"
---

# MarkowitzLemmaDPositive — fidelity review

> **Status: HUMAN SOURCE-FIDELITY APPROVED — pending real Comparator run and promotion gate.**
> **Lean correctness is done** — the theorem is fully proved and axiom-audited
> (`[propext, Quot.sound, Classical.choice]`; no `sorryAx`). **The source-fidelity review is now
> approved** (`verdict: PASS`, `human_approved: true`). **The Comparator status is still `NOT_RUN`**
> until the real Comparator writeback is executed, and **this target is not yet promoted** (the
> promotion gate runs after the Comparator).

## Source claim
From internal source-ledger key `thm:markowitz_lemma_d_positive`, corresponding to source LaTeX
label `lem:D` in `examples/markowitz_lecture_notes/source.tex` (lines 239–246, proof 248–263).
With a symmetric positive-definite covariance `Σ`, mean vector `μ` not proportional to the all-ones
vector `1`, and `A := 1ᵀΣ⁻¹μ`, `B := μᵀΣ⁻¹μ`, `C := 1ᵀΣ⁻¹1`, `D := BC − A²`, the source lemma
statement advertises (under its non-degeneracy assumption) **`C > 0` and `D > 0`** — used to give the
frontier linear system a unique solution `λ = (Cm − A)/D`, `γ = (B − Am)/D`. `B > 0` is not part of
the lemma's advertised statement, but it is explicitly established in the source proof as an
intermediate positivity fact (`C = 1ᵀΣ⁻¹1 > 0` and `B = μᵀΣ⁻¹μ > 0`, source line 250).

## Lean claim
`markowitz_lemma_D_positive` (root namespace `AuditHarness`, module
`AuditHarness.MarkowitzLemmaDPositive`): for `S : Matrix (Fin n) (Fin n) ℝ` with `hS : S.PosDef`,
`μ : Fin n → ℝ` with `hμ : ¬ ∃ c, μ = c • (1 : Fin n → ℝ)`, and (with `A,B,C,D` defined exactly as
above via `S⁻¹` and `⬝ᵥ`/`*ᵥ`), the conclusion is **`0 < C ∧ 0 < B ∧ 0 < D`**. (The covariance is
named `S` rather than `Σ` because `Σ` is a reserved token in Lean.)

## Fidelity checklist (reviewer observations)
- **Assumptions match.** Source SPD `Σ` ↔ Lean `S.PosDef`; source "μ not proportional to `1`" ↔ Lean
  `¬ ∃ c, μ = c • 1`. `[Nonempty (Fin n)]` (i.e. `n > 0`) is the implicit non-emptiness the source
  also assumes. No extra hypotheses added or dropped.
- **Variables match.** `A,B,C,D` are defined term-for-term as in the source (`1ᵀΣ⁻¹μ`, `μᵀΣ⁻¹μ`,
  `1ᵀΣ⁻¹1`, `BC − A²`), with `S⁻¹ ↔ Σ⁻¹`, `⬝ᵥ`/`*ᵥ ↔` the matrix/vector products.
- **Quantifiers / form match.** Same finite-dimensional setting; same closed-form scalars.
- **Conclusion is a source-supported strengthening.** The source *lemma headline* advertises
  `C > 0 ∧ D > 0`; the Lean proves `C > 0 ∧ B > 0 ∧ D > 0`, i.e. it additionally asserts `B > 0`.
  `B > 0` is explicitly established in the source proof under the same hypotheses, so surfacing it is
  a source-supported strengthening rather than a fidelity error (see **Decision**).
- **Vacuity.** Non-vacuous: the hypotheses are satisfiable (e.g. `S = 1` identity, `μ` any vector not
  proportional to `1`, `n ≥ 2`).

## Decision
**Decision: PASS with note.**

The Lean theorem is a faithful formalisation of the positivity content of Lemma D. It proves the
advertised source conclusions `C > 0` and `D > 0`, and additionally surfaces `B > 0`. This is a
source-supported strengthening rather than a fidelity error: `B > 0` is explicitly established in the
source proof under the same hypotheses, and the MK-003 source-formalisation record already scoped
this target as `C > 0, B > 0, D > 0`.

This remains flagged as a conclusion strengthening relative to the lemma headline, because the source
statement itself advertises only `C > 0` and `D > 0`. The audit decision is therefore PASS with note,
not silent match (rubric `B_conclusion: stronger_with_note`, `F_direction:
source_supported_strengthening`).

The uniqueness / Cramer's-rule consequence in Lemma D is not covered by this theorem and remains
deliberately deferred to a later target.

## Verdict
**PASS** (`verdict: PASS`, `human_approved: true`, approver Christopher Darcy). Lean correctness is
established and the source-fidelity review is approved. The Comparator run (`comparator_status:
NOT_RUN`) and the promotion gate are still outstanding; this target is not yet promoted.
