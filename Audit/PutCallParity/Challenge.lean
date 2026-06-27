import Mathlib.Data.Real.Basic

/-!
# Comparator Challenge — Put–call payoff parity

A *Mathlib-only* statement of `put_call_payoff_parity`. For this smoke-test theorem the
statement needs no project definitions (it is phrased directly in terms of `max` over `ℝ`),
so nothing is copied from the library. The theorem is stated in a dedicated
`AuditHarness.StatementAudit` namespace with the proof left as `sorry`; the matching
`Solution.lean` supplies a real proof by delegating to the library theorem.
-/

namespace AuditHarness.StatementAudit

/-- **Put–call payoff parity** (challenge statement): long call minus long put equals the
forward payoff `S - K`. -/
theorem put_call_payoff_parity (S K : ℝ) :
    max (S - K) 0 - max (K - S) 0 = S - K := by
  sorry

end AuditHarness.StatementAudit
