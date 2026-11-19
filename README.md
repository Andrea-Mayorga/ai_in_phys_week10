# AI in Physics, Week 10: Debugging Agentic Workflows

Pair-debugging activity from Week 10, Meeting 1 (*Structured Debugging and Observability for Agentic Pipelines*).

## The activity

The starting point was `agentic_bug_hunt.py`, a short, deliberately broken script that imitates an agentic research loop: at each iteration an "agent" picks a search strategy (`broaden`, `narrow` or `rephrase`), searches for papers and sends the accumulated context to a language model. The search tool and the model are **stubs** (`tool_search_papers` and `fake_llm`): no API is called, so the script runs offline and its failures can be triggered on purpose.

The script had three planted failures:

1. A tool call that silently returns an empty list instead of raising an error when there are no results.
2. A prompt that accumulates context across iterations until it exceeds the token limit.
3. A missing random seed, so results change from run to run.

The goal was to find all three using only the script and its output, document them in a bug report (line number, failure-mode category and fix), and make the script's logs detailed enough to **reproduce any failure from the logs alone** (Learning Objective 2).

The debugging followed the **OODA loop** (Observe, Orient, Decide, Act), plus a verification step after each fix.

## Files

| File | Contents |
|---|---|
| [`agentic_bug_hunt.py`](agentic_bug_hunt.py) | The corrected script (comments mark each bug and its fix) |
| [`bug_report.md`](bug_report.md) | Bug report: location, category, symptom, how each bug was confirmed, fix and verification |

## How to run

Requires only Python 3 (standard library). Tested with Python 3.14.

```bash
python3 agentic_bug_hunt.py
```

Expected output (identical on every run with the default seed):

```
INFO seed=42
INFO iter=0 prompt_len=142 blocks_kept=1
INFO iter=0 answer='summary:ITER 0] rephrase: paper-0, paper-1, paper-2'
INFO iter=1 prompt_len=186 blocks_kept=2
INFO iter=1 answer='summary:[ITER 1] broaden: paper-0, paper-1, paper-2'
ERROR iter=2 TOOL_ERROR search returned 0 results for query = 'rare-event quantum oscillation constraints | strategy=broaden'
INFO iter=3 prompt_len=268 blocks_kept=4
...
```

## Summary of fixes

| Bug | Fix |
|---|---|
| Silent tool failure | The tool raises a dedicated `ToolError`; the pipeline catches it, logs it at `ERROR` level with the failing query, and records the failure in the agent's context |
| Context overflow | Context stored as a list of blocks, compressed (question stated once; each block keeps only the strategy and paper IDs) and trimmed to a character budget by dropping the oldest blocks |
| Non-reproducibility | `random.seed(seed)` with a seed parameter (default 42) that is written to the log |

All `print` calls were replaced with Python's `logging` module, so normal events (`INFO`) and tool failures (`ERROR`) are distinguishable in the trace.

## Lessons learned

- **Fix the crash first.** The overflow crashed the script at iteration 0, before the other two bugs could show up.
- **A traceback is not a log.** It said *where* the script failed, but not *at which iteration* or *by how much*. Logging the iteration and the prompt length made the failure reproducible.
- **Don't mask symptoms.** Raising the token limit or stopping the loop early made the error disappear without fixing the unbounded context.
- **Make failures explicit.** An empty list is ambiguous; a named exception plus an `ERROR` log line is not.
- **Log the seed**, not just set it: a seed that isn't in the log can't be used to replay a run.
- **Calibration note:** with the original 280-character limit, the overflow happens at iteration 0 instead of iteration 4 as the handout intends; a limit of about 900 reproduces the intended behaviour (details in the bug report).
