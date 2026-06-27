#!/usr/bin/env python3
"""Scan the Lean sources for incomplete proofs (`sorry` / `admit` / `sorryAx`).

Part of the audit-first pipeline's "no-sorry" stage: a faithful Comparator audit is only
meaningful if the library proof it delegates to is actually complete. This is a *textual*
scan (it does not run Lean); for a kernel-level guarantee use `#print axioms <decl>` or the
Comparator stage, which checks the permitted-axiom set.

By design, each Comparator **Challenge** file states its theorem with `:= by sorry` (the
Solution supplies the real proof), so `Audit/*/Challenge.lean` files are excluded by default.
Pass --include-challenge to scan them too. `*.lean.template` skeleton files are never scanned.

Exit code 0 if no offending tokens are found, 1 otherwise.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Search the whole repo for *.lean, minus build output and dependencies.
SEARCH_ROOT = ROOT
EXCLUDED_DIR_PARTS = {".lake", "lake-packages", ".git"}

# Whole-word tokens that indicate an incomplete or cheated proof.
TOKENS = ("sorry", "admit", "sorryAx")
TOKEN_RE = re.compile(r"(?<![A-Za-z0-9_])(" + "|".join(TOKENS) + r")(?![A-Za-z0-9_])")

# A `--` line comment or the body of a `/- ... -/` block: a mention of "sorry" in prose is not
# an incomplete proof. We strip line comments and block comments before scanning.
LINE_COMMENT_RE = re.compile(r"--.*?$", re.MULTILINE)
BLOCK_COMMENT_RE = re.compile(r"/-.*?-/", re.DOTALL)


def is_challenge(path: Path) -> bool:
    return path.parent.parent.name == "Audit" and path.name == "Challenge.lean"


def strip_comments(text: str) -> str:
    text = BLOCK_COMMENT_RE.sub(" ", text)
    text = LINE_COMMENT_RE.sub("", text)
    return text


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--include-challenge", action="store_true",
                    help="also scan Audit/*/Challenge.lean (which intentionally use sorry)")
    args = ap.parse_args()

    offenders: list[tuple[Path, int, str]] = []
    scanned = skipped_challenge = 0

    for f in sorted(SEARCH_ROOT.rglob("*.lean")):
        if any(part in EXCLUDED_DIR_PARTS for part in f.parts):
            continue
        if is_challenge(f) and not args.include_challenge:
            skipped_challenge += 1
            continue
        scanned += 1
        raw = f.read_text(encoding="utf-8")
        code = strip_comments(raw)
        # Report against original line numbers by scanning line-by-line on a comment-stripped copy.
        stripped_lines = strip_comments(raw).splitlines()
        for i, line in enumerate(stripped_lines, start=1):
            m = TOKEN_RE.search(line)
            if m:
                offenders.append((f.relative_to(ROOT), i, m.group(1)))

    if offenders:
        for rel, lineno, tok in offenders:
            print(f"SORRY: {rel}:{lineno}: found '{tok}'")
        print(f"\nFAIL: {len(offenders)} incomplete-proof token(s) in {scanned} scanned file(s).")
        if skipped_challenge:
            print(f"  ({skipped_challenge} Audit Challenge file(s) skipped; "
                  f"pass --include-challenge to scan them.)")
        return 1

    print(f"PASS: no sorry/admit in {scanned} scanned .lean file(s).")
    if skipped_challenge:
        print(f"  ({skipped_challenge} Audit Challenge file(s) skipped by design.)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
