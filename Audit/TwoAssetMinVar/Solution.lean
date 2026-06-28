import AuditHarness

/-!
# Comparator Solution — Two-asset minimum-variance weight

Restates `two_asset_min_variance_weight` with the **identical** statement and the **same** copied
`twoAssetVariance` (byte-identical to `Challenge.lean`) in the `AuditHarness.StatementAudit`
namespace, so the two audited statements are identical for the Comparator. The proof delegates to
the library theorem `_root_.AuditHarness.two_asset_min_variance_weight`; the copied definition is
definitionally equal to the project one, so the delegating term type-checks.
-/

namespace AuditHarness.StatementAudit

/-- Same Mathlib-only copy of `twoAssetVariance` as the Challenge (identical body). -/
def twoAssetVariance (sigma1Sq sigma2Sq sigma12 w : ℝ) : ℝ :=
  w ^ 2 * sigma1Sq + (1 - w) ^ 2 * sigma2Sq + 2 * w * (1 - w) * sigma12

/-- **Two-asset minimum-variance weight** (solution): identical statement to the challenge, proved
by delegating to the library theorem `_root_.AuditHarness.two_asset_min_variance_weight`. -/
theorem two_asset_min_variance_weight
    (sigma1Sq sigma2Sq sigma12 : ℝ)
    (hdenom : 0 < sigma1Sq + sigma2Sq - 2 * sigma12) :
    ∀ w : ℝ,
      twoAssetVariance sigma1Sq sigma2Sq sigma12
          ((sigma2Sq - sigma12) / (sigma1Sq + sigma2Sq - 2 * sigma12))
        ≤ twoAssetVariance sigma1Sq sigma2Sq sigma12 w :=
  _root_.AuditHarness.two_asset_min_variance_weight sigma1Sq sigma2Sq sigma12 hdenom

end AuditHarness.StatementAudit
