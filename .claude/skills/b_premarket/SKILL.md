---
name: b_premarket
description: System B Stage 2 — Pre-market Reviewer. Loads last night's tomorrow_watchlist.json, applies mechanical filters (gap, volume, earnings), then dispatches one mini-agent per surviving candidate plus a synthesizer to produce today_watchlist.json. Fires ~5:30am Pacific before US market open.
disable-model-invocation: true
allowed-tools: Bash(*) Read Write Agent
---

# /b_premarket — System B Stage 2 Pre-market Reviewer

You are the conductor for System B's Stage 2. Sequence: one Python step → N parallel mini-agent dispatches → one synthesizer dispatch → one commit. Do not improvise.

## Step 1 — Run the mechanical pre-filter and build per-ticker facts

```bash
RUN_ID=$(date +%Y%m%d_%H%M%S)
echo "Stage 2 run_id: $RUN_ID"

.venv/bin/python -m ai_hedge.runner.b_stage2 --run-id "$RUN_ID"
PREMKT_EXIT=$?
```

- `PREMKT_EXIT == 0` and at least 1 survivor → continue to Step 2.
- `PREMKT_EXIT == 2` → 0 survivors today (everything dropped or watchlist stale). Skip Steps 2–3, jump to Step 4 (commit a no-trade-today note).
- `PREMKT_EXIT == 1` → hard failure (couldn't read source watchlist). STOP, print error, do not commit.

Read the survivor list:
```bash
SURVIVORS=$(python -c "import json; d=json.load(open('runs/$RUN_ID/premarket_filtered.json')); print(' '.join(d.get('survivors', [])))")
echo "Survivors: $SURVIVORS"
```

If `$SURVIVORS` is empty, skip to Step 4.

## Step 2 — Dispatch per-ticker mini-agents (one per survivor, IN PARALLEL)

For each ticker in `$SURVIVORS`, send ONE Agent tool call. **Send all of them in a single message** so they run in parallel.

For each ticker `{TICKER}`, use this exact prompt:

```
IMPORTANT: Do NOT invoke any skills. Do NOT use memory tools. Just read files and write one JSON file.

You are a System B Stage 2 Pre-market Reviewer mini-agent. You analyze ONE ticker per dispatch. You have fresh context — you know nothing about other candidates.

1. Read your system prompt from: ai_hedge/personas/prompts/b_premarket.md
2. Read your facts bundle from: runs/{RUN_ID}/facts/b_premarket__{TICKER}.json
   (this already has wiki_context with setup_history TL;DR, recent.md TL;DR, regime TL;DR injected)

Produce a strict JSON object answering the questions in your system prompt:
{
  "ticker": "{TICKER}",
  "setup_valid": "yes" | "no" | "partial",
  "setup_type": "breakout" | "pullback" | "gap" | "mean_reversion" | "range_break" | "catalyst" | null,
  "watch_level": float | null,
  "invalidation_level": float | null,
  "catalyst_note": "...",
  "conviction": int (1-10),
  "notes": "..."
}

Failure modes (per the prompt):
- If facts show data_unavailable, output setup_valid="no" and explain in notes.
- If wiki_context is empty (new ticker, no setup_history), rely solely on the technical state and say so in notes.

Write the result to: runs/{RUN_ID}/agent_outputs/b_premarket__{TICKER}.json
```

Wait for ALL parallel dispatches to complete before Step 3.

## Step 3 — Dispatch the synthesizer (one call, ranks survivors)

Dispatch **one** Agent tool call:

```
IMPORTANT: Do NOT invoke any skills. Do NOT use memory tools. Just read files and write one JSON file.

You are the System B Stage 2 Synthesizer. You receive an array of mini-agent decisions and produce the day's final watchlist.

1. Read your system prompt from: ai_hedge/personas/prompts/b_premarket_synthesizer.md
2. Read every mini-agent output from: runs/{RUN_ID}/agent_outputs/b_premarket__*.json
3. Read empirical patterns from: wiki/meta/setup_patterns.md (use this to break ties — prefer setup types that have worked for us historically)

Apply the ranking rules in your system prompt:
- Drop any with setup_valid == "no"
- Sort by conviction desc, then by setup_type win-rate desc
- Cap at top 10

Output the strict JSON object specified in the prompt with keys:
- today_watchlist: array of {ticker, setup_type, watch_level, invalidation_level, catalyst_note, conviction, source_reasons}
- meta: {total_evaluated, total_kept, dropped_count, ranking_rationale}

Write the resulting JSON to: runs/{RUN_ID}/today_watchlist.json
```

Wait for completion.

## Step 4 — Commit and push

If the watchlist is empty (no survivors or 0 kept by synthesizer), still commit so tomorrow knows we had a no-trade day:

```bash
[ -f runs/$RUN_ID/today_watchlist.json ] || python -c "import json,pathlib; pathlib.Path(f'runs/$RUN_ID').mkdir(parents=True, exist_ok=True); pathlib.Path(f'runs/$RUN_ID/today_watchlist.json').write_text(json.dumps({'today_watchlist': [], 'meta': {'total_evaluated':0,'total_kept':0,'dropped_count':0,'ranking_rationale':'no survivors from premarket filter'}}, indent=2))"
```

Build a small summary:

```bash
python - <<'PY' "$RUN_ID"
import json, sys, pathlib
run_id = sys.argv[1]
filt = json.loads(pathlib.Path(f"runs/{run_id}/premarket_filtered.json").read_text())
wl   = json.loads(pathlib.Path(f"runs/{run_id}/today_watchlist.json").read_text())
lines = [
    f"# b_premarket summary {run_id}",
    "",
    f"- candidates in: {filt.get('candidates_in', '?')}",
    f"- mechanical survivors: {len(filt.get('survivors', []))}",
    f"- final today_watchlist: {len(wl.get('today_watchlist', []))}",
    "",
    "## Today's setups",
    ""
]
for c in wl.get("today_watchlist", []):
    lines.append(f"- {c['ticker']} ({c.get('setup_type','?')}, conv={c.get('conviction','?')}, watch={c.get('watch_level','?')}, invalidate={c.get('invalidation_level','?')})")
pathlib.Path(f"runs/{run_id}/summary.md").write_text("\n".join(lines) + "\n")
PY
```

Commit + push:

```bash
BRANCH=$(git branch --show-current)
git add -f runs/$RUN_ID/
git commit -m "$(printf "b_premarket run %s\n\n%s" "$RUN_ID" "$(head -10 runs/$RUN_ID/summary.md)")"
git pull --rebase origin "$BRANCH" || { git rebase --abort; echo "Rebase conflict — manual resolution needed"; exit 1; }
git push origin "$BRANCH"
echo "https://github.com/NamanVinayak/claude-code-swing-scanner/commits/$BRANCH"
```

## End-of-stage rules

- If no candidates survived, the next stage (`/b_decide`) will see an empty `today_watchlist.json` and skip itself. That's correct.
- Mini-agent prompts MUST be dispatched in parallel (single message with N Agent calls), NOT sequentially. The whole point of fresh per-ticker context is the parallelism.
- Never modify Stage 1's output (`tomorrow_watchlist.json`) — read-only.
- Never push to System A's repo.
