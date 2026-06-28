#!/usr/bin/env python3
"""Unit tests for the judge-output parser and verdict-recovery path in run_judge.py.

These are pure-function tests: they import the parsing helpers from `run_judge` and feed
them hand-crafted model-output strings. No model/API is called and no files are written.

Run directly (no pytest required):

    python scripts/test_judge_parsing.py

Exit code 0 if every assertion passes, 1 otherwise.

Coverage (mirrors the behaviour exercised by real runs, where some models emit YAML with an
unquoted ': ' inside a free-text field):

  a) valid YAML parses cleanly (judge_output is the mapping, no recovery);
  b) YAML with an unquoted colon in a free-text rationale fails full parsing but a single
     top-level verdict line is recovered;
  c) two conflicting top-level verdict lines are unrecoverable;
  d) no verdict line at all is unrecoverable;
  e) a recovered malformed response has judge_output = None, parse_error retained, and
     recovered_verdict = True (i.e. we never fabricate rubric/rationale from malformed YAML).
"""
from __future__ import annotations

import sys
from pathlib import Path

# Import the helpers from run_judge (this file lives alongside it in scripts/).
sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_judge as rj  # noqa: E402


# --------------------------------------------------------------------------- fixtures
VALID = """\
verdict: PASS
confidence: high
rubric:
  A_assumptions: match
  B_conclusion: identical
detected_issues: []
rationale: The Lean statement matches the source claim.
"""

# Unquoted ': ' inside the rationale value -> PyYAML cannot parse the document, but the
# top-level `verdict:` line is intact and unambiguous.
MALFORMED_RECOVERABLE = """\
verdict: FAIL
confidence: high
detected_issues:
  - axis: B_conclusion
    severity: blocking
    description: the right-hand side sign is flipped
rationale: The Lean statement changes the claim: the forward payoff is negated.
"""

# Malformed (unquoted ': ' in the note) AND two different verdict lines -> ambiguous.
MALFORMED_CONFLICTING = """\
verdict: FAIL
note: the model contradicted itself here: see below
verdict: PASS
"""

# Malformed (unquoted ': ') with no verdict line anywhere.
MALFORMED_NO_VERDICT = """\
confidence: low
rationale: I could not decide because the statement is unusual: no verdict emitted.
"""

# A response fenced in a ```yaml block should still parse cleanly.
VALID_FENCED = """\
```yaml
verdict: WARN
confidence: medium
rationale: An extra non-emptiness hypothesis is carried.
```
"""


# --------------------------------------------------------------------------- harness
_failures: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    status = "ok  " if cond else "FAIL"
    print(f"  [{status}] {name}" + (f" -- {detail}" if (detail and not cond) else ""))
    if not cond:
        _failures.append(name)


# --------------------------------------------------------------------------- tests
def test_valid_parses_cleanly() -> None:
    out, verdict, err, recovered = rj._judge_fields(VALID)
    check("a/valid: parse_error is None", err is None, repr(err))
    check("a/valid: judge_output is a mapping", isinstance(out, dict))
    check("a/valid: verdict == PASS", verdict == "PASS", repr(verdict))
    check("a/valid: recovered_verdict is False", recovered is False)
    # _parse_judge_yaml agrees.
    parsed, perr = rj._parse_judge_yaml(VALID)
    check("a/valid: _parse_judge_yaml returns mapping + no error",
          isinstance(parsed, dict) and perr is None)


def test_valid_fenced_parses_cleanly() -> None:
    out, verdict, err, recovered = rj._judge_fields(VALID_FENCED)
    check("a/fenced: parse_error is None", err is None, repr(err))
    check("a/fenced: verdict == WARN", verdict == "WARN", repr(verdict))
    check("a/fenced: recovered_verdict is False", recovered is False)


def test_malformed_recoverable_single_verdict() -> None:
    # _parse_judge_yaml must fail on the malformed document.
    parsed, perr = rj._parse_judge_yaml(MALFORMED_RECOVERABLE)
    check("b/recoverable: full YAML parse fails", parsed is None and perr is not None,
          f"parsed={parsed!r} perr={perr!r}")
    # _recover_verdict salvages exactly the one verdict present.
    rec = rj._recover_verdict(MALFORMED_RECOVERABLE)
    check("b/recoverable: _recover_verdict == FAIL", rec == "FAIL", repr(rec))


def test_conflicting_verdicts_unrecoverable() -> None:
    rec = rj._recover_verdict(MALFORMED_CONFLICTING)
    check("c/conflicting: _recover_verdict is None", rec is None, repr(rec))
    out, verdict, err, recovered = rj._judge_fields(MALFORMED_CONFLICTING)
    check("c/conflicting: judge_verdict is None", verdict is None, repr(verdict))
    check("c/conflicting: parse_error retained", err is not None)
    check("c/conflicting: recovered_verdict is False", recovered is False)


def test_no_verdict_unrecoverable() -> None:
    rec = rj._recover_verdict(MALFORMED_NO_VERDICT)
    check("d/no-verdict: _recover_verdict is None", rec is None, repr(rec))
    out, verdict, err, recovered = rj._judge_fields(MALFORMED_NO_VERDICT)
    check("d/no-verdict: judge_verdict is None", verdict is None, repr(verdict))
    check("d/no-verdict: recovered_verdict is False", recovered is False)


def test_recovered_record_shape() -> None:
    # The contract the scorer/record-writer relies on for a recovered malformed response.
    out, verdict, err, recovered = rj._judge_fields(MALFORMED_RECOVERABLE)
    check("e/shape: judge_output is None (no fabricated rubric/rationale)", out is None,
          repr(out))
    check("e/shape: judge_verdict recovered as FAIL", verdict == "FAIL", repr(verdict))
    check("e/shape: parse_error retained", err is not None)
    check("e/shape: recovered_verdict is True", recovered is True)


def main() -> int:
    tests = [
        test_valid_parses_cleanly,
        test_valid_fenced_parses_cleanly,
        test_malformed_recoverable_single_verdict,
        test_conflicting_verdicts_unrecoverable,
        test_no_verdict_unrecoverable,
        test_recovered_record_shape,
    ]
    for t in tests:
        print(t.__name__)
        t()
    print()
    if _failures:
        print(f"FAIL: {len(_failures)} assertion(s) failed: {_failures}")
        return 1
    print("PASS: all judge-parsing assertions passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
