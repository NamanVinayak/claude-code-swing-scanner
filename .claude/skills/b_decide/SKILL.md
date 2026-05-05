---
name: b_decide
description: System B Stage 3 — Adversarial Decision. Reads today_watchlist.json, builds per-candidate facts, runs 4 perspective agents (2 bull + 2 bear) per ticker in parallel, then a judge per ticker, then aggregates and finalizes decisions.json. Fires twice — once at ~7:00am PT (post-open) and once at ~11:30am PT (power hour). No per-fire count cap — capital rules in writer (max_simultaneous_positions, total_open_risk, deployment_cap, single_position_cap) are the only authoritative limits on how many trades land.
disable-model-invocation: true
allowed-tools: Bash(*) Read Write Agent
---

# /b_decide — System B Stage 3 Adversarial Decision

You are the conductor for System B's heaviest stage. Sequence: Python builds facts → 4 perspectives × N candidates IN PARALLEL → judges per candidate → aggregate → finalize → commit. Do not improvise.

## Step 1 — Build all Stage 3 facts files

```bash
TENTATIVE_RUN_ID=$(date -u +%Y%m%d_%H%M%S)
echo "Tentative run_id: $TENTATIVE_RUN_ID"

.venv/bin/python -m ai_hedge.runner.b_stage3 --run-id "$TENTATIVE_RUN_ID"
B3_EXIT=$?
[ "$B3_EXIT" -eq 0 ] || { echo "Stage 3 init failed"; exit 1; }

RUN_ID=$(cat runs/.last_resolved_run_id)
[ -z "$RUN_ID" ] && { echo "No resolved run_id sentinel found"; exit 1; }
echo "Resolved run_id: $RUN_ID"
```

- Exit 0 → continue.
- Non-zero → STOP. Do not dispatch agents. Do not commit.

Read today's candidates:
```bash
TICKERS=$(python -c "import json; d=json.load(open('runs/$RUN_ID/today_watchlist.json')) if __import__('os').path.exists(f'runs/$RUN_ID/today_watchlist.json') else {'today_watchlist':[]}; print(' '.join([c['ticker'] for c in d.get('today_watchlist', [])]))")
echo "Candidates for adversarial debate: $TICKERS"
```

If `$TICKERS` is empty (no candidates today), skip to Step 5 (commit a no-decisions note).

## Step 1.5 — Dispatch one news researcher per ticker IN PARALLEL

For each ticker in `$TICKERS`, dispatch a single Agent tool call with `subagent_type` `general-purpose`. All N dispatches in ONE message so they run in parallel. Use this prompt template per ticker:

```
IMPORTANT: Do NOT invoke any skills. Do NOT use memory tools. You may use WebSearch, Read, and Write only.

You are a System B News Research Agent for one ticker per dispatch. Your job is to gather last-7-days news context that the Stage 3 perspective agents will rely on.

1. Read your system prompt from: ai_hedge/personas/prompts/b_news_researcher.md
2. Read your facts file from: runs/{RUN_ID}/facts/b_news_researcher__{TICKER}.json
3. Follow the prompt's instructions exactly. Save raw WebSearch results to runs/{RUN_ID}/web_research/raw/{TICKER}_*.json BEFORE summarizing.
4. Write structured output to: runs/{RUN_ID}/news/{TICKER}.json
```

Replace `{RUN_ID}` and `{TICKER}` with the actual values per dispatch.

Wait for ALL news researchers to complete. Then verify each one did its job:

```bash
for T in $TICKERS; do
  [ -f runs/$RUN_ID/news/$T.json ] || { echo "FATAL: news research missing for $T"; exit 1; }
  count=$(ls runs/$RUN_ID/web_research/raw/${T}_*.json 2>/dev/null | wc -l | tr -d ' ')
  [ "$count" -gt 0 ] || { echo "FATAL: news researcher for $T did no WebSearches (no raw files saved)"; exit 1; }
done
echo "News research verified for all $(echo $TICKERS | wc -w | tr -d ' ') tickers"
```

This step is mandatory. If it fails, abort the run. Do not silently fall back to running bull/bear agents without news context — that defeats the entire purpose of having dedicated researchers.

After verification passes, merge each news researcher's output into the per-perspective facts bundles so bulls/bears see the news as `recent_news_7d` (unioned with whatever Finnhub already provided, deduped by URL):

```bash
.venv/bin/python -m ai_hedge.runner.b_stage3 --run-id "$RUN_ID" --merge-news
MERGE_EXIT=$?
[ "$MERGE_EXIT" -eq 0 ] || { echo "FATAL: news merge failed"; exit 1; }
```

## Step 2 — Dispatch 4 perspective agents per ticker (ALL IN PARALLEL)

For each ticker in `$TICKERS`, send 4 Agent tool calls — `b_bull_a`, `b_bull_b`, `b_bear_a`, `b_bear_b`. **Send ALL of them across all tickers in a single message** so they run in parallel. For 5 tickers that's 20 parallel dispatches.

For each (TICKER, AGENT) pair, use this prompt template:

```
IMPORTANT: Do NOT invoke any skills. Do NOT use memory tools. Do NOT invoke WebSearch — news has already been gathered by a dedicated researcher and merged into your facts bundle as `recent_news_7d`. Read files and write one JSON file.

You are a System B Stage 3 perspective agent: {AGENT}. Single ticker per dispatch. Fresh context.

1. Read your system prompt from: ai_hedge/personas/prompts/{AGENT}.md
2. Read your facts bundle from: runs/{RUN_ID}/facts/{AGENT}__{TICKER}.json
   (wiki_context with thesis, catalysts, technicals already injected; `recent_news_7d` populated from Finnhub + web research; `news_source` field tells you provenance)

Treat `recent_news_7d` as the complete and authoritative news window. Do not search independently. If a fact you need is not in the bundle, note it as a research gap in your output.

Output the strict JSON object specified in your system prompt. Schema differs by agent role (bull vs bear), but ALL include: ticker, top_3_arguments, web_sources_last_7d (inherit URLs from the facts bundle's `recent_news_7d`; do not invent).

Write the result to: runs/{RUN_ID}/agent_outputs/{AGENT}__{TICKER}.json
```

Replace `{AGENT}` with one of `b_bull_a` / `b_bull_b` / `b_bear_a` / `b_bear_b`, and `{TICKER}` with the candidate symbol.

Wait for ALL perspective agents to complete before Step 3.

## Step 3 — Dispatch the judge once per ticker (PARALLEL)

For each ticker in `$TICKERS`, dispatch ONE Agent tool call. Send all judge dispatches in a single message (parallel).

```
IMPORTANT: Do NOT invoke any skills. Do NOT use memory tools. Just read files and write one JSON file.

You are the System B Stage 3 Judge. Single ticker per dispatch. Your only output is approve/reject for THIS ticker, with exact entry/stop/target/quantity if approved.

1. Read your system prompt from: ai_hedge/personas/prompts/b_judge.md
2. Read your facts bundle from: runs/{RUN_ID}/facts/b_judge__{TICKER}.json
   (this includes risk_budget snapshot + wiki_context with budget_state, lessons, setup_patterns, open_positions, trades)
3. Read the 4 perspective outputs:
   - runs/{RUN_ID}/agent_outputs/b_bull_a__{TICKER}.json
   - runs/{RUN_ID}/agent_outputs/b_bull_b__{TICKER}.json
   - runs/{RUN_ID}/agent_outputs/b_bear_a__{TICKER}.json
   - runs/{RUN_ID}/agent_outputs/b_bear_b__{TICKER}.json

Apply the decision rules in your system prompt:
1. Compute probability-weighted expected return.
2. REJECT if expected return ≤ 0.
3. REJECT if any budget check fails (positions cap, total open risk cap, deployment cap, single-position cap).
4. If approving, compute exact quantity using position_size_shares math (account × risk% × size_multiplier ÷ |entry − stop|).

Output the strict JSON object specified in your system prompt (`b_judge.md`). The schema is a wrapper: `{"ticker": <str>, "approved": [<trade>...], "rejected": [<reject>...], "summary": <str>}`. Each trade in `approved` includes: direction, entry_price, stop_loss, target_price, target_price_2, quantity, expected_holding_days, setup_type, conviction, rationale, risk_usd, position_size_class. Each entry in `rejected` includes: ticker, reason. For a single-ticker dispatch, exactly one of `approved` or `rejected` will contain one element.

Write to: runs/{RUN_ID}/agent_outputs/b_judge__{TICKER}.json
```

Wait for ALL judges to complete.

## Step 4 — Aggregate judge outputs (capital rules in writer enforce limits, no count cap)

```bash
python - <<'PY' "$RUN_ID"
import json, sys, pathlib
run_id = sys.argv[1]
out_dir = pathlib.Path(f"runs/{run_id}/agent_outputs")
approved, rejected = [], []
# Each judge file is a wrapper: {"ticker": <str>, "approved": [<trade>...], "rejected": [<reject>...], "summary": <str>}
# For a single-ticker dispatch, exactly one of approved/rejected holds one element.
for f in sorted(out_dir.glob("b_judge__*.json")):
    d = json.loads(f.read_text())
    for trade in d.get("approved", []):
        approved.append(trade)
    for r in d.get("rejected", []):
        rejected.append({"ticker": r.get("ticker"), "reason": r.get("reason", "rejected")})

# Sort by conviction (highest first). No per-fire count cap — the writer's
# capital rules (max_simultaneous_positions, total_open_risk, deployment_cap,
# single_position_cap) are the only authoritative limits on how many trades
# actually land. This matches how a real swing trader thinks: take any setup
# that passes risk discipline, regardless of how many setups appear in one fire.
approved.sort(key=lambda x: x.get("conviction", 0), reverse=True)

merged = {"approved": approved, "rejected": rejected, "summary": f"approved={len(approved)}, rejected={len(rejected)}, candidates={len(approved)+len(rejected)}"}
pathlib.Path(f"runs/{run_id}/judge_output.json").write_text(json.dumps(merged, indent=2))
print(json.dumps({"approved": [a['ticker'] for a in approved], "rejected": [r['ticker'] for r in rejected]}, indent=2))
PY
```

If 0 approved, that's fine — Stage 3 sometimes finds no high-conviction trades. Continue to finalize anyway.

## Step 5 — Finalize: convert judge_output.json → decisions.json

```bash
.venv/bin/python -m ai_hedge.runner.b_stage3 --run-id "$RUN_ID" --finalize
FINALIZE_EXIT=$?
[ "$FINALIZE_EXIT" -eq 0 ] || { echo "Finalize failed"; exit 1; }
ls runs/$RUN_ID/decisions.json
```

`decisions.json` is now in System A simulator schema. The 5-min Turso ingester cron will pick it up automatically — no manual ingestion call.

## Step 6 — Commit and push

Build summary:

```bash
python - <<'PY' "$RUN_ID"
import json, sys, pathlib
run_id = sys.argv[1]
jo = json.loads(pathlib.Path(f"runs/{run_id}/judge_output.json").read_text())
dec = json.loads(pathlib.Path(f"runs/{run_id}/decisions.json").read_text()) if pathlib.Path(f"runs/{run_id}/decisions.json").exists() else {"decisions": {}}
lines = [
    f"# b_decide summary {run_id}",
    "",
    f"- approved: {len(jo.get('approved', []))}",
    f"- rejected: {len(jo.get('rejected', []))}",
    "",
    "## Approved trades",
    ""
]
for t, d in dec.get("decisions", {}).items():
    lines.append(f"- {t} {d.get('action','?')} entry={d.get('entry_price','?')} stop={d.get('stop_loss','?')} target={d.get('target_price','?')} qty={d.get('quantity','?')} conv={d.get('confidence','?')}")
lines += ["", "## Rejections (with reasons)", ""]
for r in jo.get("rejected", []):
    lines.append(f"- {r.get('ticker','?')}: {r.get('reason','?')}")
pathlib.Path(f"runs/{run_id}/summary.md").write_text("\n".join(lines) + "\n")
PY
```

```bash
BRANCH=$(git branch --show-current)
git add -f runs/$RUN_ID/
git commit -m "$(printf "b_decide run %s\n\n%s" "$RUN_ID" "$(head -15 runs/$RUN_ID/summary.md)")"
git pull --rebase origin "$BRANCH" || { git rebase --abort; echo "Rebase conflict — manual resolution needed"; exit 1; }
git push origin "$BRANCH"
echo "https://github.com/NamanVinayak/claude-code-swing-scanner/commits/$BRANCH"
```

## End-of-stage rules

- This skill is invoked TWICE per trading day (Desktop Scheduled Task at 7am PT and 11:30am PT). Each fire is independent — different run_id, separate facts, separate judges. The hard cap of 3 trades applies PER FIRE, not per day.
- The 7-day news rule is the most-violated rule by LLMs. The prompt enforces it; the judge double-checks. If you notice perspective outputs citing pre-7-day news, that's a prompt-quality issue, not a conductor issue.
- decisions.json is written in System A simulator schema. It flows into Turso via the 5-min `dashboard.yml` workflow's "Ingest New Decisions" step.
- Never modify other stages' outputs. Read-only on `today_watchlist.json`.
- Never push to System A's repo.
