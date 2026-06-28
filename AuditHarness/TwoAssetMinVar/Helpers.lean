import Mathlib.Data.Real.Basic
import Mathlib.Tactic.FieldSimp
import Mathlib.Tactic.Ring
import Mathlib.Tactic.Linarith

/-!
# Two-asset minimum-variance portfolio — definitions and proof helpers

The portfolio-variance definition and the proof-engineering lemmas for
`AuditHarness.two_asset_min_variance_weight` live here, so the public theorem module
(`AuditHarness/TwoAssetMinVar.lean`) reads as a short, source-facing statement with a one-line
proof. `twoAssetVariance` keeps its fully-qualified name `AuditHarness.twoAssetVariance` (the
namespace, not the file, fixes the name), so the Comparator triple and mutants are unaffected.
-/

namespace AuditHarness

/-- Variance of a two-asset portfolio with weight `w` in asset 1 and `1 - w` in asset 2, with
variance parameters `sigma1Sq`, `sigma2Sq` and covariance `sigma12`. -/
def twoAssetVariance (sigma1Sq sigma2Sq sigma12 w : ℝ) : ℝ :=
  w ^ 2 * sigma1Sq + (1 - w) ^ 2 * sigma2Sq + 2 * w * (1 - w) * sigma12

/-- **Completed-square identity.** With `denom = sigma1Sq + sigma2Sq - 2 * sigma12 ≠ 0` and
`w* = (sigma2Sq - sigma12) / denom`, the variance gap is exactly `denom * (w - w*)²`. This is the
`field_simp` / `ring` heavy lifting, kept out of the public theorem. -/
theorem twoAssetVariance_sub_argmin
    (sigma1Sq sigma2Sq sigma12 w : ℝ)
    (hd : sigma1Sq + sigma2Sq - 2 * sigma12 ≠ 0) :
    twoAssetVariance sigma1Sq sigma2Sq sigma12 w
        - twoAssetVariance sigma1Sq sigma2Sq sigma12
            ((sigma2Sq - sigma12) / (sigma1Sq + sigma2Sq - 2 * sigma12))
      = (sigma1Sq + sigma2Sq - 2 * sigma12)
          * (w - (sigma2Sq - sigma12) / (sigma1Sq + sigma2Sq - 2 * sigma12)) ^ 2 := by
  unfold twoAssetVariance
  field_simp
  ring

/-- **Minimality at `w*`.** When `denom > 0` the variance gap `denom * (w - w*)²` is non-negative,
so `w* = (sigma2Sq - sigma12) / denom` attains a value `≤` that at any real `w`. -/
theorem twoAssetVariance_argmin_le
    (sigma1Sq sigma2Sq sigma12 : ℝ)
    (hdenom : 0 < sigma1Sq + sigma2Sq - 2 * sigma12) (w : ℝ) :
    twoAssetVariance sigma1Sq sigma2Sq sigma12
        ((sigma2Sq - sigma12) / (sigma1Sq + sigma2Sq - 2 * sigma12))
      ≤ twoAssetVariance sigma1Sq sigma2Sq sigma12 w := by
  have hsub := twoAssetVariance_sub_argmin sigma1Sq sigma2Sq sigma12 w (ne_of_gt hdenom)
  have hnn : 0 ≤ (sigma1Sq + sigma2Sq - 2 * sigma12)
      * (w - (sigma2Sq - sigma12) / (sigma1Sq + sigma2Sq - 2 * sigma12)) ^ 2 :=
    mul_nonneg hdenom.le (sq_nonneg _)
  linarith [hsub, hnn]

end AuditHarness
