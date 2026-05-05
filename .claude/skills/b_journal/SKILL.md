---
name: b_journal
description: System B Stage 4 — End-of-Day Journal. Reads today's trade outcomes from Turso, mechanically updates lessons / setup_patterns / budget_state / open_positions, bootstraps wiki pages for any new tickers traded, then dispatches the journal agent to write narrative lessons + thesis updates. Fires ~1:30pm Pacific after market close.
disable-model-invocation: true
allowed-tools: Bash(*) Read Write Agent
---

# /b_journal — System B Stage 4 End-of-Day Journal

You are the conductor for System B's learning loop. Sequence: Python does the mechanical wiki updates → ONE journal agent fills in narrative content → commit. Do not improvise.

## Step 1 — Run the mechanical journal updates

```bash
RUN_ID=$(date -u +%Y%m%d_%H%M%S)
echo "Stage 4 run_id: $RUN_ID"

.venv/bin/python -m ai_hedge.runner.b_stage4 --run-id "$RUN_ID"
B4_EXIT=$?
```

- Exit 0 → continue. (Even if there were no trades today, b_stage4.py still refreshes setup_patterns / open_positions / budget_state with the current state. That's correct.)
- Non-zero → STOP. Print error. Do not commit.

Sanity check that the facts file landed:
```bash
ls runs/$RUN_ID/journal_facts.json
ls runs/$RUN_ID/facts/b_journal__GLOBAL.json
```

## Step 2 — Dispatch the journal agent

Dispatch **one** Agent tool call:

```
IMPORTANT: Do NOT invoke any skills. Do NOT use memory tools. Read files and write files.

You are the System B Stage 4 Journal Agent. You run once per day after the mechanical Python journal updates. Your job is the narrative work — turning facts into lessons and updating per-ticker theses where today's outcomes changed something.

1. Read your system prompt from: ai_hedge/personas/prompts/b_journal.md
2. Read the canonical facts bundle from: runs/{RUN_ID}/journal_facts.json
   (closed_trades_today, open_positions, new_tickers_bootstrapped, previous_lessons_count, budget_state_summary)
3. Read the GLOBAL wiki-injected facts from: runs/{RUN_ID}/facts/b_journal__GLOBAL.json
4. Read the current state files you may need to edit:
   - wiki/meta/lessons.md (find <!-- trade_id=N --> markers and replace [journal_agent: pending] with concrete one-sentence reasons)
   - For each ticker in closed_trades_today: wiki/tickers/<TICKER>/thesis.md and wiki/tickers/<TICKER>/setup_history.md

Three jobs (do them in order):

JOB 1 — Fill lesson WHY placeholders.
For each closed trade, find the bullet in lessons.md tagged with its trade_id and replace [journal_agent: pending] with ONE concrete sentence explaining WHY the trade worked or failed. The reason MUST be derivable from the facts data — no speculation. Cite the source where useful (which perspective flagged the risk, what catalyst hit, etc.).

JOB 2 — Update per-ticker thesis pages where today's outcome changed something.
For each ticker in closed_trades_today, read its current wiki/tickers/<TICKER>/thesis.md. If the outcome falsified or strengthened a thesis claim, edit the relevant section and add to the "What falsified the prior thesis" section (System A discipline). Bump last_updated and last_run_id in the front-matter. If the thesis is unaffected (small confirming win), skip.

For tickers in new_tickers_bootstrapped (which Python already created skeleton pages for), populate thesis.md from scratch using the trade rationale + wiki_context. Strict 7-day news rule applies if you use WebSearch.

JOB 3 — Update setup_history per ticker.
For each ticker in closed_trades_today, append one row to wiki/tickers/<TICKER>/setup_history.md table:
| date | setup_type | screener_signals | watch_level | outcome | one-line lesson |

Constraints:
- Do NOT modify the ## Rules (locked) section of wiki/meta/budget_state.md
- Do NOT modify lessons that already have a real WHY (only fill placeholders)
- Do NOT add new lessons not already in the file (Python phase added them; you only fill the WHY)

Output (JSON, written to runs/{RUN_ID}/agent_outputs/b_journal_status.json):
{
  "lessons_filled": int,
  "theses_updated": [tickers],
  "setup_histories_updated": [tickers],
  "notes": "..."
}
```

Wait for completion.

## Step 3 — Commit and push

Build summary:

```bash
python - <<'PY' "$RUN_ID"
import json, sys, pathlib
run_id = sys.argv[1]
jf = json.loads(pathlib.Path(f"runs/{run_id}/journal_facts.json").read_text())
status_path = pathlib.Path(f"runs/{run_id}/agent_outputs/b_journal_status.json")
status = json.loads(status_path.read_text()) if status_path.exists() else {}
lines = [
    f"# b_journal summary {run_id}",
    "",
    f"- closed trades today: {len(jf.get('closed_trades_today', []))}",
    f"- open positions: {len(jf.get('open_positions', []))}",
    f"- new tickers bootstrapped: {jf.get('new_tickers_bootstrapped', [])}",
    f"- lessons filled by agent: {status.get('lessons_filled', 0)}",
    f"- theses updated: {status.get('theses_updated', [])}",
    f"- setup_histories updated: {status.get('setup_histories_updated', [])}",
    "",
]
budget = jf.get("budget_state_summary", {})
lines += [
    "## Budget state after journal",
    f"- cash: ${budget.get('cash_usd', '?')}",
    f"- deployed: ${budget.get('deployed_usd', '?')}",
    f"- open risk: ${budget.get('open_risk_usd', '?')}",
    f"- positions open: {budget.get('positions_open', '?')}",
    f"- phase: {budget.get('current_phase', '?')}",
]
pathlib.Path(f"runs/{run_id}/summary.md").write_text("\n".join(lines) + "\n")
PY
```

```bash
BRANCH=$(git branch --show-current)
git add -f runs/$RUN_ID/ wiki/
git commit -m "$(printf "b_journal run %s\n\n%s" "$RUN_ID" "$(head -15 runs/$RUN_ID/summary.md)")"
git pull --rebase origin "$BRANCH" || { git rebase --abort; echo "Rebase conflict — manual resolution needed"; exit 1; }
git push origin "$BRANCH"
echo "https://github.com/NamanVinayak/claude-code-swing-scanner/commits/$BRANCH"
```

## End-of-stage rules

- Stage 4 is mostly mechanical. The LLM agent only does narrative work (filling WHY placeholders + thesis edits). All counts and tables come from Python.
- If there were no trades today (closed_trades_today empty), the agent has nothing to write WHY for, but Stage 4 still updates open_positions / budget_state / setup_patterns. Always commit, even on quiet days.
- Wiki pages for new tickers are created BEFORE the agent runs — the agent just populates them with content. Never depend on the agent creating files from scratch.
- Never modify the ## Rules (locked) section of budget_state.md. The Python phase preserves it; the agent must too.
- Never push to System A's repo.
