import Mathlib.Data.Real.Basic

/-!
# Comparator Challenge — Two-asset minimum-variance weight

A *Mathlib-only* statement of `two_asset_min_variance_weight`. The portfolio-variance helper
`twoAssetVariance` is a project definition, so the Challenge copies it (byte-identically) into the
dedicated `AuditHarness.StatementAudit` namespace and states the theorem with `:= by sorry`; the
matching `Solution.lean` supplies a real proof by delegating to the library theorem.
-/

namespace AuditHarness.StatementAudit

/-- Mathlib-only copy of `AuditHarness.twoAssetVariance` (identical body). -/
def twoAssetVariance (sigma1Sq sigma2Sq sigma12 w : ℝ) : ℝ :=
  w ^ 2 * sigma1Sq + (1 - w) ^ 2 * sigma2Sq + 2 * w * (1 - w) * sigma12

/-- **Two-asset minimum-variance weight** (challenge statement): the variance is minimised over
all real weights at `w* = (sigma2Sq - sigma12) / (sigma1Sq + sigma2Sq - 2 * sigma12)`. -/
theorem two_asset_min_variance_weight
    (sigma1Sq sigma2Sq sigma12 : ℝ)
    (hdenom : 0 < sigma1Sq + sigma2Sq - 2 * sigma12) :
    ∀ w : ℝ,
      twoAssetVariance sigma1Sq sigma2Sq sigma12
          ((sigma2Sq - sigma12) / (sigma1Sq + sigma2Sq - 2 * sigma12))
        ≤ twoAssetVariance sigma1Sq sigma2Sq sigma12 w := by
  sorry

end AuditHarness.StatementAudit
