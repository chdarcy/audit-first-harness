---
target: PutCallParity
source_refs: [thm:putcall]
lean_declaration: put_call_payoff_parity
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
human_approved_utc: "2026-06-27T00:00:00Z"
---

# PutCallParity — fidelity review

## Source claim
From `thm:putcall` (equation `eq:putcall`): the long-call minus long-put payoff equals the
forward payoff, `max(S - K, 0) - max(K - S, 0) = S - K`, as a pointwise identity in the
reals with no interest-rate or no-arbitrage assumption.

## Lean claim
`put_call_payoff_parity` (root namespace `AuditHarness`, module `AuditHarness.PutCallParity`):
for all `S K : ℝ`, `max (S - K) 0 - max (K - S) 0 = S - K`.

## Assumption comparison
Source: `S, K` real, no further hypotheses. Lean: universally quantified over `S K : ℝ`,
no hypotheses. **No assumption added or dropped.**

## Conclusion comparison
Both state the same identity term-for-term: call payoff `max(S - K, 0)`, put payoff
`max(K - S, 0)`, forward payoff `S - K`. **Direction preserved**; the equation is not
weakened to an inequality or to a single leg.

## Modelling choices
- Payoffs are modelled directly over `ℝ` via `max _ 0`; no separate option/price type is
  introduced. The identity is independent of `S ≥ 0`, so the non-negativity remark in the
  source is not carried as a hypothesis (it is not needed).

## Potential mismatches
- None. The statement is a closed identity; there is no quantifier-scope, vacuity, or
  side-condition subtlety to record.

## Human reviewer notes
Approved as the example/smoke-test target. The Lean statement is a faithful, term-for-term
formalisation of the source identity. This target exists to exercise the pipeline
end-to-end on a trivially-checkable claim; it is not a substantive financial result.
