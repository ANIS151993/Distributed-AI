#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from benchmarks.gsm8k_runner import load_gsm8k_samples
from benchmarks.mmlu_runner import load_mmlu_samples
from benchmarks.truthfulqa_runner import load_truthfulqa_samples
from orchestrator.evaluator import BenchmarkEvaluator, save_overall_reports


BENCHMARK_LOADERS = {
    "mmlu": load_mmlu_samples,
    "gsm8k": load_gsm8k_samples,
    "truthfulqa": load_truthfulqa_samples,
}



def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run distributed ensemble benchmark experiments")
    parser.add_argument("--orchestrator-url", default="http://127.0.0.1:8000", help="Orchestrator API base URL")
    parser.add_argument("--benchmarks", default="mmlu,gsm8k,truthfulqa", help="Comma-separated benchmark names")
    parser.add_argument("--strategies", default="majority,weighted,isp,topic,debate", help="Comma-separated strategies")
    parser.add_argument("--repetitions", type=int, default=5, help="Repetitions per benchmark")
    parser.add_argument("--samples-per-benchmark", type=int, default=20, help="Samples per benchmark")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--temperature", type=float, default=0.2)
    parser.add_argument("--deterministic", action="store_true", help="Force deterministic mode")
    parser.add_argument("--max-agents", type=int, default=None)
    parser.add_argument("--mock-mode", action="store_true", help="Use orchestrator mock agents for simulation")
    parser.add_argument("--output-dir", default=None, help="Output directory for results")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()

    selected_benchmarks = [name.strip().lower() for name in args.benchmarks.split(",") if name.strip()]
    strategies = [name.strip().lower() for name in args.strategies.split(",") if name.strip()]

    run_stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(args.output_dir or f"results/run_{run_stamp}")
    output_dir.mkdir(parents=True, exist_ok=True)

    evaluator = BenchmarkEvaluator(
        orchestrator_url=args.orchestrator_url,
        output_root=str(output_dir),
    )

    all_summary: List[Dict[str, Any]] = []
    all_significance: List[Dict[str, Any]] = []

    for bench in selected_benchmarks:
        if bench not in BENCHMARK_LOADERS:
            raise ValueError(f"Unsupported benchmark: {bench}")
        loader = BENCHMARK_LOADERS[bench]
        samples = loader(limit=args.samples_per_benchmark, seed=args.seed)

        result = await evaluator.run_benchmark(
            benchmark_name=bench,
            samples=samples,
            strategies=strategies,
            repetitions=args.repetitions,
            seed=args.seed,
            temperature=args.temperature,
            deterministic=args.deterministic,
            max_agents=args.max_agents,
            mock_mode=args.mock_mode,
        )

        all_summary.extend(result["summary"])
        all_significance.extend(result["significance"])

    save_overall_reports(
        output_root=str(output_dir),
        all_summary_rows=all_summary,
        all_significance_rows=all_significance,
    )

    print(f"Experiment run complete. Outputs saved to: {output_dir}")


if __name__ == "__main__":
    asyncio.run(main())
