from __future__ import annotations

import csv
import json
import math
import statistics
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple

import httpx

try:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
except Exception:  # pragma: no cover
    plt = None

try:
    import numpy as np
except Exception:  # pragma: no cover
    np = None

try:
    from scipy import stats
except Exception:  # pragma: no cover
    stats = None

from .utils import normalize_answer, token_f1



def _mean(values: List[float]) -> float:
    return float(sum(values) / len(values)) if values else 0.0



def _std(values: List[float]) -> float:
    if len(values) <= 1:
        return 0.0
    return float(statistics.stdev(values))



def confidence_interval(values: List[float], confidence: float = 0.95) -> Tuple[float, float]:
    if not values:
        return 0.0, 0.0
    if len(values) == 1:
        return values[0], values[0]

    mean = _mean(values)
    std_err = statistics.stdev(values) / math.sqrt(len(values))

    if stats is not None:
        z = stats.t.ppf((1 + confidence) / 2.0, len(values) - 1)
    else:
        z = 1.96
    margin = z * std_err
    return mean - margin, mean + margin



def paired_significance(base: List[float], other: List[float]) -> Dict[str, Any]:
    if len(base) != len(other) or not base:
        return {
            "paired_t_p": None,
            "paired_t_stat": None,
            "wilcoxon_p": None,
            "wilcoxon_stat": None,
            "mean_delta": None,
        }

    mean_delta = _mean([o - b for b, o in zip(base, other)])
    out: Dict[str, Any] = {
        "paired_t_p": None,
        "paired_t_stat": None,
        "wilcoxon_p": None,
        "wilcoxon_stat": None,
        "mean_delta": mean_delta,
    }
    if stats is None:
        return out

    try:
        t_stat, t_p = stats.ttest_rel(other, base)
        out["paired_t_p"] = float(t_p)
        out["paired_t_stat"] = float(t_stat)
    except Exception:
        pass

    try:
        w_stat, w_p = stats.wilcoxon(other, base, zero_method="pratt")
        out["wilcoxon_p"] = float(w_p)
        out["wilcoxon_stat"] = float(w_stat)
    except Exception:
        pass

    return out



def _write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    headers = sorted({k for row in rows for k in row.keys()})
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)



def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")



def _plot_metrics(summary_rows: List[Dict[str, Any]], output_path: Path, title: str) -> None:
    if plt is None or not summary_rows:
        return

    strategies = [row["strategy"] for row in summary_rows]
    accuracy = [row["accuracy"] for row in summary_rows]
    f1 = [row["f1"] for row in summary_rows]
    latency = [row["latency_mean_ms"] for row in summary_rows]

    fig, axes = plt.subplots(1, 3, figsize=(14, 4))
    axes[0].bar(strategies, accuracy)
    axes[0].set_title("Accuracy")
    axes[0].set_ylim(0, 1)

    axes[1].bar(strategies, f1)
    axes[1].set_title("F1")
    axes[1].set_ylim(0, 1)

    axes[2].bar(strategies, latency)
    axes[2].set_title("Latency Mean (ms)")

    fig.suptitle(title)
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=180)
    plt.close(fig)



def _latex_summary_table(summary_rows: List[Dict[str, Any]], caption: str, label: str) -> str:
    header = (
        "\\begin{table}[t]\n"
        "\\centering\n"
        "\\small\n"
        "\\begin{tabular}{lcccccc}\n"
        "\\hline\n"
        "Strategy & Accuracy & F1 & Latency(ms) & Latency SD & Agreement & 95\\% CI \\\\\n"
        "\\hline\n"
    )
    body_lines = []
    for row in summary_rows:
        ci_text = f"[{row['accuracy_ci_low']:.3f}, {row['accuracy_ci_high']:.3f}]"
        body_lines.append(
            f"{row['strategy']} & {row['accuracy']:.3f} & {row['f1']:.3f} & "
            f"{row['latency_mean_ms']:.1f} & {row['latency_std_ms']:.1f} & {row['agreement_rate']:.3f} & {ci_text} \\\\"
        )
    footer = (
        "\\hline\n"
        "\\end{tabular}\n"
        f"\\caption{{{caption}}}\n"
        f"\\label{{{label}}}\n"
        "\\end{table}\n"
    )
    return header + "\n".join(body_lines) + "\n" + footer



def _latex_significance_table(significance_rows: List[Dict[str, Any]], caption: str, label: str) -> str:
    header = (
        "\\begin{table}[t]\n"
        "\\centering\n"
        "\\small\n"
        "\\begin{tabular}{lccccc}\n"
        "\\hline\n"
        "Comparison & Mean $\\Delta$ & t-stat & t-p & Wilcoxon & Wilcoxon p \\\\\n"
        "\\hline\n"
    )
    body_lines = []
    for row in significance_rows:
        body_lines.append(
            f"{row['comparison']} & {row['mean_delta'] if row['mean_delta'] is not None else float('nan'):.4f} & "
            f"{row['paired_t_stat'] if row['paired_t_stat'] is not None else float('nan'):.4f} & "
            f"{row['paired_t_p'] if row['paired_t_p'] is not None else float('nan'):.4f} & "
            f"{row['wilcoxon_stat'] if row['wilcoxon_stat'] is not None else float('nan'):.4f} & "
            f"{row['wilcoxon_p'] if row['wilcoxon_p'] is not None else float('nan'):.4f} \\\\"
        )
    footer = (
        "\\hline\n"
        "\\end{tabular}\n"
        f"\\caption{{{caption}}}\n"
        f"\\label{{{label}}}\n"
        "\\end{table}\n"
    )
    return header + "\n".join(body_lines) + "\n" + footer


class BenchmarkEvaluator:
    def __init__(self, orchestrator_url: str, output_root: str, timeout_s: float = 180.0) -> None:
        self.orchestrator_url = orchestrator_url.rstrip("/")
        self.output_root = Path(output_root)
        self.timeout_s = timeout_s

    async def run_benchmark(
        self,
        benchmark_name: str,
        samples: List[Dict[str, Any]],
        strategies: List[str],
        repetitions: int,
        seed: int,
        temperature: float,
        deterministic: bool,
        max_agents: int | None,
        mock_mode: bool,
    ) -> Dict[str, Any]:
        benchmark_dir = self.output_root / benchmark_name
        benchmark_dir.mkdir(parents=True, exist_ok=True)

        records: List[Dict[str, Any]] = []
        correctness_by_strategy: Dict[str, List[float]] = defaultdict(list)
        direct_set = {"majority", "weighted", "isp", "topic"}
        direct_strategies = [strategy for strategy in strategies if strategy in direct_set]
        non_direct_strategies = [strategy for strategy in strategies if strategy not in direct_set]

        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            for rep in range(repetitions):
                for idx, sample in enumerate(samples):
                    sample_seed = int(seed + rep * 100000 + idx)
                    sample_id = sample.get("id", idx)
                    truth = normalize_answer(sample["answer"])
                    sample_max_tokens = int(sample.get("max_tokens", 64))

                    if direct_strategies:
                        shared_payload = {
                            "prompt": sample["prompt"],
                            "strategy": direct_strategies[0],
                            "temperature": temperature,
                            "deterministic": deterministic,
                            "seed": sample_seed,
                            "max_tokens": sample_max_tokens,
                            "max_agents": max_agents,
                            "ground_truth": sample["answer"],
                            "metadata": {
                                "benchmark": benchmark_name,
                                "sample_id": sample_id,
                                "independent_variables": {
                                    "strategy": "direct_shared_batch",
                                    "temperature": temperature,
                                    "deterministic": deterministic,
                                    "seed": sample_seed,
                                },
                            },
                            "mock_mode": mock_mode,
                            "compute_all_direct": True,
                        }

                        started = time.perf_counter()
                        try:
                            response = await client.post(f"{self.orchestrator_url}/query", json=shared_payload)
                            response.raise_for_status()
                            shared_data = response.json()
                        except Exception as exc:
                            shared_data = {
                                "aggregate": {"answer": "", "agreement_rate": 0.0},
                                "aggregates": {},
                                "total_latency_ms": (time.perf_counter() - started) * 1000.0,
                                "resource_usage": {},
                                "error": str(exc),
                            }

                        shared_elapsed_ms = float(
                            shared_data.get("total_latency_ms", (time.perf_counter() - started) * 1000.0)
                        )
                        shared_resource = shared_data.get("resource_usage", {})
                        shared_gpu = shared_resource.get("gpu", []) or []
                        shared_gpu_util = (
                            _mean([float(x.get("utilization_percent", 0.0)) for x in shared_gpu]) if shared_gpu else 0.0
                        )
                        aggregate_map = shared_data.get("aggregates", {})
                        if not isinstance(aggregate_map, dict):
                            aggregate_map = {}

                        for strategy in direct_strategies:
                            aggregate_data = aggregate_map.get(strategy)
                            if aggregate_data is None and strategy == shared_payload["strategy"]:
                                aggregate_data = shared_data.get("aggregate", {})
                            if not isinstance(aggregate_data, dict):
                                aggregate_data = {"answer": "", "agreement_rate": 0.0}

                            pred = normalize_answer(aggregate_data.get("answer", ""))
                            correct = 1.0 if pred == truth and truth else 0.0
                            f1 = token_f1(pred, truth)
                            record = {
                                "benchmark": benchmark_name,
                                "repetition": rep,
                                "strategy": strategy,
                                "sample_id": sample_id,
                                "prompt": sample["prompt"],
                                "truth": sample["answer"],
                                "prediction": pred,
                                "correct": correct,
                                "f1": f1,
                                "latency_ms": shared_elapsed_ms,
                                "agreement_rate": float(aggregate_data.get("agreement_rate", 0.0)),
                                "cpu_percent": shared_resource.get("cpu_percent"),
                                "gpu_util_percent": shared_gpu_util,
                                "error": shared_data.get("error"),
                            }
                            records.append(record)
                            correctness_by_strategy[strategy].append(correct)

                    for strategy in non_direct_strategies:
                        strategy_max_tokens = sample_max_tokens
                        strategy_max_agents = max_agents
                        if strategy == "debate":
                            strategy_max_tokens = min(sample_max_tokens, 16)
                            if strategy_max_agents is None:
                                strategy_max_agents = 2

                        payload = {
                            "prompt": sample["prompt"],
                            "strategy": strategy,
                            "temperature": temperature,
                            "deterministic": deterministic,
                            "seed": sample_seed,
                            "max_tokens": strategy_max_tokens,
                            "max_agents": strategy_max_agents,
                            "ground_truth": sample["answer"],
                            "metadata": {
                                "benchmark": benchmark_name,
                                "sample_id": sample_id,
                                "independent_variables": {
                                    "strategy": strategy,
                                    "temperature": temperature,
                                    "deterministic": deterministic,
                                    "seed": sample_seed,
                                },
                            },
                            "mock_mode": mock_mode,
                        }

                        started = time.perf_counter()
                        try:
                            response = await client.post(f"{self.orchestrator_url}/query", json=payload)
                            response.raise_for_status()
                            data = response.json()
                        except Exception as exc:
                            data = {
                                "aggregate": {"answer": "", "agreement_rate": 0.0},
                                "total_latency_ms": (time.perf_counter() - started) * 1000.0,
                                "resource_usage": {},
                                "error": str(exc),
                            }

                        elapsed_ms = float(data.get("total_latency_ms", (time.perf_counter() - started) * 1000.0))
                        pred = normalize_answer(data.get("aggregate", {}).get("answer", ""))
                        correct = 1.0 if pred == truth and truth else 0.0
                        f1 = token_f1(pred, truth)

                        resource = data.get("resource_usage", {})
                        gpu = resource.get("gpu", []) or []
                        gpu_util = _mean([float(x.get("utilization_percent", 0.0)) for x in gpu]) if gpu else 0.0

                        record = {
                            "benchmark": benchmark_name,
                            "repetition": rep,
                            "strategy": strategy,
                            "sample_id": sample_id,
                            "prompt": sample["prompt"],
                            "truth": sample["answer"],
                            "prediction": pred,
                            "correct": correct,
                            "f1": f1,
                            "latency_ms": elapsed_ms,
                            "agreement_rate": float(data.get("aggregate", {}).get("agreement_rate", 0.0)),
                            "cpu_percent": resource.get("cpu_percent"),
                            "gpu_util_percent": gpu_util,
                            "error": data.get("error"),
                        }
                        records.append(record)
                        correctness_by_strategy[strategy].append(correct)

        summary_rows: List[Dict[str, Any]] = []
        for strategy in strategies:
            subset = [row for row in records if row["strategy"] == strategy]
            acc_values = [row["correct"] for row in subset]
            f1_values = [row["f1"] for row in subset]
            latency_values = [row["latency_ms"] for row in subset]
            agreement_values = [row["agreement_rate"] for row in subset]
            cpu_values = [float(row["cpu_percent"] or 0.0) for row in subset]
            gpu_values = [float(row["gpu_util_percent"] or 0.0) for row in subset]
            ci_low, ci_high = confidence_interval(acc_values)
            summary_rows.append(
                {
                    "benchmark": benchmark_name,
                    "strategy": strategy,
                    "n": len(subset),
                    "accuracy": _mean(acc_values),
                    "f1": _mean(f1_values),
                    "latency_mean_ms": _mean(latency_values),
                    "latency_std_ms": _std(latency_values),
                    "agreement_rate": _mean(agreement_values),
                    "cpu_mean": _mean(cpu_values),
                    "gpu_util_mean": _mean(gpu_values),
                    "accuracy_ci_low": ci_low,
                    "accuracy_ci_high": ci_high,
                }
            )

        baseline = strategies[0] if strategies else None
        significance_rows: List[Dict[str, Any]] = []
        if baseline:
            base_vals = correctness_by_strategy.get(baseline, [])
            for strategy in strategies:
                if strategy == baseline:
                    continue
                test = paired_significance(base_vals, correctness_by_strategy.get(strategy, []))
                significance_rows.append(
                    {
                        "benchmark": benchmark_name,
                        "comparison": f"{strategy} vs {baseline}",
                        **test,
                        "significant_paired_t_0.05": bool(
                            test["paired_t_p"] is not None and test["paired_t_p"] < 0.05
                        ),
                        "significant_wilcoxon_0.05": bool(
                            test["wilcoxon_p"] is not None and test["wilcoxon_p"] < 0.05
                        ),
                    }
                )

        _write_csv(benchmark_dir / "raw_records.csv", records)
        _write_json(benchmark_dir / "raw_records.json", records)
        _write_csv(benchmark_dir / "summary.csv", summary_rows)
        _write_json(benchmark_dir / "summary.json", summary_rows)
        _write_csv(benchmark_dir / "significance.csv", significance_rows)
        _write_json(benchmark_dir / "significance.json", significance_rows)

        _plot_metrics(summary_rows, benchmark_dir / "metrics.png", f"{benchmark_name} benchmark")

        latex_summary = _latex_summary_table(
            summary_rows,
            caption=f"{benchmark_name} results for ensemble strategies",
            label=f"tab:{benchmark_name}_summary",
        )
        latex_significance = _latex_significance_table(
            significance_rows,
            caption=f"{benchmark_name} paired significance tests",
            label=f"tab:{benchmark_name}_significance",
        )
        (benchmark_dir / "summary_table.tex").write_text(latex_summary, encoding="utf-8")
        (benchmark_dir / "significance_table.tex").write_text(latex_significance, encoding="utf-8")

        return {
            "benchmark": benchmark_name,
            "summary": summary_rows,
            "significance": significance_rows,
            "records": len(records),
            "output_dir": str(benchmark_dir),
        }



def save_overall_reports(
    output_root: str,
    all_summary_rows: List[Dict[str, Any]],
    all_significance_rows: List[Dict[str, Any]],
) -> None:
    out = Path(output_root)
    _write_csv(out / "overall_summary.csv", all_summary_rows)
    _write_json(out / "overall_summary.json", all_summary_rows)
    _write_csv(out / "overall_significance.csv", all_significance_rows)
    _write_json(out / "overall_significance.json", all_significance_rows)

    if plt is not None and all_summary_rows:
        by_strategy: Dict[str, List[float]] = defaultdict(list)
        for row in all_summary_rows:
            by_strategy[row["strategy"]].append(row["accuracy"])

        strategies = sorted(by_strategy)
        avg_accuracy = [_mean(by_strategy[s]) for s in strategies]
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.bar(strategies, avg_accuracy)
        ax.set_ylim(0, 1)
        ax.set_title("Average Accuracy Across Benchmarks")
        fig.tight_layout()
        fig.savefig(out / "overall_accuracy.png", dpi=180)
        plt.close(fig)

    latex = _latex_summary_table(
        all_summary_rows,
        caption="All benchmark summary metrics",
        label="tab:overall_summary",
    )
    (out / "overall_summary_table.tex").write_text(latex, encoding="utf-8")
