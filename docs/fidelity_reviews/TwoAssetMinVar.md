---
target: TwoAssetMinVar
source_refs: [thm:two_asset_minvar]
lean_declaration: two_asset_min_variance_weight
verdict: PASS
rubric:
  A_assumptions: match
  B_conclusion: identical
  C_quantifiers: match
  D_variables: match
  E_vacuity: non_vacuous
  F_direction: preserved
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
human_approved: true
human_approver: "Example Reviewer"
human_approved_utc: "2026-06-28T00:00:00Z"
---

# TwoAssetMinVar — fidelity review

## Source claim
From `thm:two_asset_minvar` (`examples/two_asset_minvar/source.tex`): for two risky assets with
variance parameters `σ₁²`, `σ₂²` and covariance `σ₁₂`, the portfolio variance
`V(w) = w² σ₁² + (1-w)² σ₂² + 2 w (1-w) σ₁₂` is minimised over **all real weights** at
`w* = (σ₂² - σ₁₂) / (σ₁² + σ₂² - 2σ₁₂)`, provided `σ₁² + σ₂² - 2σ₁₂ > 0`; equivalently
`V(w*) ≤ V(w)` for every real `w`.

## Lean claim
`two_asset_min_variance_weight` (root namespace `AuditHarness`, module
`AuditHarness.TwoAssetMinVar`), with `twoAssetVariance sigma1Sq sigma2Sq sigma12 w` defined as
`w^2 * sigma1Sq + (1 - w)^2 * sigma2Sq + 2 * w * (1 - w) * sigma12`:
given `hdenom : 0 < sigma1Sq + sigma2Sq - 2 * sigma12`, for all `w : ℝ`,
`twoAssetVariance … ((sigma2Sq - sigma12) / (sigma1Sq + sigma2Sq - 2 * sigma12)) ≤ twoAssetVariance … w`.

## Fidelity checklist
- **Assumptions match.** The only hypothesis is `0 < σ₁² + σ₂² - 2σ₁₂` (the quadratic
  coefficient / denominator). No extra `σ₁² > 0` or `σ₂² > 0` positivity is added — the
  inequality does not need it. **No assumption added or dropped.**
- **Conclusion matches.** Both state `V(w*) ≤ V(w)` with the same `V` and the same closed-form
  `w*`. The variance formula matches term-for-term, including the `2 w (1-w) σ₁₂` covariance
  term and its sign.
- **Variables match.** `sigma1Sq ↔ σ₁²`, `sigma2Sq ↔ σ₂²`, `sigma12 ↔ σ₁₂`, `w ↔ w`,
  `w* ↔ (σ₂² - σ₁₂)/denom`.
- **Quantifiers / domain match.** The Lean theorem quantifies `∀ w : ℝ` — the **whole real
  line**. There is **no long-only `0 ≤ w ≤ 1` constraint**; the source likewise says "all real
  weights."
- **Non-strict global minimiser.** The conclusion is `≤` (non-strict). It is not strengthened to
  strict `<` (which would be false at `w = w*`) nor to optimality-with-uniqueness.
- **No uniqueness claim.** Neither the source nor the Lean statement asserts that `w*` is the
  *unique* minimiser; only that it attains the minimum.
- **Vacuity.** The hypothesis `0 < σ₁² + σ₂² - 2σ₁₂` is satisfiable (e.g. `σ₁²=σ₂²=1, σ₁₂=0` →
  `denom = 2`), so the theorem is **non-vacuous**.

## Proof note
The proof is algebraic: `V(w) - V(w*) = denom · (w - w*)²` with `denom > 0`, so the difference is
non-negative (`field_simp; ring` for the identity, then `linarith`). No calculus, no `sorry`.

## Verdict
**PASS** — direct, term-for-term formalisation of the source claim with matching domain,
conclusion, and hypothesis. This is the second worked target exercising the pipeline end-to-end.
