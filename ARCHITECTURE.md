# ARCHITECTURE.md — Audit-First Lean Formalisation Harness

**Status:** v0.1 experimental architecture  
**Audience:** Claude Opus / coding agent / human maintainer  
**Repository:** `audit-first-harness`  
**Purpose:** Build a reusable, audit-first pipeline for turning mathematical source claims into Lean formalisation targets while preventing source-to-Lean semantic drift.

**Scope note:** The current repository is **v0.1 — an audit and measurement harness**. It audits, reports, and (via the human-approval *input* gate) gates; it is **not** a fully agentic anti-drift system. The closed-loop controller that would let judge output directly drive statement revision and proof attempts is a **v0.3 research goal** (see §0.1 and §12).

---

## 0. Executive summary

This repository is **not** a general automatic LaTeX-to-Lean solver.

It is an **audit-first formalisation harness**. Its job is to structure, test, and record the path from a source theorem to a Lean theorem so that a human or model agent cannot silently prove the wrong theorem.

The central risk is:

> Lean can prove a theorem that is formally valid but not the theorem the source intended.

The harness therefore separates two validation layers:

1. **Formal validation**
   - Lean build
   - no-sorry/no-admit checks
   - Comparator audit using Challenge/Solution triples
   - permitted axiom checks
   - kernel acceptance

2. **Semantic/fidelity validation**
   - theorem cards extracted or transcribed from source `.tex`
   - source-to-Lean mapping ledger
   - human fidelity review
   - blinded LLM judge
   - mutation tests to measure whether the judge can detect planted semantic defects
   - parse-format metrics for judge output reliability
   - future: non-LLM alignment signal, vacuity checks, unused-hypothesis checks, and closed-loop revision

The current MVP already implements the core audit/reporting stack. The next major architectural step is to make the fidelity judge **drive a promotion/revision gate**, rather than merely produce a report.

**Two boundaries this document keeps sharp:**

1. **Formal correctness ≠ source fidelity.** Lean build, no-sorry, the axiom / `#print axioms` audit, and the Comparator establish *formal proof correctness* and *formal statement equality* (the audited Challenge statement is exactly the statement the Solution proves, under a bounded axiom set). They do **not**, by themselves, establish that the Lean statement matches the source theorem. Source-to-Lean fidelity is the separate job of theorem cards, the mapping, fidelity reviews, the LLM judge, mutation scoring, and human review. In particular, **the Comparator compares Challenge vs Solution, not `.tex` source vs Lean.**
2. **Judge metrics ≠ theorem truth.** **Mutation recall and the consistency false-alarm rate measure judge reliability, not theorem truth.** A judge that misses a planted defect tells you the *judge* is imperfect on that defect class; it does not tell you the real mapping is wrong.

---

## 0.1 Versioned scope (v0.1 / v0.2 / v0.3)

**v0.1 — already implemented (the audit & measurement spine):**

- source cards (`docs/theorem_index.yaml`);
- formal mapping bridge (`docs/formal_mapping.yaml`);
- fidelity reviews and the human-approval **input** gate;
- blinded, hash-provenanced mutation packages (`run_mutants.py --dry-run`);
- live judge runner (`run_judge.py --execute-api`, opt-in);
- judge scoring (`score_judge.py`);
- parse-format metrics + prompt-format hardening;
- textual no-sorry check (`check_sorries.py`);
- Comparator triples (Challenge / Solution / comparator.json);
- a real Comparator run demonstrated end-to-end on **PutCallParity**;
- generated pipeline / validation / mutation reports.

**v0.2 — immediate engineering (no new research):**

- `scripts/gate_decision.py` — a pure, offline promotion gate (§11);
- `rebuild_pipeline.py --target` (§20.2);
- Comparator-status writeback into `formal_mapping.yaml`;
- a cleaner evidence-artifact policy (§15);
- a kernel/axiom audit using `#print axioms` and/or `lean4checker`, augmenting the textual no-sorry scan (§14);
- **TwoAssetMinVar** as the second worked target (§19);
- a real `PASS_PROVABLE_EQUIV` path requiring a *built* in-Lean equivalence lemma (§8, §20.6).

**v0.3 — research extensions:**

- the **closed-loop controller**: judge failure → revise statement / card / mapping → regenerate the Comparator triple → re-judge → prove;
- a FormalAlign-style **non-LLM** alignment signal;
- a **multi-judge ensemble**;
- vacuity and unused-hypothesis checks;
- a blueprint / dependency graph (LeanArchitect-style);
- scaling to a Markowitz mini-suite.

Only once the v0.3 loop exists should the system be described as "agentic anti-drift." Until then it is an audit/measurement harness.

---

## 1. Design principle

The system must never treat successful Lean compilation as sufficient evidence of source fidelity.

A formally proved statement can still be wrong with respect to the source if:

- an assumption was dropped;
- an assumption was strengthened;
- a conclusion was weakened;
- a variable was swapped;
- a denominator condition was omitted;
- uniqueness was claimed in the source but only non-strict optimality was proved;
- a theorem over all real weights was formalised only over long-only weights;
- a geometric statement was replaced by a squared algebraic statement without recording the equivalence;
- a theorem became vacuous due to contradictory hypotheses;
- an unused hypothesis gives a false sense of source coverage.

Therefore the pipeline must explicitly track:

```text
source claim
→ theorem card
→ candidate Lean statement
→ fidelity review / judge
→ proof
→ Comparator audit
→ promotion decision
```

---

## 2. What the harness is

The harness is a repository-level workflow for **traceable formalisation**.

It provides:

- a minimal Lean/Lake project;
- source `.tex` examples;
- theorem-card templates;
- formal mapping templates;
- fidelity review templates;
- mutation-test templates;
- judge prompt;
- judge package generation;
- live judge execution;
- judge scoring;
- parse-format metrics;
- no-sorry scan;
- Comparator Challenge/Solution layout;
- pipeline report generation;
- human-gated build and Comparator stages.

It deliberately keeps the source side, formal side, review side, and judge-evaluation side separate.

---

## 3. What the harness is not

The harness is **not**:

- an automatic LaTeX parser;
- an automatic theorem extractor;
- an automatic Lean proof generator;
- an autonomous proof search system;
- a guarantee that the LLM judge is correct;
- a replacement for human mathematical review;
- a replacement for Lean or Comparator.

A model agent may help write theorem cards, Lean statements, proofs, and reviews. However, the harness must treat model output as **untrusted until validated**.

---

## 4. High-level pipeline

The intended architecture is:

```text
source.tex
  ↓
theorem_index.yaml
  ↓
formal_mapping.yaml
  ↓
fidelity_reviews/<Target>.md
  ↓
candidate Lean statement
  ↓
judge package generation
  ↓
fidelity judge
  ↓
judge scoring against mutants
  ↓
candidate fidelity gate (pre-proof)
  ↓
Lean proof
  ↓
lake build
  ↓
no-sorry check
  ↓
Audit/<Target>/Challenge.lean
Audit/<Target>/Solution.lean
Audit/<Target>/comparator.json
  ↓
Comparator real-landrun check
  ↓
pipeline report
  ↓
promotion decision
```

The current MVP implements most of this path. The missing piece is the **closed-loop controller** that turns judge/gate results into required revisions.

---

## 5. Repository layout

Expected structure:

```text
audit-first-harness/
├── README.md
├── ARCHITECTURE.md
├── LICENSE
├── lean-toolchain
├── lakefile.toml
├── lake-manifest.json                 # if generated and appropriate
├── requirements.txt
│
├── AuditHarness.lean
├── AuditHarness/
│   └── PutCallParity.lean             # example theorem
│
├── Audit/
│   ├── Template/
│   │   ├── Challenge.lean.template
│   │   ├── Solution.lean.template
│   │   └── comparator.json.template
│   └── PutCallParity/
│       ├── Challenge.lean
│       ├── Solution.lean
│       └── comparator.json
│
├── examples/
│   └── put_call_parity/
│       └── source.tex
│
├── docs/
│   ├── COMPARATOR.md
│   ├── theorem_index.yaml
│   ├── formal_mapping.yaml
│   ├── validation_report.md           # generated
│   ├── mutation_report.md             # generated / updated
│   ├── pipeline_report.md             # generated
│   │
│   ├── templates/
│   │   ├── theorem_card.template.yaml
│   │   ├── mapping.template.yaml
│   │   ├── fidelity_review.template.md
│   │   └── mutants.template.yaml
│   │
│   ├── judge_prompts/
│   │   └── judge_v1.md
│   │
│   ├── fidelity_reviews/
│   │   └── PutCallParity.md
│   │
│   ├── mutants/
│   │   └── PutCallParity.yaml
│   │
│   ├── judge_inputs_dryrun/           # generated
│   │   ├── V-0001.yaml
│   │   ├── ...
│   │   ├── _manifest.yaml             # answer key, local only
│   │   └── _targets.yaml              # membership-only sidecar
│   │
│   ├── judge_requests/                # generated manual exports
│   │
│   └── judge_results/                 # generated real/manual judge results
│       ├── PutCallParity.yaml
│       └── PutCallParity_scored.yaml
│
└── scripts/
    ├── validate_mapping.py
    ├── run_mutants.py
    ├── run_judge.py
    ├── score_judge.py
    ├── import_manual_judge_results.py
    ├── check_sorries.py
    ├── rebuild_pipeline.py
    └── test_judge_parsing.py
```

---

## 6. Core ledger files

### 6.1 `docs/theorem_index.yaml`

This is the **source-side theorem ledger**.

It should describe the mathematical claim from the source document without mentioning Lean declarations.

It answers:

- What does the source claim?
- Where is the claim in the source?
- What are the source assumptions?
- What is the source conclusion?
- What informal interpretation should the formaliser preserve?
- Is the theorem exact, geometric, algebraic, probabilistic, asymptotic, etc.?

It should not contain:

- Lean theorem names;
- proof status;
- Comparator configs;
- judge verdicts;
- mutation labels.

Example shape:

```yaml
version: "0.1"

entries:
  thm:two_asset_minvar:
    auto:
      source_file: examples/two_asset_minvar/source.tex
      title: Two-asset minimum-variance portfolio
      body_tex: |
        Let two risky assets have variance parameters ...
    curated:
      paraphrase: >
        For two risky assets with variance parameters sigma1_sq and sigma2_sq
        and covariance sigma12, the quadratic portfolio variance is minimized
        over all real weights at the stated closed-form weight, assuming the
        quadratic coefficient is positive.
      informal_assumptions:
        - sigma1_sq and sigma2_sq are positive real variance parameters.
        - sigma12 is a real covariance parameter.
        - sigma1_sq + sigma2_sq - 2 sigma12 is positive.
        - The minimisation domain is all real weights, not only long-only weights.
      notes:
        - This version states non-strict optimality, not uniqueness.
```

### 6.2 `docs/formal_mapping.yaml`

This is the **source-to-Lean bridge**.

It answers:

- Which source claim maps to which Lean declaration?
- Which Lean module contains the theorem?
- Which Comparator triple audits it?
- What is the current lifecycle state?
- Has a human approved the mapping?
- What is the Comparator status?

It should not contain the full mathematics or prose review.

Example shape:

```yaml
version: "0.1"

permitted_axioms: [propext, Quot.sound, Classical.choice]

targets:
  TwoAssetMinVar:
    source_refs: ["thm:two_asset_minvar"]
    lean:
      declaration: two_asset_min_variance_weight
      module: AuditHarness.TwoAssetMinVar
      fully_qualified: AuditHarness.two_asset_min_variance_weight
    comparator:
      dir: Audit/TwoAssetMinVar
      config: Audit/TwoAssetMinVar/comparator.json
      challenge_module: Audit.TwoAssetMinVar.Challenge
      solution_module: Audit.TwoAssetMinVar.Solution
      audit_theorem: AuditHarness.StatementAudit.two_asset_min_variance_weight
    verdict: PASS
    equivalence: null
    comparator_status: NOT_RUN
    review: docs/fidelity_reviews/TwoAssetMinVar.md
    state: HUMAN_APPROVED
    human_approved: true
```

### 6.3 `docs/fidelity_reviews/<Target>.md`

This is the **human-readable semantic review**.

It should explain why the Lean statement is faithful to the source, using a checklist:

- assumptions;
- conclusion;
- variables;
- quantifiers;
- representation choices;
- algebraic reformulations;
- caveats;
- verdict.

It should use YAML frontmatter so scripts can check consistency.

Example frontmatter:

```yaml
---
target: TwoAssetMinVar
source_refs: [thm:two_asset_minvar]
lean_declaration: two_asset_min_variance_weight
verdict: PASS
rubric:
  A_assumptions: match
  B_conclusion: identical
  C_quantifiers: match
  D_variables: match
  E_vacuity: non_vacuous
  F_direction: preserved
  G_units_form: match
judge:
  status: NOT_RUN
human_approved: true
human_approver: Christopher Darcy
human_approved_utc: "TODO"
---
```

The body should be plain English. It should be detailed enough that another reviewer can see why the mapping was approved.

### 6.4 `docs/mutants/<Target>.yaml`

This is the **judge calibration file**.

It contains:

- the real statement;
- meaning-preserving variants expected to pass;
- defect-injecting variants expected to fail;
- expected labels;
- mutation operators;
- notes.

It is not sent to the judge directly. `run_mutants.py` creates blinded packages and holds back the answer key.

---

## 7. Blinded judge package design

The judge layer must avoid leaking answer-key information.

`run_mutants.py --dry-run` should:

1. read the source theorem card;
2. read the formal mapping;
3. read the fidelity review;
4. read the mutants file;
5. enforce the human approval gate;
6. create one package per variant;
7. blind the package with deterministic shuffled IDs such as `V-0001`;
8. rename the Lean theorem to a neutral candidate name;
9. write judge-visible packages;
10. write a local `_manifest.yaml` answer key;
11. write a membership-only `_targets.yaml`.

The judge sees:

```text
source claim
candidate Lean statement
ambient information
allowed verdict enum
```

The judge must not see:

- expected verdict;
- mutant class;
- operator;
- target name if forbidden by the leak policy;
- human approval;
- answer key;
- whether it is real or mutated.

---

## 8. Judge prompt

The judge prompt lives at:

```text
docs/judge_prompts/judge_v1.md
```

The judge is an adversarial formalisation-fidelity reviewer.

It compares:

- source assumptions;
- Lean assumptions;
- source conclusion;
- Lean conclusion;
- variable correspondence;
- quantifier scope;
- possible vacuity;
- formula shape;
- representation choices.

Verdict enum:

```text
PASS
PASS_EQUIV
PASS_PROVABLE_EQUIV
WARN
FAIL
OUT_OF_SCOPE
```

Output must be strict YAML.

The prompt must require:

- YAML only;
- no code fences;
- no prose outside YAML;
- quote short free-text scalars;
- block scalars for rationale/equivalence arguments;
- no unquoted `: ` inside scalar text;
- exactly one top-level `verdict:` line.

The parser should still be defensive because models may violate these instructions.

---

## 9. Judge output parsing and recovery

`run_judge.py` owns judge execution and output parsing.

Required behaviour:

- keep `raw_output` unchanged;
- parse strict YAML when possible;
- if full YAML parsing fails, recover only a single unambiguous top-level `verdict:` line;
- preserve `parse_error`;
- set `recovered_verdict: true` when recovery was used;
- set `judge_output: null` for recovered malformed YAML;
- never invent `rationale`, `detected_issues`, or `equivalence_argument` from malformed YAML;
- if multiple conflicting verdict lines appear, mark unrecoverable;
- if no verdict appears, mark unrecoverable.

Tests should cover:

1. valid YAML parses cleanly;
2. unquoted colon in rationale causes full parse failure but allows single-verdict recovery;
3. multiple conflicting verdict lines are unrecoverable;
4. no verdict line is unrecoverable;
5. recovered malformed output preserves raw output and parse error.

---

## 10. Scoring the judge

`score_judge.py` compares judge results against `_manifest.yaml`.

This is local only. The answer key is never sent to the model.

Metrics should include:

### 10.1 Fidelity classification metrics

- `real_mapping_agreement_exact`
- `real_mapping_agreement_bucket`
- `discriminative_recall`
- `consistency_false_alarm_rate`
- `overall_bucket_accuracy`
- `per_operator` detection rates

Interpretation:

- Real mapping should be accepted.
- Consistency mutants should be accepted.
- Discriminative mutants should be rejected.
- A judge that misses discriminative mutants is not a certificate.
- A judge with false alarms on consistency mutants is brittle.

> **Mutation recall and consistency false-alarm rate measure judge reliability, not theorem truth.**

**How to read a missed discriminative mutant:**

- it is **not** an infrastructure / harness failure;
- it is **useful calibration evidence** about the judge (the benchmark found a weakness);
- it should **reduce automation confidence** and/or **require human review**;
- it should **not** be taken as automatic proof that the real theorem mapping is wrong.

### 10.2 Parse-format metrics

- `parsed_clean_count`
- `recovered_verdict_count`
- `unrecoverable_parse_error_count`
- `malformed_yaml_rate`

Interpretation:

- `malformed_yaml_rate = 0.0` is ideal.
- Recovered verdicts are auditable but lower-confidence.
- Unrecoverable parse errors should block automated promotion.

---

## 11. Promotion decision policy

The v0.1 harness mostly **reports**; the only gate today is the *input* human-approval gate. v0.2 adds a **machine-readable promotion gate** as a pure, offline script `scripts/gate_decision.py` (it may also be folded into `rebuild_pipeline.py`, but a standalone script is preferred).

### 11.1 Global vs. local signals

Promotion logic must separate two kinds of signal:

- **Local (this target):** does *this* mapping's formal and fidelity evidence pass? (build, no-sorry, axiom audit, Comparator, real-mapping verdict, provenance/hash match, human approval, review present.)
- **Global (the judge):** how reliable is the *judge itself*, as measured over the mutant set? (`discriminative_recall`, `consistency_false_alarm_rate`, `malformed_yaml_rate`.)

**Global judge-calibration metrics must not, by themselves, hard-block a target whose real mapping passed and whose formal checks passed.** They **cap confidence** and **force HUMAN_REVIEW**; they never produce BLOCK on their own.

### 11.2 Decision rules (ordered)

1. **BLOCK** — any hard formal/integrity failure: Lean build failure; no-sorry / axiom-audit failure; Comparator failure; provenance/hash mismatch (`scored` vs `_manifest`); unrecoverable judge parse error; missing human approval; missing required review; mapped Lean declaration does not exist.
2. **REVISE** or **HUMAN_REVIEW** — the **real mapping** is judged `FAIL`/`WARN` (or the judge flags an essential mismatch on the real statement) with no recorded human override: the **statement/mapping may need revision** (REVISE is the closed-loop trigger; HUMAN_REVIEW if a human must adjudicate first).
3. **HUMAN_REVIEW / lower confidence** — formal checks pass and the real mapping is accepted, but **judge calibration is weak**: low discriminative recall, nonzero consistency false-alarm rate, malformed/recovered YAML, `PASS_EQUIV` without a built equivalence lemma, or single-judge disagreement. Set `confidence: medium|low`.
4. **PROMOTE** — all formal gates pass, the real mapping is accepted, and judge confidence is high.

### 11.3 `gate_decision.py` (v0.2 milestone)

A **pure, offline, idempotent** script. It **must not** call any API, **must not** run the judge, and only **consumes existing artifacts**.

**Inputs:**

- `docs/formal_mapping.yaml` (state, `human_approved`, `comparator_status`, declaration existence);
- `docs/fidelity_reviews/<Target>.md` (frontmatter: approval, rubric, verdict);
- `docs/judge_results/<Target>_scored.yaml` (fidelity + parse-format metrics);
- `docs/judge_inputs_dryrun/_manifest.yaml` (`prompt_sha256`, `mutants_sha256` for provenance match);
- `docs/pipeline_report.md` — or, preferably, a future **structured pipeline JSON** carrying build / no-sorry / Comparator stage results;
- thresholds for `discriminative_recall`, `consistency_false_alarm_rate`, and `malformed_yaml_rate`.

**Output:** `docs/promotion/<Target>.yaml`

```yaml
promotion_decision:
  target: TwoAssetMinVar
  status: PROMOTE | BLOCK | REVISE | HUMAN_REVIEW
  confidence: high | medium | low
  reasons:
    - ...
  allowed_next_steps:
    - ...
  provenance:
    prompt_sha256: ...
    mutants_sha256: ...
    scored_utc: ...
    comparator_status: ...
    landrun_abi: ...
  decided_utc: ...
```

**Guarantees:** no model call; writes only under `docs/promotion/`; never edits `formal_mapping.yaml`, reviews, or mutants; refuses to overwrite without `--force`.

Illustrative decision (PutCallParity, recall 0.667, FAR 0.0, Comparator passed): formal gates and the real mapping pass, so this is **not** a BLOCK; the sub-1.0 discriminative recall caps confidence and yields `status: HUMAN_REVIEW`, `confidence: medium`, with reason "judge missed one planted defect — calibration evidence, not a mapping refutation." This keeps judge metrics in their proper, confidence-capping role and is how the harness becomes more than a report.

### 11.4 Candidate gate vs. promotion gate

The harness has **two** gates, and they must not be conflated:

- **Candidate fidelity gate (pre-proof).** Decides whether the statement/mapping is faithful enough to be *worth proving*. It runs before any Lean proof, on card / mapping / review / judge evidence. A `REVISE` here means "fix the statement before spending effort on a proof."
- **Final promotion gate (post-Comparator).** Decides whether an *already proved and Comparator-checked* target may be marked **promoted**. It additionally consumes build / no-sorry / axiom-audit / Comparator results.

`gate_decision.py` (§11.3) can serve both roles; the available inputs differ (the pre-proof call has no build/Comparator results yet). In §4, the `candidate fidelity gate` is the first gate and the `promotion decision` is the second.

---

## 12. Closed-loop agentic workflow

The desired next version is a loop where judge feedback informs construction.

Current MVP:

```text
candidate exists
→ judge reports
→ human interprets
```

Target architecture:

```text
source.tex
→ agent writes theorem card
→ agent proposes Lean statement
→ judge reviews mapping
→ if FAIL/WARN: agent revises theorem card / Lean statement / mapping
→ repeat until PASS or human override
→ agent attempts Lean proof
→ Lean build
→ Comparator
→ promotion decision
```

A Claude Opus implementation should follow this discipline:

1. Do not start proof search until the candidate statement has a source card and mapping.
2. Run the judge before investing in a long proof.
3. If the judge identifies a mismatch, revise the statement rather than forcing a proof.
4. If the statement changes, regenerate the Comparator Challenge/Solution.
5. Only after statement fidelity is acceptable should proof automation begin.
6. Every override must be recorded in the fidelity review.

---

## 13. Comparator architecture

Comparator validates formal statement equality and kernel acceptance.

For each target:

```text
Audit/<Target>/Challenge.lean
Audit/<Target>/Solution.lean
Audit/<Target>/comparator.json
```

### 13.1 Challenge

Challenge should:

- import only Mathlib or minimal copied definitions;
- not import the project library;
- restate the theorem in the `AuditHarness.StatementAudit` namespace;
- use `:= by sorry` for the theorem body;
- avoid project dependencies.

### 13.2 Solution

Solution should:

- import the project library;
- repeat the identical statement;
- prove it by delegating to the project theorem;
- use `_root_.` if necessary to avoid namespace shadowing.

### 13.3 comparator.json

Should contain:

- challenge module;
- solution module;
- theorem names;
- permitted axioms;
- `enable_nanoda`.

Success means:

```text
Your solution is okay!
```

Comparator does not check source fidelity. It checks that the formal theorem audited in Challenge is exactly the formal theorem proved in Solution.

Restated for emphasis: **the Comparator compares Challenge vs Solution (formal statement equality + kernel acceptance under permitted axioms). It does not compare `.tex` source vs Lean.** Source fidelity is established by the card / mapping / review / judge / human layer, never by the Comparator alone.

### 13.4 Sandbox status vocabulary

The Comparator runs the Challenge build and `lean4export` inside a `landrun` (Landlock) sandbox. The strength of that sandbox is environment-dependent — e.g. under WSL the kernel often exposes only Landlock **ABI 3**, and the Comparator invokes `landrun --best-effort`, which degrades to the available ABI. Do **not** overstate the guarantee. Record the achieved mode in `comparator_status`, using a vocabulary such as:

```text
PASSED_REAL_LANDRUN              # full Landlock sandbox
PASSED_REAL_LANDRUN_BEST_EFFORT  # real landrun, degraded or unverified ABI / best-effort mode
PASSED_FAKE_LANDRUN              # scripts/fake-landrun.sh shim — NOT sandboxed
SKIPPED_COMPARATOR_TOOL_UNAVAILABLE
FAILED_COMPARATOR
```

Where possible also record the Landlock ABI and environment (`landrun_abi`, kernel version) in the evidence bundle and in `promotion_decision.provenance`.

**Gate policy:** the promotion gate must not treat all `PASSED_*` statuses as equal. `PASSED_FAKE_LANDRUN` is a *degraded* audit (the formal proof passed, but the sandbox is not real) and must **not** yield a high-confidence `PROMOTE` without a recorded human override — it caps confidence and routes to `HUMAN_REVIEW`. `PASSED_REAL_LANDRUN_BEST_EFFORT` is intermediate: record it, and policy may lower confidence accordingly.

---

## 14. No-sorry and proof completeness

`check_sorries.py` should fail if any non-Challenge Lean file contains:

- `sorry`
- `admit`
- `sorryAx`
- possibly other incomplete-proof markers

It should skip:

```text
Audit/*/Challenge.lean
Audit/Template/*.template
```

because Challenge files intentionally state the theorem with `sorry`.

Future enhancement:

- use Lean environment inspection rather than textual scanning;
- check for unexpected axioms;
- check imported declarations for axiom pollution if feasible.

**v0.2 — kernel/axiom audit.** The textual scan is a heuristic and can be fooled (macro-generated `sorry`, axiom pollution, `native_decide`). v0.2 should add a kernel-backed check that, for each promoted declaration, verifies via `#print axioms` (and/or `lean4checker`) that its axiom set ⊆ the permitted axioms `{propext, Quot.sound, Classical.choice}` and contains no `sorryAx`. This is the same guarantee the Comparator relies on, applied to the library proof directly.

---

## 15. Artifact and evidence policy

Classify every file into one of four tiers:

- **Source** — committed, reviewed as code: scripts, prompts, templates, README/ARCHITECTURE, `requirements.txt`, source `.tex`, Lean source, Audit templates, tests, and the ledger YAMLs (`theorem_index.yaml`, `formal_mapping.yaml`, mutants, reviews).
- **Fixtures** — committed but regenerated *deliberately* and reviewed when they change: the seeded `docs/judge_inputs_dryrun/V-*.yaml`, `_manifest.yaml`, `_targets.yaml` for the canonical example.
- **Evidence** — a reproducible record of a real run, captured intentionally: judge results, scored results, and the generated reports for a specific run, with provenance (`prompt_sha256`, `mutants_sha256`, model, `comparator_status`, `landrun_abi`).
- **Disposable** — everything else generated locally; not committed.

**Rules:**

- **Do not mix hardening/source commits with evidence-run commits.** A generic hardening commit must **not** include generated judge results or timestamp churn.
- **Evidence-run commits (or evidence bundles) may include generated artifacts intentionally**, with a message that says so (e.g. `Record fresh PutCallParity full harness run`).
- **If the prompt or mutants change, stale generated dry-run artifacts must be regenerated or excluded** — never commit dry-run packages whose `prompt_sha256` no longer matches `judge_v1.md`.
- **Prefer a structured evidence directory or release artifact** for full runs, e.g. `evidence/<UTC>-<target>/`, rather than overwriting the in-tree reports; keep `docs/judge_results/` out of generic commits (gitignore by default).

---

## 16. Environment and cache policy

Do not commit:

```text
.lake/
.elan/
.venv/
__pycache__/
*.pyc
.oai_key
*.key
.env
comparator binaries
landrun binaries
lean4export binaries
WSL build directories
```

Commit reproducibility metadata instead:

```text
lean-toolchain
lakefile.toml
lake-manifest.json
requirements.txt
README.md
docs/COMPARATOR.md
```

The environment should be reproducible by running:

```bash
lake exe cache get
lake build
python -m pip install -r requirements.txt
```

Comparator setup should be documented, not vendored.

---

## 17. API key policy

The live judge uses `OPENAI_API_KEY` from the environment.

Rules:

- never print the key;
- never inspect the key value except for non-empty presence if needed;
- never commit `.oai_key`;
- never commit `.env`;
- never write key values into logs;
- real model calls require explicit `--execute-api`;
- no script should call a model by default.

If the user has a differently named key such as `OPENAI_KEY_API`, ask before aliasing it.

---

## 18. Example target: PutCallParity

The current example is put-call payoff parity:

```lean
theorem put_call_payoff_parity (S K : ℝ) :
    max (S - K) 0 - max (K - S) 0 = S - K
```

It is deliberately small.

Its purpose is to test:

- theorem card;
- mapping;
- review;
- mutants;
- judge package generation;
- live judge;
- parse-format hardening;
- Lean build;
- no-sorry;
- Comparator.

Important interpretation:

If the judge misses a mutant, the harness did not fail. The harness measured that the judge is imperfect.

Say:

```text
Infrastructure passed. Judge benchmark found a weakness.
```

Do not say:

```text
The smoke test failed.
```

---

## 19. Recommended next target: TwoAssetMinVar

A good next target is the two-asset minimum-variance portfolio theorem.

Reasons:

- finance-relevant;
- close to Markowitz;
- small enough for Lean;
- has meaningful fidelity traps;
- proof is algebraic;
- easy to mutate.

Source theorem should avoid uniqueness initially unless the Lean theorem proves uniqueness.

Recommended source claim:

```tex
\documentclass{article}
\usepackage{amsmath}

\begin{document}

\section*{Two-asset minimum-variance portfolio}

Let two risky assets have variance parameters
\[
\sigma_1^2 > 0,
\qquad
\sigma_2^2 > 0,
\]
and covariance parameter \(\sigma_{12}\). Consider a portfolio that invests weight
\(w \in \mathbb{R}\) in asset 1 and weight \(1-w\) in asset 2. Its variance is
\[
V(w)
=
w^2 \sigma_1^2
+
(1-w)^2 \sigma_2^2
+
2w(1-w)\sigma_{12}.
\]

Assume
\[
\sigma_1^2 + \sigma_2^2 - 2\sigma_{12} > 0.
\]

Define
\[
w^\ast
=
\frac{\sigma_2^2 - \sigma_{12}}
{\sigma_1^2 + \sigma_2^2 - 2\sigma_{12}}.
\]

Then \(w^\ast\) minimizes \(V\) over all real weights. Equivalently, for every
\(w \in \mathbb{R}\),
\[
V(w^\ast) \leq V(w).
\]

\end{document}
```

Possible mutants:

- numerator changed to `sigma1Sq - sigma12`;
- denominator condition dropped;
- covariance sign changed;
- domain changed from all real weights to `0 ≤ w ≤ 1`;
- conclusion changed from `≤` to equality;
- portfolio variance drops covariance term;
- `w*` changed to its complement.

---

## 20. Future improvements

### 20.1 Closed-loop controller

Add a controller that uses judge output to decide:

- revise;
- prove;
- block;
- promote;
- human review.

### 20.2 `--target` support in `rebuild_pipeline.py`

The pipeline should support:

```bash
python scripts/rebuild_pipeline.py --target TwoAssetMinVar
```

Currently it may operate over all mapping targets.

This is a **v0.2** task. Per-target operation is needed for:

- **multi-target repos** (don't re-run every target when one changed);
- **closed-loop iteration** on a single theorem under construction;
- **faster CI** (per-target matrix);
- **per-target evidence bundles** (§15).

The no-argument behaviour (all targets) must be preserved.

### 20.3 FormalAlign-style second signal

Add a non-LLM semantic alignment signal:

- embedding similarity;
- statement-alignment score;
- certainty score;
- compare with LLM judge.

Use this as a heterogeneous second opinion.

### 20.4 Kernel-backed vacuity checks

Add tests or generated lemmas to catch vacuous statements.

For example:

- hypotheses are contradictory;
- theorem is provable from impossible assumptions;
- important variables/hypotheses are unused.

### 20.5 Unused-hypothesis linter

Detect if source-critical hypotheses appear in Lean but are not used by the proof.

This is not always an error, but should trigger review.

### 20.6 PASS_PROVABLE_EQUIV

Implement a real path for:

```text
PASS_PROVABLE_EQUIV
```

**Status: v0.2 — wired as a guarded path.** `PASS_PROVABLE_EQUIV` is legitimate only when an in-Lean equivalence lemma is supplied and the equivalence-check stage verifies that it builds and uses only permitted axioms; otherwise it is downgraded to review/blocking evidence per §11.2. Emit it **only if** an in-Lean equivalence lemma is supplied **and builds**; otherwise use `PASS_EQUIV`. Treat any `PASS_PROVABLE_EQUIV` without a built lemma as a calibration flag (→ HUMAN_REVIEW, per §11.2).

Example:

```lean
theorem source_form_iff_lean_form : SourceForm ↔ LeanForm := ...
```

### 20.7 Theorem dependency graph

Move from a flat theorem list to a blueprint graph:

```yaml
nodes:
  - id: thm:...
    depends_on: [...]
    formal_target: ...
```

This helps with large projects such as Markowitz.

### 20.8 Multi-judge ensemble

If a single judge has low discriminative recall, run:

- gpt-4.1;
- o3;
- Claude;
- FormalAlign-style score.

Then gate on consensus or disagreement.

---

## 21. Instructions for Claude Opus

When working in this repo:

1. Do not call the API unless explicitly asked.
2. Do not print or inspect API keys.
3. Do not commit caches.
4. Do not mix hardening commits with evidence-run commits.
5. Do not change theorem statements silently.
6. Do not change mutants or expected labels casually.
7. If a Lean statement changes, update:
   - theorem card if needed;
   - formal mapping if needed;
   - fidelity review;
   - mutants if affected;
   - Comparator Challenge/Solution.
8. Run validation before presenting results.
9. Ask before committing.
10. If the judge reports a mismatch, prefer revising the statement/mapping over forcing a proof.
11. Treat Lean build success as formal proof success, not source-fidelity success.
12. Treat Comparator success as formal statement-audit success, not source-fidelity success.
13. Treat judge success as evidence, not a certificate.
14. Treat mutation-score failures as findings, not infrastructure failures.

---

## 22. Minimal command sequences

### 22.1 Generic non-API validation

```bash
python scripts/validate_mapping.py
python scripts/check_sorries.py
python scripts/run_mutants.py --dry-run
python scripts/rebuild_pipeline.py
lake build
```

### 22.2 Full local build with gated build

```bash
python scripts/rebuild_pipeline.py --with-build
```

### 22.3 Full Comparator run

Requires Linux/WSL and Comparator env vars.

```bash
export COMPARATOR_BIN="$HOME/tools/comparator/.lake/build/bin/comparator"
export COMPARATOR_LEAN4EXPORT="$HOME/tools/lean4export/.lake/build/bin/lean4export"
export COMPARATOR_LANDRUN="$HOME/tools/landrun/landrun"

python scripts/rebuild_pipeline.py --with-build --with-comparator
```

### 22.4 Live judge

Only when explicitly approved.

```bash
python scripts/run_mutants.py --dry-run

python scripts/run_judge.py \
  --target PutCallParity \
  --provider openai \
  --model gpt-4.1 \
  --temperature 0 \
  --execute-api

python scripts/run_judge.py --target PutCallParity --reparse

python scripts/score_judge.py --target PutCallParity --force
```

### 22.5 Fresh theorem workflow

```bash
# 1. Add examples/<target>/source.tex
# 2. Add theorem card
# 3. Add Lean statement
# 4. Add mapping
# 5. Add fidelity review
# 6. Add mutants
# 7. Add Comparator triple

python scripts/validate_mapping.py
python scripts/run_mutants.py --dry-run

# Optional live judge before proof
python scripts/run_judge.py --target <Target> --provider openai --model gpt-4.1 --execute-api
python scripts/score_judge.py --target <Target> --force

# If accepted, prove
lake build
python scripts/check_sorries.py
python scripts/rebuild_pipeline.py --with-build --with-comparator
```

---

## 23. Success criteria for v0.2

The harness reaches v0.2 when it can demonstrate the following on a fresh theorem such as `TwoAssetMinVar`:

1. A fresh `.tex` source is added.
2. Claude/model writes a theorem card.
3. Claude/model proposes a Lean statement.
4. The judge reviews the candidate before proof search.
5. A gate decision is produced.
6. If the candidate is rejected, the gate emits `REVISE` with actionable reasons.
7. The final accepted statement is proved in Lean.
8. Comparator passes real-landrun.
9. The final report records:
   - source card;
   - mapping;
   - fidelity review;
   - judge result;
   - mutation-score reliability;
   - build/no-sorry;
   - Comparator status;
   - promotion decision.

That is the point where the judgement layer is genuinely informing construction, not merely reporting afterwards.

**Automatic or agent-driven revision after a `REVISE` decision is v0.3, not v0.2.** v0.2 only requires that the gate *emits* an actionable `REVISE`; a human acts on it (the v0.3 controller automates that step).

---

## 23.1 Research grounding and references

This remains an architecture document, not a literature review, but the design borrows established ideas and must cite them accurately. Each entry gives the contribution, how it relates to this harness, and whether it supports or challenges the design. Names that could **not** be verified as real projects (e.g. "Goedel-Architect", "TheoremGraph") are deliberately **not** cited; the verified names below should be used instead.

**Traceable informal↔formal structure**

- **Lean blueprints (`leanblueprint`).** plasTeX plugin building informal↔formal dependency graphs (`\uses`, `\leanok`); used in large projects (e.g. PFR). Relates to our ledger (cards/mapping) and to §20.7. *Supports* the traceability premise. <https://github.com/PatrickMassot/leanblueprint>
- **LeanArchitect (2026).** Automates blueprint generation, linking Lean declarations to blueprint metadata with dependency inference and human/AI progress tracking. The mature version of the §20.7 dependency-graph goal. *Note:* LeanArchitect is closer to **Lean→blueprint synchronisation** (extracting/managing blueprint data from Lean code) than raw `.tex`→Lean extraction; this harness currently uses hand-curated theorem cards rather than automatic blueprint extraction. *Supports, with that caveat.* <https://arxiv.org/abs/2601.22554>

**Autoformalization & proof automation**

- **Goedel-Prover / Goedel-Prover-V2.** Open-source Lean 4 whole-proof ATP with autoformalizers and verifier-feedback self-correction. Relates to the proof-automation phase of §12. *Supports* loop feasibility. (Use this name — not "Goedel-Architect".) <https://arxiv.org/abs/2502.07640> · <https://arxiv.org/abs/2508.03613>
- **ProofBridge (2025).** Joint NL↔FL embeddings + iterative repair using Lean's type checker and an LLM equivalence judge. Essentially the §12 closed loop for proofs. *Supports* feasibility; *challenges* novelty and warns of judge-in-the-loop Goodharting. <https://arxiv.org/abs/2510.15681>

**Fidelity / alignment evaluation (the judge layer)**

- **FormalAlign (ICLR 2025).** Learned alignment evaluator (generation + representational-alignment losses) that detects misaligned autoformalizations. Directly the §20.3 non-LLM second signal. *Supports.* <https://arxiv.org/abs/2410.10135> · <https://github.com/rookie-joe/FormalAlign>
- **Reliable Evaluation and Benchmarks for Statement Autoformalization (Poiroux, Weiss, Kunčak & Bosselut, EMNLP 2025).** Introduces robust benchmarks and metrics for statement autoformalization (BEq+, ProofNetVerif, ProofNet#, RLM25) and shows that reliably judging whether a formal statement preserves source semantics is hard — even human-written formal statements contain semantic errors. The empirical motivation for audit-first (§1). *Supports strongly.* <https://aclanthology.org/2025.emnlp-main.907/>
- **Symbolic equivalence + semantic consistency (2024).** Selects autoformalizations via ATP-checked symbolic equivalence and informalize-then-embed semantic consistency — a non-LLM corroboration recipe for §20.3. *Supports.* <https://arxiv.org/abs/2410.20936>
- **Epistemic Ensemble of LLM Judges for Formal Mathematical Reasoning (2025).** Argues single LLM judges are unreliable and proposes principled ensembles. Directly supports §20.8 and the "judge ≠ certificate" stance. *Supports.* <https://arxiv.org/abs/2506.10903>
- **Do LLMs Game Formalization? (2026).** Documents faithfulness failures (vacuity, premise manipulation, predicate substitution). Grounds the §1 risk list and §20.4–20.5. *Supports.* <https://arxiv.org/abs/2604.19459>

**Judge-reliability methodology**

- **C²-Faith (2026) — chain-of-thought faithfulness, NOT autoformalization.** Benchmarks LLM judges with controlled single-step perturbations (causal / coverage). Methodologically analogous to our mutation-by-perturbation calibration, but for CoT reasoning; cite only as a methodological analogue, clearly labelled. <https://arxiv.org/abs/2603.05167>
- **Mutation testing (general method).** Inject small faults to measure a test suite's discriminating power; the classic *equivalent-mutant problem* corresponds to our "consistency false alarm." We apply it to a *judge* rather than a test suite. Established software-engineering technique (DeMillo, Lipton & Sayward, 1978; Jia & Harman survey, *IEEE TSE*, 2011).

**Formal anchor**

- **Lean FRO Comparator.** Builds Challenge/Solution in a `landrun` sandbox, exports via `lean4export`, checks that the statement's used declarations match and that the proof kernel-accepts under permitted axioms. The formal anchor of §13, and a differentiator from eval work that relies only on type-check / BLEU / embeddings. *Supports.* <https://github.com/leanprover/comparator>
- **lean-eval.** Comparator-based Lean evaluation harness (`Solution.lean` as a fixed bridge). A relevant pattern for multi-target evaluation. <https://github.com/leanprover/lean-eval>
- **lean4checker.** Independent re-checking of the Lean environment; basis for the v0.2 kernel/axiom audit (§14). <https://github.com/leanprover/lean4checker>

---

## 24. Summary

The architecture has not diverged from the original vision; the current repository is a **v0.1 subset** of it (see §0.1).

The current repository implements the audit and measurement spine:

```text
source → card → mapping → review → mutants → judge → score → Lean → Comparator → report
```

The next step is to add the decision loop:

```text
judge/report → revise/block/promote
```

**Today (v0.1), this is an audit and measurement harness, not an agentic system.** Only once the v0.3 closed loop exists should it be described as an agentic anti-drift formalisation system. Until then it audits, reports, and gates; judge output does not yet drive construction.
