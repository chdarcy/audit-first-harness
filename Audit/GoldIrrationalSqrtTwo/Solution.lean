import AuditHarness

/-!
# Comparator Solution — Irrationality of √2

Restates `gold_irrational_sqrt_two` with the **identical** statement in the
`AuditHarness.StatementAudit` namespace, so the two audited statements are identical for the
Comparator. The proof delegates to the public wrapper theorem
`_root_.AuditHarness.gold_irrational_sqrt_two` (which itself delegates to Mathlib's
`irrational_sqrt_two`).
-/

namespace AuditHarness.StatementAudit

/-- **Irrationality of √2** (solution): identical statement to the challenge, proved by delegating
to the public wrapper theorem. -/
theorem gold_irrational_sqrt_two : Irrational (√2) :=
  _root_.AuditHarness.gold_irrational_sqrt_two

end AuditHarness.StatementAudit
