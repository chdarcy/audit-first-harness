#!/usr/bin/env python3
"""Source-fidelity review decision layer — the *candidate* gate (PROJECT_CONTEXT.md).

This is the **pre-proof** gate: given the structured judge evidence for a target (the real
candidate's verdict + concerns, plus the judge's calibration over that target's mutants), it decides
whether a proposed source-to-Lean mapping is faithful enough to be **worth proving** — *before* any
hard Lean proof work. It is distinct from the **promotion** gate (`gate_decision.py`, §11.3, post-
Comparator), which consumes formal build/axiom/Comparator status.

Hard boundaries (PROJECT_CONTEXT.md):
  - This is **source-fidelity review evidence, not theorem truth** and not a formal-correctness
    result. It answers "does the Lean statement match the source claim, and how much do we trust the
    judge here?" — never "is the theorem true?".
  - The judge is a **calibrated source-fidelity reviewer, not a theorem oracle.** A mutant *miss*
    (low recall / a false acceptance) is evidence about the **judge**, not evidence that the real
    mapping is wrong; it **caps automation confidence** and forces human review.
  - This layer **never edits Lean, mappings, or any file under version control**, **never calls a
    model/API**, and **never overrides a formal failure** — a `SOURCE_REVIEW_PASS` only means
    "fidelity is good enough to attempt the proof," after which the formal layers (build, no-sorry,
    axiom audit, Comparator, guarded equivalence) and the promotion gate still apply.

For future targets (e.g. the Markowitz suite), the workflow is: propose the public theorem module
`AuditHarness/<Target>.lean` (readable statement, minimal proof wrapper, stable name) + a separate
proof-engineering helper module (`AuditHarness/<Target>/Helpers.lean` or `<Target>Helpers.lean`,
per CLAUDE.md / ARCHITECTURE §5.1) → run this gate → only on `SOURCE_REVIEW_PASS` start the proof.
The theorem statement is never weakened to make a proof easier; this gate decides whether to begin.

Input: a structured-scoring summary (JSON) from `score_judge.py --structured` /
`run_structured_judge_workflow.py` (it carries `per_record`, `reliability`, `totals`, `per_target`).
Output: a machine-readable decision JSON with a status and an explicit reasons list. Pure & offline.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PASS = "SOURCE_REVIEW_PASS"
HUMAN_REVIEW = "SOURCE_REVIEW_HUMAN_REVIEW"
REVISE = "SOURCE_REVIEW_REVISE"
BLOCK = "SOURCE_REVIEW_BLOCK"

ACCEPT = {"PASS", "PASS_EQUIV", "PASS_PROVABLE_EQUIV"}

# Conservative defaults: any imperfection in the judge's calibration on this target caps an
# otherwise-passable candidate to HUMAN_REVIEW (lower trust in the judge's accept).
DEFAULT_THRESHOLDS = {
    "min_discriminative_recall": 1.0,
    "max_false_acceptance_rate_discriminative": 0.0,
    "max_false_rejection_rate_consistency": 0.0,
    "max_invalid_rate": 0.0,
    "max_unparseable_rate": 0.0,
}

DISCLAIMER = (
    "This is source-fidelity review evidence (does the Lean statement match the source claim, and "
    "how reliable is the judge here?) — NOT theorem truth and NOT a formal-correctness result. It "
    "gates whether to begin proof work; it never edits Lean and never overrides the formal layers "
    "(build / no-sorry / axiom audit / Comparator / equivalence)."
)


def _target_node(summary: dict, target: str | None) -> dict:
    """Prefer the per-target node for reliability/totals; fall back to the top-level summary."""
    per_target = summary.get("per_target") if isinstance(summary, dict) else None
    if isinstance(per_target, dict) and target in per_target and isinstance(per_target[target], dict):
        return per_target[target]
    return summary if isinstance(summary, dict) else {}


def decide_source_review(summary: dict, target: str, thr: dict | None = None) -> dict:
    """Decide whether a proposed mapping's source fidelity is good enough to proceed to proof.

    Pure: reads only the in-memory structured-scoring summary; writes/calls nothing."""
    thr = thr or DEFAULT_THRESHOLDS
    node = _target_node(summary, target)
    rel = node.get("reliability") or {}
    tot = node.get("totals") or {}
    records = [r for r in (summary.get("per_record") or [])
               if isinstance(r, dict) and r.get("target") == target]
    real = next((r for r in records if r.get("class") == "real"), None)

    block: list[str] = []
    revise: list[str] = []
    review: list[str] = []
    positives: list[str] = []

    # ---- the real candidate's judge verdict ----
    if real is None:
        block.append(f"No real-mapping judge record for {target!r}; source fidelity cannot be "
                     "assessed (run the judge + structured scoring first).")
        real_verdict = None
    else:
        real_verdict = real.get("verdict")
        schema_status = real.get("schema_status")
        high_critical = real.get("high_critical_concerns") or 0
        if schema_status == "INVALID":
            block.append("The real-mapping judge record is schema-INVALID; the structured evidence "
                         "is untrusted — re-judge / human review before proof work.")
        elif real_verdict == "UNPARSEABLE" or real_verdict is None:
            block.append(f"The judge produced no usable verdict on the real mapping "
                         f"(verdict {real_verdict!r}); re-judge or human review before proof work.")
        elif real_verdict == "FAIL":
            revise.append("The judge rejected the real mapping (FAIL); the Lean statement / mapping "
                          "likely needs revision before any proof effort is spent.")
        elif real_verdict == "WARN":
            review.append("The judge flagged the real mapping (WARN); a human must decide whether to "
                          "revise the statement or accept the caveat before proving.")
        elif real_verdict not in ACCEPT:
            review.append(f"The judge did not accept the real mapping (verdict {real_verdict!r}); "
                          "needs human judgement before proof work.")
        else:
            positives.append(f"The judge accepted the real mapping (verdict {real_verdict}).")
            if high_critical > 0:
                review.append(f"The judge raised {high_critical} high/critical concern(s) on the "
                              "real mapping; human review is required despite the accept verdict.")

    # ---- calibration caps (judge reliability over this target's mutants; never theorem truth) ----
    recall = rel.get("discriminative_recall")
    fa = rel.get("false_acceptance_rate_discriminative")
    fr = rel.get("false_rejection_rate_consistency")
    invalid_rate = tot.get("invalid_rate")
    unparseable_rate = tot.get("unparseable_rate")

    if recall is not None and recall < thr["min_discriminative_recall"]:
        review.append(f"Judge discriminative recall {recall} is below {thr['min_discriminative_recall']} "
                      "on this target (it missed planted defect(s)): lower trust in its accept of the "
                      "real mapping — human review, and strengthen calibration (better prompts, more "
                      "mutants, or a second judge).")
    if fa is not None and fa > thr["max_false_acceptance_rate_discriminative"]:
        review.append(f"Judge false-acceptance rate on discriminative mutants {fa} exceeds "
                      f"{thr['max_false_acceptance_rate_discriminative']}: it accepted a defective "
                      "variant — lower trust; human review.")
    if fr is not None and fr > thr["max_false_rejection_rate_consistency"]:
        review.append(f"Judge false-rejection rate on consistency variants {fr} exceeds "
                      f"{thr['max_false_rejection_rate_consistency']}: it over-flags faithful "
                      "variants — human review.")
    if invalid_rate is not None and invalid_rate > thr["max_invalid_rate"]:
        review.append(f"Structured invalid_rate {invalid_rate} exceeds {thr['max_invalid_rate']}: "
                      "some judge records were not well-formed — human review.")
    if unparseable_rate is not None and unparseable_rate > thr["max_unparseable_rate"]:
        review.append(f"Structured unparseable_rate {unparseable_rate} exceeds "
                      f"{thr['max_unparseable_rate']}: some judge replies had no usable verdict — "
                      "human review.")

    # ---- resolve (most conservative wins) ----
    if block:
        status, reasons = BLOCK, block + review
    elif revise:
        status, reasons = REVISE, revise + review
    elif review:
        status, reasons = HUMAN_REVIEW, positives + review
    else:
        status = PASS
        reasons = positives + ["The real mapping was accepted and the judge's calibration on this "
                               "target meets the conservative thresholds; source fidelity is good "
                               "enough to proceed to proof work."]
    reasons.append(DISCLAIMER)

    return {
        "status": status,
        "target": target,
        "reasons": reasons,
        "real_verdict": real_verdict,
        "calibration": {
            "discriminative_recall": recall,
            "false_acceptance_rate_discriminative": fa,
            "false_rejection_rate_consistency": fr,
            "invalid_rate": invalid_rate,
            "unparseable_rate": unparseable_rate,
        },
        "note": "source-fidelity review evidence, not theorem truth",
        "decided_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Source-fidelity review decision (pre-proof candidate "
                                             "gate; pure, offline, calls no model/API).")
    ap.add_argument("--summary", required=True, metavar="PATH",
                    help="structured-scoring summary JSON (score_judge.py --structured / "
                         "run_structured_judge_workflow.py)")
    ap.add_argument("--target", required=True, help="mapping target, e.g. GoldIrrationalSqrtTwo")
    ap.add_argument("--out", metavar="PATH", help="optional path to write the decision JSON")
    args = ap.parse_args()

    p = Path(args.summary)
    if not p.exists():
        sys.stderr.write(f"ERROR: summary not found: {args.summary}\n")
        return 2
    try:
        summary = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        sys.stderr.write(f"ERROR: summary is not valid JSON ({exc})\n")
        return 2

    decision = decide_source_review(summary, args.target)
    text = json.dumps(decision, indent=2, sort_keys=True)
    if args.out:
        outp = Path(args.out)
        outp.parent.mkdir(parents=True, exist_ok=True)
        outp.write_text(text + "\n", encoding="utf-8")
        print(f"SOURCE_REVIEW [{decision['status']}] -> {outp}")
    print(text)
    # Exit 0 only on PASS; non-zero signals "do not auto-proceed" (BLOCK/REVISE/HUMAN_REVIEW).
    return 0 if decision["status"] == PASS else 1


if __name__ == "__main__":
    sys.exit(main())
