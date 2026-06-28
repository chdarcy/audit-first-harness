import Mathlib.Data.Real.Basic
import Mathlib.Tactic.FieldSimp
import Mathlib.Tactic.Ring
import Mathlib.Tactic.Linarith

/-!
# Two-asset minimum-variance portfolio (worked target)

A second, slightly less trivial real-analysis target for the audit-first harness: the classic
two-asset Markowitz minimum-variance weight. For two risky assets with variance parameters
`sigma1Sq`, `sigma2Sq` and covariance `sigma12`, a portfolio holding weight `w` in asset 1 and
`1 - w` in asset 2 has variance

`V(w) = w² · σ₁² + (1-w)² · σ₂² + 2 · w · (1-w) · σ₁₂`.

Writing `denom = σ₁² + σ₂² - 2 σ₁₂`, the variance is the quadratic
`V(w) = denom · w² + 2 (σ₁₂ - σ₂²) · w + σ₂²`. When `denom > 0` this is a strictly convex
parabola minimised at `w* = (σ₂² - σ₁₂) / denom`, because

`V(w) - V(w*) = denom · (w - w*)²  ≥ 0`.

The result is deliberately **algebraic**, and its scope is exactly the source claim:

* the minimisation is over **all real weights** `w : ℝ` — there is **no** long-only
  `0 ≤ w ≤ 1` constraint;
* the conclusion is **non-strict global** minimality (`V(w*) ≤ V(w)`);
* **uniqueness is not claimed**;
* the only hypothesis is `denom > 0` — no `σ₁² > 0` / `σ₂² > 0` positivity is needed for the
  inequality, only that the quadratic coefficient is positive.
-/

namespace AuditHarness

/-- Variance of a two-asset portfolio with weight `w` in asset 1 and `1 - w` in asset 2,
with variance parameters `sigma1Sq`, `sigma2Sq` and covariance `sigma12`. -/
def twoAssetVariance (sigma1Sq sigma2Sq sigma12 w : ℝ) : ℝ :=
  w ^ 2 * sigma1Sq + (1 - w) ^ 2 * sigma2Sq + 2 * w * (1 - w) * sigma12

/-- **Two-asset minimum-variance weight.** When the quadratic coefficient
`sigma1Sq + sigma2Sq - 2 * sigma12` is positive, the portfolio variance is globally minimised
over **all real weights** at `w* = (sigma2Sq - sigma12) / (sigma1Sq + sigma2Sq - 2 * sigma12)`.
The conclusion is non-strict (`≤`) and makes no uniqueness claim. -/
theorem two_asset_min_variance_weight
    (sigma1Sq sigma2Sq sigma12 : ℝ)
    (hdenom : 0 < sigma1Sq + sigma2Sq - 2 * sigma12) :
    ∀ w : ℝ,
      twoAssetVariance sigma1Sq sigma2Sq sigma12
          ((sigma2Sq - sigma12) / (sigma1Sq + sigma2Sq - 2 * sigma12))
        ≤ twoAssetVariance sigma1Sq sigma2Sq sigma12 w := by
  intro w
  have hd : sigma1Sq + sigma2Sq - 2 * sigma12 ≠ 0 := ne_of_gt hdenom
  -- `V(w) - V(w*) = denom · (w - w*)²`, a completed-square identity.
  have hid :
      twoAssetVariance sigma1Sq sigma2Sq sigma12 w
          - twoAssetVariance sigma1Sq sigma2Sq sigma12
              ((sigma2Sq - sigma12) / (sigma1Sq + sigma2Sq - 2 * sigma12))
        = (sigma1Sq + sigma2Sq - 2 * sigma12)
            * (w - (sigma2Sq - sigma12) / (sigma1Sq + sigma2Sq - 2 * sigma12)) ^ 2 := by
    unfold twoAssetVariance
    field_simp
    ring
  have hnn :
      0 ≤ (sigma1Sq + sigma2Sq - 2 * sigma12)
            * (w - (sigma2Sq - sigma12) / (sigma1Sq + sigma2Sq - 2 * sigma12)) ^ 2 :=
    mul_nonneg hdenom.le (sq_nonneg _)
  linarith [hid, hnn]

end AuditHarness
