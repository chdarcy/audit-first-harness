import Mathlib.Data.Real.Basic
import Mathlib.Tactic.Linarith

/-!
# Put–call payoff parity — proof helpers

Proof-engineering helpers for `AuditHarness.put_call_payoff_parity`. The two `max`-elimination
case lemmas live here so the public theorem module
(`AuditHarness/PutCallParity.lean`) reads as a short, source-facing statement. These are internal
lemmas; the mapped, source-facing declaration is the theorem in the public module.
-/

namespace AuditHarness

/-- Case `S ≤ K` (the call is out of the money, the put is in): both payoff legs collapse and the
identity follows by `linarith`. -/
theorem put_call_payoff_parity_of_le (S K : ℝ) (h : S ≤ K) :
    max (S - K) 0 - max (K - S) 0 = S - K := by
  rw [max_eq_right (sub_nonpos.mpr h), max_eq_left (sub_nonneg.mpr h)]
  linarith

/-- Case `K ≤ S` (the call is in the money, the put is out): symmetric to
`put_call_payoff_parity_of_le`. -/
theorem put_call_payoff_parity_of_ge (S K : ℝ) (h : K ≤ S) :
    max (S - K) 0 - max (K - S) 0 = S - K := by
  rw [max_eq_left (sub_nonneg.mpr h), max_eq_right (sub_nonpos.mpr h)]
  linarith

end AuditHarness
