import AuditHarness.TwoAssetMinVar.Helpers

/-!
# Two-asset minimum-variance portfolio (worked target)

The classic two-asset Markowitz minimum-variance weight. For two risky assets with variance
parameters `sigma1Sq`, `sigma2Sq` and covariance `sigma12`, a portfolio holding weight `w` in
asset 1 and `1 - w` in asset 2 has variance
`twoAssetVariance sigma1Sq sigma2Sq sigma12 w = w² σ₁² + (1-w)² σ₂² + 2 w (1-w) σ₁₂`.

Writing `denom = σ₁² + σ₂² - 2 σ₁₂`, when `denom > 0` this strictly-convex quadratic is minimised
over **all real weights** at `w* = (σ₂² - σ₁₂) / denom`. The scope is exactly the source claim:
minimisation over the whole real line (no long-only `0 ≤ w ≤ 1` constraint), a non-strict global
inequality (`V(w*) ≤ V(w)`), no uniqueness claim, and the only hypothesis is `denom > 0`.

This is the **source-facing theorem module**: the statement below is the mapped declaration
(`docs/formal_mapping.yaml`). The definition `twoAssetVariance` and the completed-square /
minimality lemmas live in `AuditHarness.TwoAssetMinVar.Helpers`.
-/

namespace AuditHarness

/-- **Two-asset minimum-variance weight.** When the quadratic coefficient
`sigma1Sq + sigma2Sq - 2 * sigma12` is positive, the portfolio variance is globally minimised over
**all real weights** at `w* = (sigma2Sq - sigma12) / (sigma1Sq + sigma2Sq - 2 * sigma12)`. The
conclusion is non-strict (`≤`) and makes no uniqueness claim. -/
theorem two_asset_min_variance_weight
    (sigma1Sq sigma2Sq sigma12 : ℝ)
    (hdenom : 0 < sigma1Sq + sigma2Sq - 2 * sigma12) :
    ∀ w : ℝ,
      twoAssetVariance sigma1Sq sigma2Sq sigma12
          ((sigma2Sq - sigma12) / (sigma1Sq + sigma2Sq - 2 * sigma12))
        ≤ twoAssetVariance sigma1Sq sigma2Sq sigma12 w :=
  fun w => twoAssetVariance_argmin_le sigma1Sq sigma2Sq sigma12 hdenom w

end AuditHarness
