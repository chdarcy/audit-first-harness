# JUDGE_EVIDENCE_SUMMARY

First real (opt-in) judge calibration run — empirical judge-**reliability** evidence.

| Field | Value |
|---|---|
| Date (UTC) | 2026-06-28 |
| Repo commit at run time | `663fd19` (Add blinding-boundary regression tests) |
| Target | **GoldIrrationalSqrtTwo** (public gold-reference: √2 ∉ ℚ) |
| Provider / model | `openai` / `gpt-4o` |
| Temperature | `0` |
| API calls made | **10** (one per blinded package) |
| Packages judged | **10** |
| Composition | **1 real / 7 discriminative / 2 consistency** |

## Headline metrics

| Metric | Value | Reading |
|---|---|---|
| `discriminative_recall` | **1.0** (7/7) | the judge **rejected every planted defect** |
| `consistency_false_alarm_rate` | **0.0** (0/2) | no false alarms on meaning-preserving variants |
| `real_mapping_agreement` (exact / bucket) | **True / True** | the real mapping was accepted |
| `overall_bucket_accuracy` | **1.0** (10/10) | every variant landed in the expected accept/reject bucket |
| Parse quality | **10 clean / 0 recovered / 0 unrecoverable**; `malformed_yaml_rate` 0.0 | every reply was strict, parseable YAML |
| Structured schema | **VALID 10 / PARTIAL 0 / INVALID 0**; `unparseable_rate` 0.0 | all records satisfy `schema_version 0.3.0` |
| High/critical concerns | 10 (across the 7 rejected mutants) | the defects were flagged with serious severity, as expected |

## Per-variant result (un-blinded via the local answer key; scoring side only)

| variant_id | class | expected | judge | bucket match |
|---|---|---|---|---|
| `gold_irrational_sqrt_two` | real | PASS | PASS | ✅ |
| `GIST-C1` | consistency | PASS | PASS | ✅ |
| `GIST-C2` | consistency | PASS_EQUIV | PASS | ✅ |
| `GIST-D1` | discriminative | FAIL | FAIL | ✅ |
| `GIST-D2` | discriminative | FAIL | FAIL | ✅ |
| `GIST-D3` | discriminative | FAIL | FAIL | ✅ |
| `GIST-D4` | discriminative | FAIL | FAIL | ✅ |
| `GIST-D5` | discriminative | WARN | WARN | ✅ |
| `GIST-D6` | discriminative | FAIL | FAIL | ✅ |
| `GIST-D7` | discriminative | FAIL | FAIL | ✅ |

Verdict spread: **3 accept** (real + 2 consistency, all `PASS`), **7 reject** (6 `FAIL` + 1 `WARN` on `GIST-D5`, the unnecessary-extra-assumption mutant). **0 `UNPARSEABLE`**, **0 `OUT_OF_SCOPE`**. No malformed replies, no recovered verdicts, no schema-invalid records.

## Interpretation and caveats

- This is **judge-reliability evidence, not theorem truth.** Mutation recall and the consistency
  false-alarm rate measure how well the *judge* detects planted source-fidelity defects on this
  target; they say nothing about whether any theorem is "true." A perfect score here means the
  judge discriminated faithful from defective mappings on `GoldIrrationalSqrtTwo` — it is **not** a
  proof about √2 or a certificate of any mapping.
- The judge is a **calibrated source-fidelity reviewer, not a theorem oracle.** Its verdicts never
  override the formal layers (Lean build, no-sorry, axiom audit, Comparator, guarded equivalence);
  in the gate they can only cap an otherwise-promotable target to `HUMAN_REVIEW`.
- **Comparator remains Challenge/Solution formal equality only**, not source-`.tex` fidelity. This
  run concerns source-to-Lean *fidelity* (the judge), a separate axis from formal correctness.
- **Scope:** one target, one model, one temperature, a single 10-package round (small sample). It is
  a clean first calibration point, not a benchmark; broaden across targets/models/seeds before
  drawing general conclusions.
- **Blinding preserved:** the judge runner read only the membership sidecar `_targets.yaml`;
  un-blinding (`blind_id → variant_id/class/expected`) happened only on the scoring/export side via
  `_manifest.yaml`.

## Artifact policy

Raw judge artifacts are **generated and gitignored — not committed**: the per-package replies and
provenance (`docs/judge_results/GoldIrrationalSqrtTwo.yaml`), the scored metrics
(`…_scored.yaml`), and the structured export / score summary
(`…_structured.json`, `…_structured_score.json`) all stay local under `.gitignore`
(`docs/judge_results/*.yaml`, etc.). Only this human-readable summary is committed. The run is
reproducible: reassemble packages with `python scripts/run_mutants.py --dry-run`, then
`run_judge.py … --execute-api` (opt-in), `score_judge.py`, and
`run_structured_judge_workflow.py`.
