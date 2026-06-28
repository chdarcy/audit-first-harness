---
target: GoldIrrationalSqrtTwo
source_refs: [thm:gold_irrational_sqrt_two]
lean_declaration: gold_irrational_sqrt_two
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

# GoldIrrationalSqrtTwo — fidelity review

## Source claim
From `thm:gold_irrational_sqrt_two` (`examples/gold_irrational_sqrt_two/source.tex`): the square
root of 2 is irrational, `√2 ∉ ℚ`. A public, known-correct reference theorem (item 1 of Freek
Wiedijk's "Formalizing 100 Theorems").

## Lean claim
`gold_irrational_sqrt_two` (root namespace `AuditHarness`, module
`AuditHarness.GoldIrrationalSqrtTwo`): `Irrational (√2)`. The proof is a one-line delegation to
Mathlib's `irrational_sqrt_two` — this is a **wrapper around the existing library theorem**, not a
new proof.

## Fidelity checklist
- **Source says √2 is irrational.** The source asserts `√2 ∉ ℚ`, i.e. √2 is not rational.
- **Lean theorem says `Irrational (√2)`.** In Mathlib, `Irrational x` is defined as
  `x ∉ Set.range ((↑) : ℚ → ℝ)` — exactly "x is not equal to any rational", so
  `Irrational (√2)` is `√2 ∉ ℚ`. **Conclusion identical.**
- **No extra assumptions.** Both the source and the Lean statement are **unconditional** — no
  hypotheses are added.
- **No approximation statement.** The Lean statement is irrationality, not a numeric bound such as
  `1.414 < √2`.
- **No weaker statement.** It is not the strictly weaker `√2 ≠ 2`, and not merely positivity
  `0 < √2`; it is full irrationality.
- **Constant matches.** It is about `√2` (the real square root of 2), not `√3` or a rational
  decimal literal.
- **Vacuity.** `Irrational (√2)` is a true, non-vacuous statement (no contradictory hypotheses).

## Verdict
**PASS** — the Lean statement is exactly the source claim (`Irrational (√2)` ≡ `√2 ∉ ℚ`), proved by
delegating to the known Mathlib theorem `irrational_sqrt_two`. This is a pre-v0.3 public
gold-reference fixture, included to test source-to-Lean fidelity (and later the judgement layer)
against a known-correct public theorem.
