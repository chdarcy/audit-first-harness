# Agent instructions for audit-first-harness

## Lean readability convention

For nontrivial Lean targets, split source-facing theorem statements from proof-engineering helpers.

Use this pattern:

- `AuditHarness/<Target>.lean`
  - final source-facing theorem(s);
  - short, readable proofs;
  - imports the helper module(s).

- `AuditHarness/<Target>/Helpers.lean`
  - definitions;
  - algebraic identities;
  - technical / minimality lemmas;
  - proof-engineering details such as `ring_nf`, `field_simp`, `ring`, `linarith`, etc.

`docs/formal_mapping.yaml` must point to the final source-facing theorem in the main module, not to
an internal helper lemma.

Do not weaken theorem statements to simplify proofs. If Lean struggles, add helper lemmas.

A definition's fully-qualified name is fixed by its **namespace, not its file**: moving a `def` or
lemma into a helper module (keeping the same `namespace`) leaves its name stable, so the Comparator
triple, mutants, and mapping are unaffected. Comparator `Challenge`/`Solution` files import the
public theorem module (or the `AuditHarness` umbrella), not internal helper modules.

The worked targets `PutCallParity` and `TwoAssetMinVar` follow this convention; see
`ARCHITECTURE.md` §5.1.
