# Manual judge requests

This directory holds **exported judge-request files**, one Markdown file per blinded variant,
written by:

```bash
python scripts/run_judge.py --target <Target> --provider <P> --model <M> --export-manual
```

No model or API is called during export. Each `<Target>/<blind_id>.md` file contains:

- a **Provenance** block (reference only — do not paste it to the judge);
- the exact, frozen **system prompt** (between the `BEGIN/END-SYSTEM-PROMPT` markers);
- the exact, hashed **user message** (the blinded comparison package, strict YAML).

## Procedure

1. Open a `<Target>/<blind_id>.md` file.
2. Paste the system-prompt text (between the markers) as the judge's system prompt.
3. Paste the user-message YAML verbatim as the judge's user message.
4. Save the judge's **strict-YAML reply** to
   `docs/judge_responses_manual/<Target>/<blind_id>.yaml`.
5. Once every blind ID for the target has a reply, aggregate them:

   ```bash
   python scripts/import_manual_judge_results.py --target <Target>
   python scripts/score_judge.py --target <Target>
   ```

Exported request files must carry the `MANUAL_EXPORT_NO_MODEL_CALLED` banner and must not leak
any answer-key labels; `scripts/validate_mapping.py` enforces this. This `README.md` is skipped
by that check.
