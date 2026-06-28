-- Root of the AuditHarness example library.
--
-- This is the *minimal* Lean library shipped with the audit-first harness. It exists only
-- to give the pipeline a real, buildable target to operate on (the put–call payoff parity
-- smoke-test theorem). It is NOT a mathematics library; add your own modules here.
import AuditHarness.PutCallParity
import AuditHarness.TwoAssetMinVar
