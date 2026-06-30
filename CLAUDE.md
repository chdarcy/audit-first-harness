# Agent instructions for audit-first-harness

**Read [`PROJECT_CONTEXT.md`](PROJECT_CONTEXT.md) first** — it is the canonical, single source of
truth (architecture, status, pipeline, invariants, Markowitz state, roadmap, blockers, milestone
history, and the full agent operating rules incl. the Lean theorem/helper split convention).

Core rules (the durable detail lives in `PROJECT_CONTEXT.md` — invariants §3, agent rules §30):

- Preserve the **source-fidelity vs formal-correctness** boundary; **judge metrics ≠ theorem truth**.
- Do **not** overclaim proof / mapping / Comparator / judge / promotion status.
- Do **not** create Lean files or formal mappings unless the task explicitly asks.
- Keep **live judge/API calls opt-in** (`run_judge.py --execute-api` only); nothing else calls a model.
- Preserve the **blinding boundary** and the **pre-proof, non-mutating** source-fidelity review gate.
- Preserve the **public theorem / helper split** (`AuditHarness/<Target>.lean` +
  `AuditHarness/<Target>/Helpers.lean`); never weaken a theorem statement to ease a proof.
- Commits are approval-gated: touch exactly the files a task names; restore generated reports rather
  than committing churn.
