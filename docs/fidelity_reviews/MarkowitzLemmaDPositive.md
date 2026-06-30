---
target: MarkowitzLemmaDPositive
source_refs: [thm:markowitz_lemma_d_positive]
lean_declaration: markowitz_lemma_D_positive
verdict: null
rubric:
  A_assumptions: match
  B_conclusion: stronger
  C_quantifiers: match
  D_variables: match
  E_vacuity: non_vacuous
  F_direction: strengthened
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
human_approved: false
human_approver: null
human_approved_utc: null
---

# MarkowitzLemmaDPositive — fidelity review (DRAFT)

> **Status: DRAFT — pending human review and a Comparator run. NOT approved for promotion.**
> The Lean theorem is fully proved and axiom-audited (`[propext, Quot.sound, Classical.choice]`; no
> `sorryAx`), so **Lean proof correctness is done**. This file records draft, objectively-checkable
> observations for a human reviewer; it does **not** assert a final source-fidelity verdict
> (`verdict: null`) and carries no human approval (`human_approved: false`). See the **open question**
> below before promoting.

## Source claim
From `thm:markowitz_lemma_d_positive` (`examples/markowitz_lecture_notes/source.tex`, lines 240–245).
With a symmetric positive-definite covariance `Σ`, mean vector `μ` not proportional to the all-ones
vector `1`, and `A := 1ᵀΣ⁻¹μ`, `B := μᵀΣ⁻¹μ`, `C := 1ᵀΣ⁻¹1`, `D := BC − A²`, the source states (under
its non-degeneracy assumption) **`C > 0` and `D > 0`** — used to give the frontier linear system a
unique solution `λ = (Cm − A)/D`, `γ = (B − Am)/D`. The source advertises `C > 0` and `D > 0`
explicitly; **`B > 0` appears only implicitly in the proof** (`μᵀΣ⁻¹μ > 0` for the non-degenerate
case).

## Lean claim
`markowitz_lemma_D_positive` (root namespace `AuditHarness`, module
`AuditHarness.MarkowitzLemmaDPositive`): for `S : Matrix (Fin n) (Fin n) ℝ` with `hS : S.PosDef`,
`μ : Fin n → ℝ` with `hμ : ¬ ∃ c, μ = c • (1 : Fin n → ℝ)`, and (with `A,B,C,D` defined exactly as
above via `S⁻¹` and `⬝ᵥ`/`*ᵥ`), the conclusion is **`0 < C ∧ 0 < B ∧ 0 < D`**. (The covariance is
named `S` rather than `Σ` because `Σ` is a reserved token in Lean.)

## Fidelity checklist (draft observations)
- **Assumptions match.** Source SPD `Σ` ↔ Lean `S.PosDef`; source "μ not proportional to `1`" ↔ Lean
  `¬ ∃ c, μ = c • 1`. `[Nonempty (Fin n)]` (i.e. `n > 0`) is the implicit non-emptiness the source
  also assumes. No extra hypotheses added or dropped.
- **Variables match.** `A,B,C,D` are defined term-for-term as in the source (`1ᵀΣ⁻¹μ`, `μᵀΣ⁻¹μ`,
  `1ᵀΣ⁻¹1`, `BC − A²`), with `S⁻¹ ↔ Σ⁻¹`, `⬝ᵥ`/`*ᵥ ↔` the matrix/vector products.
- **Quantifiers / form match.** Same finite-dimensional setting; same closed-form scalars.
- **Conclusion is STRONGER than the source's explicit claim.** The source explicitly advertises
  `C > 0 ∧ D > 0`; the Lean proves `C > 0 ∧ B > 0 ∧ D > 0`, i.e. it additionally asserts `B > 0`.
- **Vacuity.** Non-vacuous: the hypotheses are satisfiable (e.g. `S = 1` identity, `μ` any vector not
  proportional to `1`, `n ≥ 2`).

## Open question for the human reviewer (the reason verdict is pending)
Does including **`B > 0`** in the Lean conclusion preserve fidelity to the source lemma, which
explicitly states only `C > 0` and `D > 0`? Two defensible readings:
1. **Faithful** — `B > 0` (`μᵀΣ⁻¹μ > 0`) is implicit in the source's non-degenerate setting and is
   used inside the source proof, so surfacing it is a benign strengthening.
2. **Over-strong** — the source *lemma as stated* claims only `C > 0, D > 0`; adding `B > 0` states
   more than the cited result, which a strict fidelity review may want as a separate sub-claim or a
   `WARN`/`stronger` annotation rather than a direct `PASS`.
A human must choose (and the Comparator run must be executed) before this target is promoted.

## Verdict
**Pending** (`verdict: null`). Lean correctness is established; source-fidelity sign-off and the
Comparator run are outstanding. Not approved for promotion.
