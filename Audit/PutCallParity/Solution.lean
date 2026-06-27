import AuditHarness

/-!
# Comparator Solution — Put–call payoff parity

Restates `put_call_payoff_parity` with the **identical** statement and the **same**
`AuditHarness.StatementAudit` namespace as `Challenge.lean`, so the two theorem statements
are identical for the Comparator. The proof delegates to the library theorem
`_root_.AuditHarness.put_call_payoff_parity`.
-/

namespace AuditHarness.StatementAudit

/-- **Put–call payoff parity** (solution): identical statement to the challenge, proved by
delegating to the library theorem. -/
theorem put_call_payoff_parity (S K : ℝ) :
    max (S - K) 0 - max (K - S) 0 = S - K := by
  exact _root_.AuditHarness.put_call_payoff_parity S K

end AuditHarness.StatementAudit
