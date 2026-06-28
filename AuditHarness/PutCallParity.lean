import AuditHarness.PutCallParity.Helpers

/-!
# Put–call payoff parity (smoke-test theorem)

A single, self-contained real-analysis lemma used as the end-to-end smoke test for the audit-first
harness. It is the *payoff* form of put–call parity: at expiry, holding one long call and one short
put (both struck at `K`) on an underlying worth `S` replicates the forward payoff `S - K`:

`max (S - K) 0 - max (K - S) 0 = S - K`.

`max (S - K) 0` is the call payoff, `max (K - S) 0` is the put payoff. This is an identity over the
reals; it carries no financial assumptions (no interest rate, no no-arbitrage), which is exactly
why it is a good minimal target for exercising the pipeline.

This is the **source-facing theorem module**: the statement below is the mapped declaration
(`docs/formal_mapping.yaml`). The `max`-elimination case lemmas live in
`AuditHarness.PutCallParity.Helpers`.
-/

namespace AuditHarness

/-- **Put–call payoff parity.** The long-call minus long-put payoff equals the forward payoff
`S - K`, for every spot `S` and strike `K`. -/
theorem put_call_payoff_parity (S K : ℝ) :
    max (S - K) 0 - max (K - S) 0 = S - K := by
  rcases le_total S K with h | h
  · exact put_call_payoff_parity_of_le S K h
  · exact put_call_payoff_parity_of_ge S K h

end AuditHarness
