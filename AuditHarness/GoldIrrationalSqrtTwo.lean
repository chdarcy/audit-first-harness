import Mathlib.NumberTheory.Real.Irrational

/-!
# Gold reference target — irrationality of √2

A **pre-v0.3 public gold-reference target**: a known-correct public theorem whose Lean proof
already exists in Mathlib. The source claim is `√2 ∉ ℚ`; the mapped Lean statement is
`Irrational (√2)`, proved by delegating to Mathlib's `irrational_sqrt_two`
(`Mathlib/NumberTheory/Real/Irrational.lean`).

This target is **not** an original finance theorem and contains **no new proof** — it is a thin
wrapper around the library theorem. It exists to exercise the harness's source-to-Lean fidelity
machinery (and, later, the v0.3 judgement layer) against a public, known-correct reference.

This is the **source-facing theorem module** (the mapped declaration in `docs/formal_mapping.yaml`).
The proof is a one-line delegation, so no helper module is needed.
-/

namespace AuditHarness

/-- **Gold/reference target: the square root of 2 is irrational.** A thin wrapper delegating to
Mathlib's `irrational_sqrt_two`; the statement is exactly `Irrational (√2)`. -/
theorem gold_irrational_sqrt_two : Irrational (√2) :=
  irrational_sqrt_two

end AuditHarness
