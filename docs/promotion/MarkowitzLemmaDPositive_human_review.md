# MarkowitzLemmaDPositive — human promotion review

Decision: PROMOTE WITH HUMAN REVIEW

Reviewer: Christopher Darcy
Date: 2026-07-01T23:41:27Z

The automated gate returned HUMAN_REVIEW because the calibrated judge raised false alarms on
meaning-preserving consistency variants. This is a judge-reliability cap, not a formal/source-fidelity
failure. With the human override recorded, the gate's formal core reached PROMOTE
(`judge_metric_cap.capped_from: PROMOTE`); only the conservative structured judge-metric cap held the
reported status at HUMAN_REVIEW. Thresholds were not modified.

Reviewed evidence:
- Real mapping accepted by judge: PASS.
- Discriminative recall: 1.0.
- Consistency false-alarm / false-rejection rate: 0.6, caused by harmless consistency variants.
- Lean build: PASS.
- No-sorry check: PASS.
- Axiom audit: PASS.
- Human source-fidelity review: PASS.
- Comparator: PASSED_REAL_LANDRUN_BEST_EFFORT.
- `B > 0` was accepted as a source-supported proof-body positivity fact; uniqueness/Cramer's-rule remains deferred.

Conclusion:
The HUMAN_REVIEW cap is accepted and resolved by human review. MK-003 is approved for promotion. This
human override does not override any failed formal check; all formal checks already passed. It is a
judgement-layer override only and does not override Lean correctness, source fidelity, the axiom audit,
or the Comparator. The promotion is recorded as `promotion_state: PROMOTED_WITH_HUMAN_REVIEW` in
`docs/formal_mapping.yaml`.
