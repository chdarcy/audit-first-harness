# ROADMAP — active next steps

The authoritative list of what comes next. For the stable design see
[`../ARCHITECTURE.md`](../ARCHITECTURE.md); for dated history see [`MILESTONES.md`](MILESTONES.md);
for the archived audit snapshot see [`GAP_ANALYSIS.md`](GAP_ANALYSIS.md).

## Where we are

The harness is implemented and exercised on three worked targets, the generic source-formalisation
layer exists, and the first content-bearing source intake (Markowitz) is done — at the
**source-inventory stage only**. Source: `examples/markowitz_lecture_notes/source.tex`; inventory:
`docs/source_inventories/markowitz_lecture_notes.yaml` (12 candidate targets). **Nothing in the
inventory is proved, mapped, or verified.**

## Current next steps (Markowitz, conservative algebraic-first path)

1. **Promote `MK-000` + `MK-003` into per-target source-formalisation records** under
   `docs/source_formalizations/` (validated by `scripts/validate_source_formalization.py`).
   - `MK-000` — algebraic scaffolding (`Σ` a given symmetric positive-definite matrix; `μ`, `1`;
     scalars `A, B, C, D`; portfolio with budget `wᵀ1 = 1`; mean/variance).
   - `MK-003` — the `D = BC − A² > 0` (and `C > 0`, `B > 0`) Cauchy–Schwarz lemma; the recommended
     first proof target (small, purely algebraic, high reuse).
2. **Theorem card for `MK-003`: done.** `docs/theorem_index.yaml` entry
   `thm:markowitz_lemma_d_positive` (source-side, unmapped). The **formal mapping is deferred**: a
   draft `docs/formal_mapping.yaml` entry cannot pass `validate_mapping.py` yet — it requires an
   existing Lean declaration, Comparator config, and review file, and there is no draft/unimplemented
   mapping state. Smallest follow-up: add a draft-mapping lifecycle to `validate_mapping.py` that
   skips the Lean/Comparator/review checks for a target explicitly marked draft, then add the
   source↔Lean bridge for `MarkowitzLemmaDPositive`.
3. **Write the Lean scaffolding / theorem statement** — `AuditHarness/<Target>.lean` (readable
   public statement) + a `Helpers.lean` proof module, per [`../CLAUDE.md`](../CLAUDE.md) §5.1. Do not
   weaken the statement to ease the proof.
4. **Prove it and run the formal layer** — `lake build`, no-sorry scan, kernel/axiom audit.
5. **Add source-fidelity review + mutants + a blinded judge package** for the target, and run the
   pre-proof source-fidelity review gate.
6. **Add the Comparator triple** (`Audit/<Target>/`) and record promotion-gate evidence.

Then iterate down the recommended inventory sequence (`MK-007` two-fund, `MK-004` frontier,
`MK-005` parabola, `MK-006` GMVP, `MK-008` risk-free/CML, `MK-009` one-fund/tangency).

## Deferred / out of scope for the first pass

- Probabilistic foundations (`MK-001` L² returns, `MK-002` Cov→PSD bridge) — crosses the
  probabilistic↔algebraic abstraction boundary; needs probability-library support.
- Full KKT / convex-optimisation global-uniqueness half of `MK-004`.
- `MK-010` (tangency maximises Sharpe — Kantorovich) and `MK-011` (CAPM — relies on unstated
  equilibrium economics; the source proof is a sketch).

## Standing constraints (carried into all of the above)

- Formal correctness ≠ source fidelity; judge metrics ≠ theorem truth.
- The judge is a calibrated source-fidelity reviewer, not a theorem oracle; a judge PASS never
  overrides a formal failure.
- The source-fidelity review gate is **pre-proof and non-mutating** (never edits Lean).
- The Comparator checks Challenge/Solution equality, not source-`.tex` vs Lean.
- Live judge/API calls are opt-in only.
- The closed-loop controller (judge output *driving* statement revision) remains future research.
