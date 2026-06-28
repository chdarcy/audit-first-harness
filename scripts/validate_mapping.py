#!/usr/bin/env python3
"""Deterministic validator for the audit-first traceability ledger (MVP).

Checks the consistency of:
  - docs/theorem_index.yaml      (source ledger)
  - docs/formal_mapping.yaml     (source <-> Lean bridge)
  - docs/fidelity_reviews/*.md   (per-target fidelity reviews, YAML frontmatter)

and writes docs/validation_report.md.

This MVP performs *structural* checks only. It deliberately does NOT run Lean, the
Comparator, or any axiom/sorry analysis (that is other stages of the pipeline). It looks up
each mapped Lean declaration name by plain-text search under the library and Audit/ trees.

Exit code 0 if there are no errors, 1 otherwise. Warnings do not fail the run.
"""
from __future__ import annotations

import sys
from pathlib import Path

try:
    import yaml
except ModuleNotFoundError:
    sys.stderr.write(
        "ERROR: PyYAML is required. Install it with: python -m pip install pyyaml\n"
    )
    sys.exit(2)

ROOT = Path(__file__).resolve().parent.parent
THEOREM_INDEX = ROOT / "docs" / "theorem_index.yaml"
FORMAL_MAPPING = ROOT / "docs" / "formal_mapping.yaml"
REVIEWS_DIR = ROOT / "docs" / "fidelity_reviews"
REPORT = ROOT / "docs" / "validation_report.md"
# Lean source trees searched for mapped declaration names. Any top-level *.lean library plus
# the Audit/ tree; this is intentionally broad so renaming the library does not break lookup.
LEAN_SEARCH_DIRS = [ROOT, ROOT / "Audit"]

# Judge / mutation layer (checked only if these exist; absence is not an error).
MUTANTS_DIR = ROOT / "docs" / "mutants"
JUDGE_PROMPTS_DIR = ROOT / "docs" / "judge_prompts"
JUDGE_PROMPT = JUDGE_PROMPTS_DIR / "judge_v1.md"
MUTATION_REPORT = ROOT / "docs" / "mutation_report.md"
DRYRUN_DIR = ROOT / "docs" / "judge_inputs_dryrun"
TARGETS_FILE = DRYRUN_DIR / "_targets.yaml"
MANIFEST_FILE = DRYRUN_DIR / "_manifest.yaml"
JUDGE_RESULTS_DIR = ROOT / "docs" / "judge_results"
JUDGE_REQUESTS_DIR = ROOT / "docs" / "judge_requests"

# Manual judge-request exports must carry this banner and no answer-key labels. We scan for
# distinctive answer-key forms ("class:"/"operator:" as YAML keys; the others are unambiguous)
# so the embedded public system prompt and blinded package do not trigger false positives.
EXPORT_STATUS = "MANUAL_EXPORT_NO_MODEL_CALLED"
REQUEST_FORBIDDEN_TOKENS = ("expected_verdict", "variant_id", "human_approved", "class:", "operator:")

REQUIRED_METRICS = {
    "real_mapping_agreement_exact", "real_mapping_agreement_bucket",
    "discriminative_recall", "consistency_false_alarm_rate", "overall_bucket_accuracy",
}
# Scoring must never write back into the source-of-truth mapping ledger.
SCORING_WRITEBACK_KEYS = {
    "judge_verdict", "judge_output", "metrics", "scored_utc", "per_variant", "judge_bucket",
}

# _targets.yaml is a membership-only sidecar: per-variant entries may carry ONLY these.
MEMBERSHIP_KEYS = {"target", "input_sha256"}
# Answer-key fields that must NEVER appear anywhere in _targets.yaml.
ANSWER_KEY_FIELDS = {
    "expected_verdict", "class", "operator", "variant_id",
    "human_approved", "verdict",
}

NOTE_REQUIRED_VERDICTS = {"PASS_EQUIV", "WARN"}
ALLOWED_VERDICTS = {
    "PASS", "PASS_EQUIV", "PASS_PROVABLE_EQUIV", "WARN", "FAIL", "OUT_OF_SCOPE",
}
ALLOWED_CLASSES = {"discriminative", "consistency"}
REQUIRED_MUTANT_FIELDS = ["id", "class", "operator", "mutated_statement", "expected_verdict"]
REJECT_VERDICTS = {"FAIL", "WARN"}
ACCEPT_VERDICTS = {"PASS", "PASS_EQUIV", "PASS_PROVABLE_EQUIV"}


def equivalence_evidence_error(equivalence) -> str | None:
    """None if `equivalence` is structurally valid PASS_PROVABLE_EQUIV evidence, else an error.

    Required shape (see ARCHITECTURE.md §20.6): {kind: provable_equiv, lemma: <fqn>,
    module: <module>} (notes optional). That the lemma actually *builds* is verified separately
    by scripts/check_equivalence.py; here we only check that the fields are present."""
    if not isinstance(equivalence, dict):
        return "no equivalence object"
    missing = []
    if equivalence.get("kind") != "provable_equiv":
        missing.append("kind: provable_equiv")
    if not equivalence.get("lemma"):
        missing.append("lemma")
    if not equivalence.get("module"):
        missing.append("module")
    return ("missing " + ", ".join(missing)) if missing else None


class Validator:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def err(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)

    # -- loading -----------------------------------------------------------
    def load_yaml(self, path: Path) -> dict:
        if not path.exists():
            self.err(f"missing file: {path.relative_to(ROOT)}")
            return {}
        try:
            return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:  # pragma: no cover - defensive
            self.err(f"YAML parse error in {path.relative_to(ROOT)}: {exc}")
            return {}

    def load_frontmatter(self, path: Path) -> dict:
        """Parse the leading `--- ... ---` YAML frontmatter of a Markdown file."""
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        if not lines or lines[0].strip() != "---":
            self.err(f"{path.relative_to(ROOT)}: no YAML frontmatter (expected leading '---')")
            return {}
        end = None
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                end = i
                break
        if end is None:
            self.err(f"{path.relative_to(ROOT)}: unterminated frontmatter (no closing '---')")
            return {}
        block = "\n".join(lines[1:end])
        try:
            return yaml.safe_load(block) or {}
        except yaml.YAMLError as exc:
            self.err(f"{path.relative_to(ROOT)}: frontmatter parse error: {exc}")
            return {}

    # -- lean lookup -------------------------------------------------------
    def build_lean_corpus(self) -> str:
        chunks: list[str] = []
        seen: set[Path] = set()
        for d in LEAN_SEARCH_DIRS:
            if not d.exists():
                self.warn(f"Lean search dir not found: {d}")
                continue
            for f in d.rglob("*.lean"):
                if f in seen:
                    continue
                seen.add(f)
                try:
                    chunks.append(f.read_text(encoding="utf-8"))
                except OSError as exc:  # pragma: no cover - defensive
                    self.warn(f"could not read {f}: {exc}")
        return "\n".join(chunks)

    # -- main --------------------------------------------------------------
    def run(self) -> int:
        index = self.load_yaml(THEOREM_INDEX)
        mapping = self.load_yaml(FORMAL_MAPPING)

        index_keys = set((index.get("entries") or {}).keys())
        targets = mapping.get("targets") or {}
        if not targets:
            self.err("formal_mapping.yaml has no targets")

        lean_corpus = self.build_lean_corpus()
        rows: list[dict] = []

        for name, t in targets.items():
            row = {
                "target": name,
                "source_refs": ", ".join(t.get("source_refs") or []),
                "lean": (t.get("lean") or {}).get("declaration", "?"),
                "verdict": t.get("verdict", "?"),
                "human_approved": t.get("human_approved"),
                "comparator_status": t.get("comparator_status", "?"),
                "notes": [],
            }

            # 1. every source_ref exists in theorem_index
            for ref in t.get("source_refs") or []:
                if ref not in index_keys:
                    self.err(f"[{name}] source_ref '{ref}' not in theorem_index.yaml")
                    row["notes"].append(f"missing source_ref {ref}")

            # 2. review file exists
            review_rel = t.get("review")
            review_fm: dict = {}
            if not review_rel:
                self.err(f"[{name}] no 'review' path in mapping")
            else:
                review_path = ROOT / review_rel
                if not review_path.exists():
                    self.err(f"[{name}] review file missing: {review_rel}")
                else:
                    review_fm = self.load_frontmatter(review_path)

            # 3. PASS_EQUIV / WARN require a non-empty equivalence note (direction or notes);
            #    PASS_PROVABLE_EQUIV requires built-lemma evidence (checked structurally here and
            #    for real by scripts/check_equivalence.py).
            verdict = t.get("verdict")
            eq = t.get("equivalence") if isinstance(t.get("equivalence"), dict) else {}
            if verdict in NOTE_REQUIRED_VERDICTS:
                note = (eq.get("direction") or eq.get("notes") or "").strip()
                if not note:
                    self.err(
                        f"[{name}] verdict {verdict} requires a non-empty equivalence note "
                        f"(equivalence.direction or equivalence.notes) in formal_mapping.yaml"
                    )
                    row["notes"].append("missing equivalence note")
            if verdict == "PASS_PROVABLE_EQUIV":
                ev_err = equivalence_evidence_error(t.get("equivalence"))
                if ev_err:
                    self.err(
                        f"[{name}] verdict PASS_PROVABLE_EQUIV requires equivalence "
                        f"{{kind: provable_equiv, lemma, module}} ({ev_err}); run "
                        f"scripts/check_equivalence.py to verify the lemma builds"
                    )
                    row["notes"].append("missing provable-equivalence evidence")

            # 4. comparator config path exists
            comp = t.get("comparator") or {}
            cfg = comp.get("config")
            if not cfg:
                self.err(f"[{name}] no comparator.config path")
            elif not (ROOT / cfg).exists():
                self.err(f"[{name}] comparator config not found: {cfg}")
                row["notes"].append("missing comparator config")

            # 5. mapped Lean declaration appears under a library or Audit/ .lean file
            decl = (t.get("lean") or {}).get("declaration")
            if not decl:
                self.err(f"[{name}] no lean.declaration")
            elif decl not in lean_corpus:
                self.err(
                    f"[{name}] lean declaration '{decl}' not found in any .lean "
                    f"under the library or Audit/"
                )
                row["notes"].append("lean decl not found")

            # 6. human_approved consistent (boolean, and matches review frontmatter)
            ha_map = t.get("human_approved")
            if not isinstance(ha_map, bool):
                self.err(f"[{name}] human_approved must be true/false, got {ha_map!r}")
            if review_fm:
                ha_rev = review_fm.get("human_approved")
                if not isinstance(ha_rev, bool):
                    self.err(f"[{name}] review human_approved must be true/false, got {ha_rev!r}")
                elif ha_rev != ha_map:
                    self.err(
                        f"[{name}] human_approved mismatch: mapping={ha_map} "
                        f"review={ha_rev}"
                    )
                # cross-check verdict + declaration agree between mapping and review
                rv = review_fm.get("verdict")
                if rv is not None and rv != verdict:
                    self.err(f"[{name}] verdict mismatch: mapping={verdict} review={rv}")
                rd = review_fm.get("lean_declaration")
                if rd is not None and rd != decl:
                    self.err(f"[{name}] lean_declaration mismatch: mapping={decl} review={rd}")

            rows.append(row)

        self.check_mutation_layer()

        self.write_report(rows)
        return self.summarize()

    # -- judge / mutation layer (only if present) --------------------------
    def check_mutation_layer(self) -> None:
        """Structural checks for the offline judge/mutation scaffold. Runs only if
        docs/mutants/ or docs/judge_prompts/ exists; otherwise a no-op. Does NOT
        require real judge results (those are deferred)."""
        if not MUTANTS_DIR.exists() and not JUDGE_PROMPTS_DIR.exists():
            return

        # judge prompt must exist once the layer is present
        if not JUDGE_PROMPT.exists():
            self.err(f"judge prompt missing: {JUDGE_PROMPT.relative_to(ROOT)}")

        mutant_files = sorted(MUTANTS_DIR.glob("*.yaml")) if MUTANTS_DIR.exists() else []
        if MUTANTS_DIR.exists() and not mutant_files:
            self.warn(f"{MUTANTS_DIR.relative_to(ROOT)} exists but contains no *.yaml")

        for mf in mutant_files:
            rel = mf.relative_to(ROOT)
            try:
                doc = yaml.safe_load(mf.read_text(encoding="utf-8")) or {}
            except yaml.YAMLError as exc:
                self.err(f"{rel}: YAML parse error: {exc}")
                continue
            muts = doc.get("mutants")
            if not isinstance(muts, list) or not muts:
                self.err(f"{rel}: no 'mutants' list")
                continue
            for i, mut in enumerate(muts):
                tag = f"{rel}:mutant#{i}"
                if not isinstance(mut, dict):
                    self.err(f"{tag}: not a mapping")
                    continue
                mid = mut.get("id", f"#{i}")
                for field in REQUIRED_MUTANT_FIELDS:
                    if not mut.get(field):
                        self.err(f"{rel}:{mid}: missing required field '{field}'")
                cls = mut.get("class")
                if cls is not None and cls not in ALLOWED_CLASSES:
                    self.err(f"{rel}:{mid}: class '{cls}' not in {sorted(ALLOWED_CLASSES)}")
                ev = mut.get("expected_verdict")
                if ev is not None and ev not in ALLOWED_VERDICTS:
                    self.err(f"{rel}:{mid}: expected_verdict '{ev}' not in {sorted(ALLOWED_VERDICTS)}")
                # coherence (warning only): discriminative must reject, consistency must accept
                if cls == "discriminative" and ev in ACCEPT_VERDICTS:
                    self.warn(f"{rel}:{mid}: discriminative mutant expects accept verdict '{ev}'")
                if cls == "consistency" and ev in REJECT_VERDICTS:
                    self.warn(f"{rel}:{mid}: consistency mutant expects reject verdict '{ev}'")

        # mutation report appears after a dry-run; absence is a warning, not an error
        if mutant_files and not MUTATION_REPORT.exists():
            self.warn(
                f"{MUTATION_REPORT.relative_to(ROOT)} not found; "
                f"run `python scripts/run_mutants.py --dry-run` to generate it"
            )

        self.check_targets_sidecar()
        self.check_judge_previews()
        self.check_judge_requests()
        self.check_scored_results()

    # -- membership sidecar (_targets.yaml) --------------------------------
    def check_targets_sidecar(self) -> None:
        if not TARGETS_FILE.exists():
            return
        try:
            doc = yaml.safe_load(TARGETS_FILE.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            self.err(f"_targets.yaml: YAML parse error: {exc}")
            return

        rel = TARGETS_FILE.relative_to(ROOT)
        # no answer-key fields anywhere in the file
        blob = TARGETS_FILE.read_text(encoding="utf-8")
        for field in sorted(ANSWER_KEY_FIELDS):
            if field in blob:
                self.err(f"{rel}: answer-key field '{field}' must not appear in membership sidecar")

        variants = doc.get("variants")
        if not isinstance(variants, dict) or not variants:
            self.err(f"{rel}: missing 'variants' mapping")
            return
        for bid, entry in variants.items():
            if not isinstance(entry, dict):
                self.err(f"{rel}:{bid}: entry is not a mapping")
                continue
            extra = set(entry.keys()) - MEMBERSHIP_KEYS
            if extra:
                self.err(f"{rel}:{bid}: non-membership keys {sorted(extra)}")
            if not entry.get("target"):
                self.err(f"{rel}:{bid}: missing 'target'")
            if not entry.get("input_sha256"):
                self.err(f"{rel}:{bid}: missing 'input_sha256'")
            # every membership blind_id must have a corresponding package file
            if not (DRYRUN_DIR / f"{bid}.yaml").exists():
                self.err(f"{rel}:{bid}: no corresponding package {bid}.yaml in {DRYRUN_DIR.name}")

    # -- judge preview files -----------------------------------------------
    def check_judge_previews(self) -> None:
        if not JUDGE_RESULTS_DIR.exists():
            return
        for pv in sorted(JUDGE_RESULTS_DIR.glob("*_preview.yaml")):
            rel = pv.relative_to(ROOT)
            try:
                doc = yaml.safe_load(pv.read_text(encoding="utf-8")) or {}
            except yaml.YAMLError as exc:
                self.err(f"{rel}: YAML parse error: {exc}")
                continue
            if doc.get("status") != "DRY_RUN_ONLY_NO_MODEL_CALLED":
                self.err(
                    f"{rel}: preview must be marked status: DRY_RUN_ONLY_NO_MODEL_CALLED, "
                    f"got {doc.get('status')!r}"
                )
            blob = pv.read_text(encoding="utf-8")
            for field in ("expected_verdict", "operator"):
                if field in blob:
                    self.err(f"{rel}: preview must not contain answer-key field '{field}'")

    # -- manual judge-request exports --------------------------------------
    def check_judge_requests(self) -> None:
        """If manual judge-request exports exist, each request file must be marked
        MANUAL_EXPORT_NO_MODEL_CALLED and must not leak answer-key labels. Absence is
        not an error; the README is not a request file and is skipped."""
        if not JUDGE_REQUESTS_DIR.exists():
            return
        for rf in sorted(JUDGE_REQUESTS_DIR.rglob("*.md")):
            if rf.name == "README.md":
                continue
            rel = rf.relative_to(ROOT)
            blob = rf.read_text(encoding="utf-8")
            if EXPORT_STATUS not in blob:
                self.err(f"{rel}: manual judge request missing status {EXPORT_STATUS}")
            for tok in REQUEST_FORBIDDEN_TOKENS:
                if tok in blob:
                    self.err(f"{rel}: exported request must not contain answer-key label '{tok}'")

    # -- scored judge results ----------------------------------------------
    def check_scored_results(self) -> None:
        """For each *_scored.yaml present, check it parses, carries the required metrics and a
        per_variant row count matching the answer key for that target, and that scoring did not
        write back into formal_mapping.yaml. Scored results are not required to exist."""
        if not JUDGE_RESULTS_DIR.exists():
            return

        manifest_variants = {}
        if MANIFEST_FILE.exists():
            try:
                mdoc = yaml.safe_load(MANIFEST_FILE.read_text(encoding="utf-8")) or {}
                manifest_variants = mdoc.get("variants") or {}
            except yaml.YAMLError as exc:
                self.err(f"_manifest.yaml: YAML parse error: {exc}")

        for sf in sorted(JUDGE_RESULTS_DIR.glob("*_scored.yaml")):
            rel = sf.relative_to(ROOT)
            try:
                doc = yaml.safe_load(sf.read_text(encoding="utf-8")) or {}
            except yaml.YAMLError as exc:
                self.err(f"{rel}: YAML parse error: {exc}")
                continue

            metrics = doc.get("metrics")
            if not isinstance(metrics, dict):
                self.err(f"{rel}: missing 'metrics' mapping")
            else:
                for field in sorted(REQUIRED_METRICS):
                    if field not in metrics:
                        self.err(f"{rel}: metrics missing '{field}'")

            target = doc.get("target")
            expected = sum(1 for v in manifest_variants.values() if v.get("target") == target)
            pv = doc.get("per_variant")
            if not isinstance(pv, list):
                self.err(f"{rel}: per_variant must be a list, got {type(pv).__name__}")
            elif expected and len(pv) != expected:
                self.err(
                    f"{rel}: per_variant has {len(pv)} rows; answer key has {expected} "
                    f"variants for target {target!r}"
                )
            elif not pv:
                self.err(f"{rel}: per_variant is empty")

        # scoring must not have written back into the mapping ledger
        if FORMAL_MAPPING.exists():
            mapping = self.load_yaml(FORMAL_MAPPING)
            for name, t in (mapping.get("targets") or {}).items():
                if not isinstance(t, dict):
                    continue
                leaked = SCORING_WRITEBACK_KEYS & set(t.keys())
                if leaked:
                    self.err(
                        f"formal_mapping.yaml target '{name}' contains scoring field(s) "
                        f"{sorted(leaked)}; scoring must not write back into the mapping"
                    )

    # -- output ------------------------------------------------------------
    def write_report(self, rows: list[dict]) -> None:
        ok = not self.errors
        lines = [
            "# Validation report",
            "",
            "_Generated by `scripts/validate_mapping.py` (MVP, structural checks only)._",
            "",
            f"**Status: {'PASS' if ok else 'FAIL'}** "
            f"({len(self.errors)} error(s), {len(self.warnings)} warning(s))",
            "",
            "| target | source refs | Lean decl | fidelity verdict | human approved | comparator status | notes |",
            "|---|---|---|---|---|---|---|",
        ]
        for r in rows:
            notes = "; ".join(r["notes"]) if r["notes"] else "-"
            lines.append(
                f"| {r['target']} | {r['source_refs']} | `{r['lean']}` | "
                f"{r['verdict']} | {r['human_approved']} | {r['comparator_status']} | {notes} |"
            )
        lines.append("")
        if self.errors:
            lines.append("## Errors")
            lines.extend(f"- {e}" for e in self.errors)
            lines.append("")
        if self.warnings:
            lines.append("## Warnings")
            lines.extend(f"- {w}" for w in self.warnings)
            lines.append("")
        lines.append(
            "> MVP scope: this report checks ledger consistency, not Lean proofs. "
            "`comparator_status` is read from `formal_mapping.yaml`, not re-run here. "
            "Live `lake build`, the no-sorry scan, and the Comparator run are separate "
            "pipeline stages (see `scripts/rebuild_pipeline.py`)."
        )
        lines.append("")
        REPORT.write_text("\n".join(lines), encoding="utf-8")

    def summarize(self) -> int:
        for w in self.warnings:
            print(f"WARN: {w}")
        for e in self.errors:
            print(f"ERROR: {e}")
        if self.errors:
            print(f"\nFAIL: {len(self.errors)} error(s). See {REPORT.relative_to(ROOT)}")
            return 1
        print(f"\nPASS: ledger consistent. Report written to {REPORT.relative_to(ROOT)}")
        return 0


if __name__ == "__main__":
    sys.exit(Validator().run())
