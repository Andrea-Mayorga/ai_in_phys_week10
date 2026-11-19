"""Broken ~60-line agentic loop used for debugging exercises."""
import logging
import random
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

MAX_PROMPT_CHARS = 280


class ToolError(Exception):
    pass


def tool_search_papers(query):
    #print(query)
    if "rare" in query:
        #return []  # BUG 1: silent empty result instead of explicit failure
        raise ToolError(f"search returned 0 results for query = {query!r}") #FIX BUG #1
    return [f"paper-{i}:{query}" for i in range(3)]


def fake_llm(prompt):
    if len(prompt) > MAX_PROMPT_CHARS:
        #print(prompt)
        raise RuntimeError("token limit exceeded")
    return "summary:" + prompt[-60:]

def build_prompt(question,blocks):
    context = "".join(blocks)
    return (f"You are a physics assistant. \nQuestion: {question}\n"
            f"Context:\n{context}\nAnswer briefly.")

def run_pipeline(question, iterations=6, seed=42):
    # BUG 3: no random seed, output differs run-to-run
    # FIX BUG 3: fixed, logged seed -> reproducible runs
    random.seed(seed)   
    logger.info(f"seed={seed}")
    blocks = []
    decisions = ["broaden", "narrow", "rephrase"]

    for i in range(iterations):
        step = random.choice(decisions)
        query = f"{question} | strategy={step}"
        if i == 2:
            query = "rare-event " + query
        try:
            papers = tool_search_papers(query)
        except ToolError as e:
            logger.error(f"iter={i} TOOL_ERROR {e}")
            blocks.append(f"[ITER {i}] {step}: FAILED (0 results)\n")
            continue

        ids = [p.split(":", 1) [0] for p in papers]
        blocks.append(f"[ITER {i}] {step}: {', '.join(ids)}\n")


        # BUG 2: unbounded context accumulation overflows at/near iteration 4
        # FIX BUG 2: drop oldest blocks until the prompt fits the budget
        while len(blocks) > 1 and len(build_prompt(question, blocks)) > MAX_PROMPT_CHARS:
            blocks.pop(0)
        prompt = build_prompt(question, blocks)
        logger.info(f"iter={i} prompt_len={len(prompt)} blocks_kept={len(blocks)}")
        answer = fake_llm(prompt)
        logger.info(f"iter={i} answer={answer[:51]!r}")


if __name__ == "__main__":
    run_pipeline("quantum oscillation constraints")
