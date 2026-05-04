---
name: b_scan
description: System B Stage 1 — Sunset Scanner. Mechanically scans the universe (~Russell 1000) for setups via TradingView signals + Capitol Trades + Finnhub, then dispatches the scanner synthesizer to write the daily macro state. Produces tomorrow_watchlist.json. Fires ~2pm Pacific each weekday after market close.
disable-model-invocation: true
allowed-tools: Bash(*) Read Write Agent
---

# /b_scan — System B Stage 1 Sunset Scanner

You are the conductor for System B's Stage 1. Your job is to sequence one Python step + one LLM dispatch + one commit. Nothing else. Do not improvise. Do not skip steps. Do not invoke other skills.

## Step 1 — Generate run ID and run the mechanical scan

```bash
RUN_ID=$(date +%Y%m%d_%H%M%S)
echo "Stage 1 run_id: $RUN_ID"

.venv/bin/python -m ai_hedge.runner.b_stage1 --run-id "$RUN_ID" --max-candidates 40
SCAN_EXIT=$?
```

Capture `SCAN_EXIT`.

- If `SCAN_EXIT == 0` → continue.
- If `SCAN_EXIT == 1` → no candidates surfaced (quiet day). Skip Step 2 entirely. Jump to Step 3 (commit) with a note that today is a no-trade scenario.
- If any other exit code → STOP, print the error, do not commit anything, return.

Sanity-confirm the outputs exist:
```bash
ls runs/$RUN_ID/tomorrow_watchlist.json runs/$RUN_ID/scanner_diagnostic.json
```

## Step 2 — Dispatch the scanner synthesizer (skip if no candidates)

If Step 1 returned no candidates (SCAN_EXIT == 1), skip this step entirely.

Otherwise, dispatch **one** Agent tool call:

```
IMPORTANT: Do NOT invoke any skills. Do NOT use memory tools. Just read files and write one file.

You are System B's Stage 1 Scanner Synthesizer.

1. Read your system prompt from: ai_hedge/personas/prompts/b_scanner_synthesizer.md
2. Read the diagnostic from: runs/{RUN_ID}/scanner_diagnostic.json
3. Read the candidates from: runs/{RUN_ID}/tomorrow_watchlist.json
4. Read current macro context from: wiki/macro/regime.md
5. Read empirical setup patterns from: wiki/meta/setup_patterns.md

Produce the COMPLETE updated content of wiki/macro/scanner_state.md, including:
- YAML front-matter with last_updated set to today's date (YYYY-MM-DD) and last_run_id set to {RUN_ID}
- The required body sections from the template: ## TL;DR, ## Sector breadth, ## Signal density, ## Anomalies, ## Last updated

Constraints:
- ≤ 500 words total
- Every factual claim must be derivable from the diagnostic JSON. If you cannot back a claim with data, do not write it.
- If the diagnostic shows partial scanner failures (errors[] non-empty), state that explicitly in the TL;DR.
- Style: senior trader's morning notes. Terse, factual, no speculation.

Write the resulting markdown directly to: wiki/macro/scanner_state.md (overwrite the existing file).
```

Replace `{RUN_ID}` with the actual run_id from Step 1.

Wait for the agent to complete before proceeding.

## Step 3 — Commit and push

Write a tiny summary file so a human (or future agent) can see what happened today without parsing JSON:

```bash
python - <<'PY' "$RUN_ID"
import json, sys, pathlib
run_id = sys.argv[1]
diag = json.loads(pathlib.Path(f"runs/{run_id}/scanner_diagnostic.json").read_text())
wl   = json.loads(pathlib.Path(f"runs/{run_id}/tomorrow_watchlist.json").read_text())
lines = [
    f"# b_scan summary {run_id}",
    "",
    f"- universe size: {diag.get('universe_size', '?')}",
    f"- candidates: {len(wl.get('candidates', []))}",
    f"- elapsed: {diag.get('elapsed_seconds', '?')}s",
    f"- errors: {len(diag.get('errors', []))}",
    "",
    "## Top candidates",
    ""
]
for c in wl.get("candidates", [])[:10]:
    lines.append(f"- {c['ticker']} (score={c.get('score','?')}, reasons={c.get('reasons',[])})")
pathlib.Path(f"runs/{run_id}/summary.md").write_text("\n".join(lines) + "\n")
PY
```

Commit run artifacts + the wiki update on the current branch:

```bash
BRANCH=$(git branch --show-current)

git add -f runs/$RUN_ID/ wiki/macro/scanner_state.md

git commit -m "$(printf "b_scan run %s\n\n%s" "$RUN_ID" "$(head -10 runs/$RUN_ID/summary.md)")"

git pull --rebase origin "$BRANCH" || { git rebase --abort; echo "Rebase conflict — manual resolution needed"; exit 1; }
git push origin "$BRANCH"
```

Print the commit URL:
```bash
echo "https://github.com/NamanVinayak/claude-code-swing-scanner/commits/$BRANCH"
```

## End-of-stage rules

- Stage 2 (the next morning) reads `runs/{LATEST_RUN_ID}/tomorrow_watchlist.json` automatically — you don't pass run_id forward.
- If you skipped Step 2 because no candidates surfaced, Stage 2 will see an empty watchlist tomorrow and skip itself. That's correct behavior.
- Never delete or modify content under `wiki/_archive/` or `tracker/`.
- Never push to System A's repo (`claude-code-hedge-fund`). This skill operates only on `claude-code-swing-scanner`.
