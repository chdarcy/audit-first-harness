-- Root of the AuditHarness example library.
--
-- ===========================================================================================
-- LEAN AUTHORING RULE — read before adding or editing any target (see PROJECT_CONTEXT.md §7.1)
--
-- Split every nontrivial target into two modules:
--   * AuditHarness/<Target>.lean          PUBLIC, source-facing theorem (the mapped declaration);
--                                          short readable proof; imports the helper module(s).
--   * AuditHarness/<Target>/Helpers.lean  definitions, algebraic identities, technical/minimality
--                                          lemmas, proof-engineering (ring_nf, field_simp, ring,
--                                          linarith, ...).
--
-- docs/formal_mapping.yaml must point to the FINAL source-facing theorem in the public module,
-- never to an internal helper. NEVER weaken a theorem statement to simplify its proof — add helper
-- lemmas instead. A declaration's fully-qualified name is fixed by its NAMESPACE, not its file, so
-- moving lemmas into Helpers (same namespace) keeps the mapping / Comparator triple / mutants stable.
-- To add a target, create the two modules above and add one `import AuditHarness.<Target>` line below.
-- ===========================================================================================
--
-- This is the *minimal* Lean library shipped with the audit-first harness. It is NOT a mathematics
-- library; it exists to give the pipeline real, buildable targets to operate on.
import AuditHarness.PutCallParity
import AuditHarness.TwoAssetMinVar
import AuditHarness.GoldIrrationalSqrtTwo
