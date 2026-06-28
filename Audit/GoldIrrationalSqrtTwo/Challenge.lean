import Mathlib.NumberTheory.Real.Irrational

/-!
# Comparator Challenge — Irrationality of √2

A *Mathlib-only* statement of `gold_irrational_sqrt_two`. Both `Irrational` and the `√` notation
come from Mathlib, so nothing is copied from the project: the theorem is stated directly in the
`AuditHarness.StatementAudit` namespace with `:= by sorry`; the matching `Solution.lean` supplies a
real proof by delegating to the public wrapper theorem.
-/

namespace AuditHarness.StatementAudit

/-- **Irrationality of √2** (challenge statement): `Irrational (√2)`. -/
theorem gold_irrational_sqrt_two : Irrational (√2) := by
  sorry

end AuditHarness.StatementAudit
