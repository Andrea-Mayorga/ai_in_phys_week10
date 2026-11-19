# Bug Report: `agentic_bug_hunt.py`

Week 10, Meeting 1: Debugging Agentic Workflows

> **Line numbers:** "Original" refers to the script as distributed; "Fixed" refers to the corrected version.
> **Categories:** replace the text in *[brackets]* with the exact term from the week's failure-mode taxonomy.

## Summary

| # | Bug | Original line(s) | Category | Fixed line(s) |
|---|---|---|---|---|
| 1 | Tool returns `[]` silently on 0 results | 7 | *silent tool failure* | 16–17, 24, 52–57 |
| 2 | Context accumulates without bound | 34, 37 | *context overflow* | 13, 34–37, 59–60, 65–67 |
| 3 | No random seed | 19, 24 | *non-reproducibility* | 39–43 |

**Order of discovery.** Bug 2 was investigated first because it crashes the program: with the original threshold, the very first prompt (≈300 chars) already exceeds the 280-char limit, so the script dies at iteration 0 and never reaches iteration 2, where Bug 1 lives. Fixing it made the other two bugs observable.

---

## Bug 2: Unbounded context accumulation

- **Location:** original lines 34 (`history += ...`) and 37 (prompt built from the whole `history`).
- **Category:** *[context overflow]*
- **Symptom:** `RuntimeError: token limit exceeded` raised from `fake_llm` (line 14).
- **How we confirmed it:** logged `i` and `len(prompt)` before each call to `fake_llm`. The prompt grows by ≈240 chars per iteration, because each block repeats the full query four times (once in the header and once inside each of the three paper strings). Iteration 0 already measures 298–306 chars, depending on the strategy word.
- **Fix:**
  1. `history` (string) → `blocks` (list), one element per iteration.
  2. **Context budget:** after appending a block, drop the oldest blocks until the prompt fits `MAX_PROMPT_CHARS` (`while ... blocks.pop(0)`). The loop never empties the list, so if a single block is too large, `fake_llm` still fails loudly instead of the model silently receiving no context.
  3. **Context compression:** the question is stated once in the prompt header; each block stores only the strategy and the paper IDs (≈45 chars instead of ≈240).
  4. The prompt is built by a single function, `build_prompt`, so the budget check measures exactly the text that is sent.
  5. The limit is a named constant (`MAX_PROMPT_CHARS`) used by both `fake_llm` and the budget.
- **Why not just raise the limit:** it would only delay the crash (more iterations or longer papers would overflow again), and with a real LLM the context window and per-token cost are not ours to choose. Thanks to compression, the fix works with the original limit of 280.
- **Verification:** `prompt_len` stays ≤ 280 and `blocks_kept` stops growing, also with `iterations=50`.

### Note for the instructor: calibration
The handout says the overflow should occur **at iteration 4**, but with a threshold of 280 it occurs **at iteration 0**. This masks Bugs 1 and 3, so the facilitation check ("confirm all three bugs trigger reliably") does not hold. Measured prompt lengths without the fix: iteration 3 ≈ 778–802, iteration 4 ≈ 1018–1050 chars. A threshold of about **900** makes the original script first fail at iteration 4.

---

## Bug 1: Silent tool failure

- **Location:** original line 7, `tool_search_papers` returns `[]` when the query contains `"rare"` (always at iteration 2).
- **Category:** *[silent tool failure]*
- **Symptom:** the loop prints `papers=0 (continuing silently)` and moves on. An empty list is ambiguous: the caller cannot tell "the search failed" from "there are no papers", and the log does not record which query failed or why.
- **How we confirmed it:** once Bug 2 was fixed, the program reached iteration 2 and the failure became visible. An intermediate attempt that returned `['query unsuccessful']` was worse: the error text entered the context as if it were a paper, which in a real pipeline could be "summarized" by the LLM as a scientific result.
- **Fix:**
  1. A dedicated exception, `class ToolError(Exception)`, so only tool failures are caught and unrelated bugs are not hidden.
  2. The tool **raises** `ToolError` with the failing query in the message.
  3. The pipeline catches it (`try` / `except ToolError`), logs it at `ERROR` level, records `FAILED (0 results)` in the agent's context (so the agent "remembers" the failed strategy) and continues. Continuing is now an explicit, logged decision.
- **Verification:** iteration 2 now produces
  ```
  ERROR iter=2 TOOL_ERROR search returned 0 results for query = 'rare-event quantum oscillation constraints | strategy=broaden'
  ```

---

## Bug 3: Missing random seed: non-reproducibility

- **Location:** `random.choice(decisions)` (original line 24) with no seed set anywhere (`run_pipeline`, original line 19).
- **Category:** *[non-determinism / non-reproducibility]*
- **Symptom:** strategies differ between runs, so failures cannot be reproduced.
- **How we confirmed it:** two consecutive runs gave different `prompt_len` values for the same iteration (e.g. 140 vs 141 at iteration 0). The only varying input is the strategy word (`narrow` = 6, `broaden` = 7, `rephrase` = 8 chars), so `random` was choosing differently each run.
- **Fix:** `run_pipeline` takes a `seed` parameter (default 42), calls `random.seed(seed)` before the first random choice and **logs the seed**, so the run can be reproduced from the log alone.
- **Verification:** two consecutive runs produce byte-identical output (`cmp`); changing the seed changes the output.

---

## Logging (towards Learning Objective 2)

All `print` calls were replaced with Python's `logging` module:
- **Levels** distinguish normal events (`INFO`) from tool failures (`ERROR`), which makes a tool failure easy to tell apart from an odd model answer in the trace.
- Each line records the iteration, prompt length, blocks kept and the seed, enough to replay a run.
- `stream=sys.stdout` so the log can be redirected to a file and compared between runs.
- No timestamp in the format, so identical runs produce identical logs. A timestamp can be added for real use.

### Final output (seed = 42, identical across runs)
```
INFO seed=42
INFO iter=0 prompt_len=142 blocks_kept=1
INFO iter=0 answer='summary:ITER 0] rephrase: paper-0, paper-1, paper-2'
INFO iter=1 prompt_len=186 blocks_kept=2
INFO iter=1 answer='summary:[ITER 1] broaden: paper-0, paper-1, paper-2'
ERROR iter=2 TOOL_ERROR search returned 0 results for query = 'rare-event quantum oscillation constraints | strategy=broaden'
INFO iter=3 prompt_len=268 blocks_kept=4
INFO iter=3 answer='summary:ITER 3] rephrase: paper-0, paper-1, paper-2'
INFO iter=4 prompt_len=266 blocks_kept=4
INFO iter=4 answer='summary:\n[ITER 4] narrow: paper-0, paper-1, paper-2'
INFO iter=5 prompt_len=266 blocks_kept=4
INFO iter=5 answer='summary:[ITER 5] broaden: paper-0, paper-1, paper-2'
```

---

## What threw me off

- **The crash hid everything else.** The original traceback said *where* the program failed but not *at which iteration* or *by how much*, so it was not enough to reproduce the failure. Logging `i` and `len(prompt)` was the key step.

- **The context looked useless.** In this toy script nothing reads the history (`fake_llm` returns the last 60 chars and the strategy is random). I still bounded it instead of deleting it, because in a real agent the history carries memory of failed strategies and accumulated evidence. Therefore, I tried implementing a solution that relates more to a real llm handling this situation: context compression and context trimming.
