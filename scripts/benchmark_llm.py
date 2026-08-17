"""Benchmark LLM prompt latency and throughput.

Usage:
    python scripts/benchmark_llm.py
    python scripts/benchmark_llm.py --runtime llama_cpp --prompt "What is RAG?"
    python scripts/benchmark_llm.py --max-new-tokens 256 --runs 3

This script does not download model weights. Configure a model via `.env`
before running, or it will exercise the fake fallback and report 0 tokens/sec.
"""
import argparse
import asyncio
import logging
import sys
import time
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from app.config import settings
from app.services.llm import complete, device_info

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_PROMPT = (
    "Summarize the following text in one sentence:\n\n"
    "Retrieval-Augmented Generation (RAG) combines a retriever with a generator "
    "to produce answers grounded in a knowledge base."
)


def _count_tokens(text: str) -> int:
    """Very rough token count for throughput reporting."""
    return max(1, len(text.split()))


async def _run_once(prompt: str, max_new_tokens: int) -> tuple[str, float]:
    start = time.perf_counter()
    response = await complete(
        prompt,
        system_prompt="You are a helpful assistant.",
        max_new_tokens=max_new_tokens,
    )
    elapsed = time.perf_counter() - start
    return response, elapsed


async def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark PenG LLM completion")
    parser.add_argument(
        "--runtime",
        choices=["transformers", "llama_cpp"],
        default=settings.llm_runtime,
        help="Override LLM runtime",
    )
    parser.add_argument("--prompt", default=DEFAULT_PROMPT, help="Prompt text")
    parser.add_argument(
        "--max-new-tokens", type=int, default=128, help="Max new tokens per run"
    )
    parser.add_argument("--runs", type=int, default=1, help="Number of runs")
    parser.add_argument(
        "--warmup", action="store_true", help="Run one warmup completion before timing"
    )
    args = parser.parse_args()

    settings.llm_runtime = args.runtime
    logger.info("Runtime info: %s", device_info())

    if args.warmup:
        logger.info("Warmup run...")
        await _run_once(args.prompt, args.max_new_tokens)

    latencies: list[float] = []
    tokens_generated: list[int] = []
    responses: list[str] = []

    for i in range(args.runs):
        response, elapsed = await _run_once(args.prompt, args.max_new_tokens)
        latencies.append(elapsed)
        tokens_generated.append(_count_tokens(response))
        responses.append(response)
        logger.info("Run %d: %.3f s, ~%d tokens", i + 1, elapsed, tokens_generated[-1])

    avg_latency = sum(latencies) / len(latencies)
    avg_tokens = sum(tokens_generated) / len(tokens_generated)
    throughput = avg_tokens / avg_latency if avg_latency > 0 else 0.0

    print("\n=== Results ===")
    print(f"Runtime:            {settings.llm_runtime}")
    print(f"Model:              {settings.llm_model}")
    print(f"GGUF path:          {settings.llm_gguf_model_path}")
    print(f"Runs:               {args.runs}")
    print(f"Avg latency:        {avg_latency:.3f} s")
    print(f"Avg output tokens:  {avg_tokens:.1f}")
    print(f"Throughput:         {throughput:.2f} tokens/s")
    print("\nLast response:")
    print(responses[-1][:500])


if __name__ == "__main__":
    asyncio.run(main())
