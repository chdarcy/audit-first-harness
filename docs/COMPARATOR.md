# Comparator stage

The harness's final audit stage uses the
[Lean FRO Comparator](https://github.com/leanprover/comparator). For each target it
re-elaborates a **Mathlib-only** statement of the theorem (`Audit/<Target>/Challenge.lean`),
exports it, builds and exports an identical statement proved by delegating to the library
(`Audit/<Target>/Solution.lean`), confirms the two exported statements are identical, checks
the axioms against `permitted_axioms`, and has the Lean kernel accept the proof. Success prints:

```
Your solution is okay!
```

This stage is **human-gated** in `scripts/rebuild_pipeline.py` (run with `--with-comparator`),
and the Comparator's execution sandbox is **Linux-only**.

## Audit triple shape

`Audit/<Target>/` holds three files (see `Audit/PutCallParity/` for a worked example and
`Audit/Template/` for skeletons):

- `Challenge.lean` — *Mathlib-only*; copies the minimal definitions to state the theorem into
  the `AuditHarness.StatementAudit` namespace; states it with `:= by sorry`. **Never** use the
  umbrella `import Mathlib`; import only the specific modules you need.
- `Solution.lean` — imports the full library, repeats the identical statement, proves it by
  delegating: `exact _root_.<lib_thm> args` (the `_root_.` escapes the same-named
  `StatementAudit` theorem). If the statement mentions a project `structure`/`class`/`inductive`,
  repack it through the anonymous constructor (a copied structure is a fresh, non-defeq type).
- `comparator.json` — `challenge_module`, `solution_module`, `theorem_names`,
  `permitted_axioms` (`propext`, `Quot.sound`, `Classical.choice`), `enable_nanoda`.

## Build the triple (any platform, native)

```bash
lake build Audit.PutCallParity.Challenge Audit.PutCallParity.Solution
# Challenge emits an expected `sorry` warning; Solution must build clean.
```

## Run the Comparator (Linux / WSL)

One-time: build the Comparator, a version-matched `lean4export` (matching this project's Lean
version), and `landrun`, then point the harness at them via environment variables:

```bash
export COMPARATOR_BIN="$HOME/tools/comparator/.lake/build/bin/comparator"
export COMPARATOR_LEAN4EXPORT="$HOME/tools/lean4export/.lake/build/bin/lean4export"
export COMPARATOR_LANDRUN="$HOME/tools/landrun/landrun"   # real Landlock sandbox
```

Then either run a single target directly:

```bash
lake build Audit.PutCallParity.Challenge Audit.PutCallParity.Solution
lake env "$COMPARATOR_BIN" Audit/PutCallParity/comparator.json
```

or let the pipeline drive every target and record the result:

```bash
python scripts/rebuild_pipeline.py --with-build --with-comparator
```

If the three `COMPARATOR_*` binaries are not set, or the platform is not Linux, the pipeline
records the stage as `SKIPPED_COMPARATOR_TOOL_UNAVAILABLE` (the `comparator.json` configs are
still checked for existence). `landrun` requires a Linux kernel ≥ 5.13 with
`CONFIG_SECURITY_LANDLOCK=y`; a `fake-landrun.sh` shim (unsandboxed, insecure) can stand in for
local dev on hosts without Landlock.

The Comparator invokes `landrun` with `--best-effort`, so on a kernel that exposes only an older
Landlock ABI (e.g. WSL, which commonly reports ABI 3) the sandbox **degrades** to what that ABI
supports rather than failing. Record the achieved mode honestly in `comparator_status`
(see [`ARCHITECTURE.md`](../ARCHITECTURE.md) §13.4): one of `PASSED_REAL_LANDRUN`,
`PASSED_REAL_LANDRUN_BEST_EFFORT`, `PASSED_FAKE_LANDRUN`, `SKIPPED_COMPARATOR_TOOL_UNAVAILABLE`,
or `FAILED_COMPARATOR`. `PASSED_FAKE_LANDRUN` is **not** a real sandbox and must never be treated
as a high-confidence pass.
