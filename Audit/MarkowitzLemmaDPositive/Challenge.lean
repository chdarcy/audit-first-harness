import Mathlib.LinearAlgebra.Matrix.PosDef
import Mathlib.LinearAlgebra.Matrix.NonsingularInverse
import Mathlib.Data.Matrix.Mul

/-!
# Comparator Challenge — Markowitz frontier discriminant is positive

A *Mathlib-only* statement of `markowitz_lemma_D_positive`. The statement is phrased directly in
terms of Matrix operations (`PosDef`, `S⁻¹`, `⬝ᵥ`, `*ᵥ`) and needs no project definitions, so
nothing is copied from the library. The theorem is stated in a dedicated
`AuditHarness.StatementAudit` namespace with the proof left as `sorry`; the matching
`Solution.lean` supplies a real proof by delegating to the library theorem.
-/

namespace AuditHarness.StatementAudit

open Matrix

/-- **Markowitz frontier discriminant is positive** (challenge statement): for a positive-definite
covariance matrix `S` and an expected-return vector `μ` that is not a scalar multiple of the
all-ones vector, the frontier Gram scalars `A = 1 ⬝ᵥ S⁻¹ μ`, `B = μ ⬝ᵥ S⁻¹ μ`, `C = 1 ⬝ᵥ S⁻¹ 1`
and the discriminant `D = B * C - A²` satisfy `0 < C`, `0 < B` and `0 < D`. -/
theorem markowitz_lemma_D_positive {n : ℕ} [Nonempty (Fin n)]
    (S : Matrix (Fin n) (Fin n) ℝ) (hS : S.PosDef) (μ : Fin n → ℝ)
    (hμ : ¬ ∃ c : ℝ, μ = c • (1 : Fin n → ℝ)) :
    let A := (1 : Fin n → ℝ) ⬝ᵥ (S⁻¹ *ᵥ μ);
    let B := μ ⬝ᵥ (S⁻¹ *ᵥ μ);
    let C := (1 : Fin n → ℝ) ⬝ᵥ (S⁻¹ *ᵥ (1 : Fin n → ℝ));
    let D := B * C - A ^ 2;
    0 < C ∧ 0 < B ∧ 0 < D := by
  sorry

end AuditHarness.StatementAudit
