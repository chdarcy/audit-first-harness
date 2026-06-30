import Mathlib.LinearAlgebra.Matrix.PosDef
import Mathlib.LinearAlgebra.Matrix.NonsingularInverse
import Mathlib.Data.Matrix.Mul

/-!
# Markowitz frontier discriminant `D > 0` — definitions and proof helpers

The Gram-form scalars and the algebraic identities backing
`AuditHarness.markowitz_lemma_D_positive` live here, so the public theorem module
(`AuditHarness/MarkowitzLemmaDPositive.lean`) reads as a short, source-facing statement with a
short proof.

For a positive-definite covariance matrix `S` and an expected-return vector `μ`, the efficient
frontier is governed by the three Gram scalars built from `S⁻¹`:

* `coeffA S μ = 1 ⬝ᵥ S⁻¹ μ`,
* `coeffB S μ = μ ⬝ᵥ S⁻¹ μ`,
* `coeffC S μ = 1 ⬝ᵥ S⁻¹ 1`,

and the frontier discriminant `discr S μ = coeffB S μ * coeffC S μ - coeffA S μ ^ 2`. These keep
their fully-qualified names `AuditHarness.MarkowitzLemmaDPositive.*` (the namespace, not the file,
fixes the name).

The crux is `witness_gram_eq`: the quadratic form of `S⁻¹` evaluated at the witness vector
`coeffC S μ • μ - coeffA S μ • 1` equals `coeffC S μ * discr S μ`. Combined with positive-
definiteness (`gram_self_pos`) and the fact that this witness is nonzero whenever `μ` is not a
scalar multiple of `1` (`witness_ne_zero`), this forces `discr S μ > 0`.
-/

namespace AuditHarness.MarkowitzLemmaDPositive

open Matrix

variable {n : ℕ}

/-- `coeffA S μ = 1 ⬝ᵥ S⁻¹ μ`, the mixed Gram scalar (numerator of the tangency weights). -/
noncomputable def coeffA (S : Matrix (Fin n) (Fin n) ℝ) (μ : Fin n → ℝ) : ℝ :=
  (1 : Fin n → ℝ) ⬝ᵥ (S⁻¹ *ᵥ μ)

/-- `coeffB S μ = μ ⬝ᵥ S⁻¹ μ`, the return-weighted Gram scalar. -/
noncomputable def coeffB (S : Matrix (Fin n) (Fin n) ℝ) (μ : Fin n → ℝ) : ℝ :=
  μ ⬝ᵥ (S⁻¹ *ᵥ μ)

/-- `coeffC S μ = 1 ⬝ᵥ S⁻¹ 1`, the total-precision Gram scalar (reciprocal min-variance scale). -/
noncomputable def coeffC (S : Matrix (Fin n) (Fin n) ℝ) (_μ : Fin n → ℝ) : ℝ :=
  (1 : Fin n → ℝ) ⬝ᵥ (S⁻¹ *ᵥ (1 : Fin n → ℝ))

/-- The Markowitz frontier discriminant `discr S μ = coeffB * coeffC - coeffA ^ 2`. -/
noncomputable def discr (S : Matrix (Fin n) (Fin n) ℝ) (μ : Fin n → ℝ) : ℝ :=
  coeffB S μ * coeffC S μ - coeffA S μ ^ 2

/-- **Gram symmetry.** Since `S⁻¹` is symmetric (inverse of a Hermitian/symmetric matrix), the Gram
form `x ⬝ᵥ S⁻¹ y` is symmetric in `x` and `y`. -/
theorem gram_comm (S : Matrix (Fin n) (Fin n) ℝ) (hS : S.PosDef) (x y : Fin n → ℝ) :
    x ⬝ᵥ (S⁻¹ *ᵥ y) = y ⬝ᵥ (S⁻¹ *ᵥ x) := by
  have hsymm : (S⁻¹)ᵀ = S⁻¹ := (isHermitian_iff_isSymm.mp hS.inv.isHermitian).eq
  rw [dotProduct_mulVec, ← mulVec_transpose, hsymm, dotProduct_comm]

/-- **Gram positivity.** The quadratic form of the positive-definite matrix `S⁻¹` is strictly
positive at any nonzero vector. Wraps `Matrix.PosDef.dotProduct_mulVec_pos` (over `ℝ`,
`star x = x`). -/
theorem gram_self_pos (S : Matrix (Fin n) (Fin n) ℝ) (hS : S.PosDef) (x : Fin n → ℝ)
    (hx : x ≠ 0) : 0 < x ⬝ᵥ (S⁻¹ *ᵥ x) := by
  have h := hS.inv.dotProduct_mulVec_pos hx
  rwa [star_trivial] at h

/-- **Crux identity.** The quadratic form of `S⁻¹` evaluated at the witness vector
`coeffC S μ • μ - coeffA S μ • 1` equals `coeffC S μ * discr S μ`. Proved by expanding bilinearity
of the Gram form, rewriting the cross term via `gram_comm`, and `ring`. -/
theorem witness_gram_eq (S : Matrix (Fin n) (Fin n) ℝ) (hS : S.PosDef) (μ : Fin n → ℝ) :
    (coeffC S μ • μ - coeffA S μ • (1 : Fin n → ℝ))
        ⬝ᵥ (S⁻¹ *ᵥ (coeffC S μ • μ - coeffA S μ • (1 : Fin n → ℝ)))
      = coeffC S μ * discr S μ := by
  have hcomm : μ ⬝ᵥ (S⁻¹ *ᵥ (1 : Fin n → ℝ)) = (1 : Fin n → ℝ) ⬝ᵥ (S⁻¹ *ᵥ μ) :=
    gram_comm S hS μ 1
  simp only [discr, coeffA, coeffB, coeffC, mulVec_sub, mulVec_smul, sub_dotProduct,
    dotProduct_sub, smul_dotProduct, dotProduct_smul, smul_eq_mul]
  rw [hcomm]
  ring

/-- The all-ones vector is nonzero whenever the index type is inhabited. -/
theorem one_ne_zero' [Nonempty (Fin n)] : (1 : Fin n → ℝ) ≠ 0 := by
  intro h
  have := congrFun h (Classical.arbitrary (Fin n))
  simp at this

/-- **Witness is nonzero.** When `μ` is not a scalar multiple of `1` and `coeffC S μ > 0`, the
witness vector `coeffC S μ • μ - coeffA S μ • 1` is nonzero: otherwise `μ` would equal
`(coeffA / coeffC) • 1`. -/
theorem witness_ne_zero (S : Matrix (Fin n) (Fin n) ℝ) (μ : Fin n → ℝ)
    (hμ : ¬ ∃ c : ℝ, μ = c • (1 : Fin n → ℝ)) (hC : 0 < coeffC S μ) :
    coeffC S μ • μ - coeffA S μ • (1 : Fin n → ℝ) ≠ 0 := by
  intro h
  have hCne : coeffC S μ ≠ 0 := ne_of_gt hC
  have h2 : coeffC S μ • μ = coeffA S μ • (1 : Fin n → ℝ) := sub_eq_zero.mp h
  have key : (coeffC S μ)⁻¹ • (coeffC S μ • μ)
      = (coeffC S μ)⁻¹ • (coeffA S μ • (1 : Fin n → ℝ)) := by rw [h2]
  rw [smul_smul, inv_mul_cancel₀ hCne, one_smul, smul_smul, ← div_eq_inv_mul] at key
  exact hμ ⟨coeffA S μ / coeffC S μ, key⟩

end AuditHarness.MarkowitzLemmaDPositive
