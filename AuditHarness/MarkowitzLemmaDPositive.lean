import AuditHarness.MarkowitzLemmaDPositive.Helpers

/-!
# Markowitz frontier discriminant is positive (worked target)

For a portfolio of `n` risky assets with positive-definite covariance matrix `Σ` (written `S`
in Lean, since `Σ` is reserved) and expected-return vector `μ`, the closed-form efficient frontier
is parameterised by the three Gram scalars

`A = 1 ⬝ᵥ Σ⁻¹ μ`,  `B = μ ⬝ᵥ Σ⁻¹ μ`,  `C = 1 ⬝ᵥ Σ⁻¹ 1`,

and the frontier **discriminant** `D = B * C - A²`. The minimum-variance frontier
`σ²(m) = (C m² - 2 A m + B) / D` is well defined exactly when `D > 0`. The source claim is:
whenever `Σ` is positive definite and `μ` is **not** a scalar multiple of the all-ones vector
`1` (i.e. expected returns are not all equal — otherwise the frontier degenerates), one has

`0 < C ∧ 0 < B ∧ 0 < D`.

`C > 0` and `B > 0` are the positive-definiteness of `Σ⁻¹` at `1` and at `μ`. The crux `D > 0`
follows from positive-definiteness at the witness vector `C • μ - A • 1`, whose Gram norm equals
`C * D` (identity `witness_gram_eq`); since that witness is nonzero (it would force `μ = (A/C) • 1`)
its norm is strictly positive, and `C > 0` then yields `D > 0`.

This is the **source-facing theorem module** (the mapped declaration). The Gram scalars
(`coeffA`/`coeffB`/`coeffC`/`discr`) and all algebraic lemmas live in
`AuditHarness.MarkowitzLemmaDPositive.Helpers`.
-/

namespace AuditHarness

open Matrix MarkowitzLemmaDPositive

/-- **Markowitz frontier discriminant is positive.** For a positive-definite covariance matrix `S`
and an expected-return vector `μ` that is not a scalar multiple of the all-ones vector, the three
frontier Gram scalars `A = 1 ⬝ᵥ S⁻¹ μ`, `B = μ ⬝ᵥ S⁻¹ μ`, `C = 1 ⬝ᵥ S⁻¹ 1` and the discriminant
`D = B * C - A²` satisfy `0 < C`, `0 < B` and `0 < D`. -/
theorem markowitz_lemma_D_positive {n : ℕ} [Nonempty (Fin n)]
    (S : Matrix (Fin n) (Fin n) ℝ) (hS : S.PosDef) (μ : Fin n → ℝ)
    (hμ : ¬ ∃ c : ℝ, μ = c • (1 : Fin n → ℝ)) :
    let A := (1 : Fin n → ℝ) ⬝ᵥ (S⁻¹ *ᵥ μ);
    let B := μ ⬝ᵥ (S⁻¹ *ᵥ μ);
    let C := (1 : Fin n → ℝ) ⬝ᵥ (S⁻¹ *ᵥ (1 : Fin n → ℝ));
    let D := B * C - A ^ 2;
    0 < C ∧ 0 < B ∧ 0 < D := by
  intro A B C D
  -- `μ ≠ 0`, since otherwise `μ = 0 • 1` would contradict `hμ`.
  have hμ0 : μ ≠ 0 := fun h => hμ ⟨0, by rw [h, zero_smul]⟩
  -- `C > 0` and `B > 0` are positive-definiteness of `S⁻¹` at `1` and at `μ`.
  have hC : 0 < C := gram_self_pos S hS 1 one_ne_zero'
  have hB : 0 < B := gram_self_pos S hS μ hμ0
  refine ⟨hC, hB, ?_⟩
  -- `D > 0`: the witness `C • μ - A • 1` is nonzero, so its Gram norm `C * D` is positive.
  have hw : 0 < coeffC S μ * discr S μ := by
    rw [← witness_gram_eq S hS μ]
    exact gram_self_pos S hS _ (witness_ne_zero S μ hμ hC)
  exact (mul_pos_iff_of_pos_left hC).mp hw

end AuditHarness
