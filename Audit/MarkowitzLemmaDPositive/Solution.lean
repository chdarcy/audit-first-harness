import AuditHarness

/-!
# Comparator Solution — Markowitz frontier discriminant is positive

Restates `markowitz_lemma_D_positive` with the **identical** statement and the same
`AuditHarness.StatementAudit` namespace as `Challenge.lean`, so the two theorem statements are
identical for the Comparator. The statement uses no project definitions, so the proof delegates
directly to the library theorem `_root_.AuditHarness.markowitz_lemma_D_positive`.
-/

namespace AuditHarness.StatementAudit

open Matrix

/-- **Markowitz frontier discriminant is positive** (solution): identical statement to the
challenge, proved by delegating to the library theorem
`_root_.AuditHarness.markowitz_lemma_D_positive`. -/
theorem markowitz_lemma_D_positive {n : ℕ} [Nonempty (Fin n)]
    (S : Matrix (Fin n) (Fin n) ℝ) (hS : S.PosDef) (μ : Fin n → ℝ)
    (hμ : ¬ ∃ c : ℝ, μ = c • (1 : Fin n → ℝ)) :
    let A := (1 : Fin n → ℝ) ⬝ᵥ (S⁻¹ *ᵥ μ);
    let B := μ ⬝ᵥ (S⁻¹ *ᵥ μ);
    let C := (1 : Fin n → ℝ) ⬝ᵥ (S⁻¹ *ᵥ (1 : Fin n → ℝ));
    let D := B * C - A ^ 2;
    0 < C ∧ 0 < B ∧ 0 < D :=
  _root_.AuditHarness.markowitz_lemma_D_positive S hS μ hμ

end AuditHarness.StatementAudit
