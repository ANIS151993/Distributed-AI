#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import math
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
RUN_ID = "run_20260226_193331"
RUN_DIR = ROOT / "artifacts" / "benchmark_runs" / RUN_ID
OPT_DIR = ROOT / "artifacts" / "optimization_runs"

DOC_FIG_DIR = ROOT / "docs" / "assets" / "figures"
DOC_DATA_DIR = ROOT / "docs" / "assets" / "data"
PAPER_FIG_DIR = ROOT / "paper" / "figures"
PAPER_TABLE_DIR = ROOT / "paper" / "tables"

BENCHMARKS = ["mmlu", "gsm8k", "truthfulqa"]
STRATEGIES = ["majority", "weighted", "isp", "topic", "debate"]


def read_csv(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def prepare_dirs() -> None:
    for path in [DOC_FIG_DIR, DOC_DATA_DIR, PAPER_FIG_DIR, PAPER_TABLE_DIR]:
        path.mkdir(parents=True, exist_ok=True)


def build_matrices(rows: List[Dict[str, str]]) -> Dict[str, Dict[str, Dict[str, float]]]:
    metrics: Dict[str, Dict[str, Dict[str, float]]] = {
        "accuracy": {b: {s: 0.0 for s in STRATEGIES} for b in BENCHMARKS},
        "latency": {b: {s: 0.0 for s in STRATEGIES} for b in BENCHMARKS},
        "f1": {b: {s: 0.0 for s in STRATEGIES} for b in BENCHMARKS},
        "agreement": {b: {s: 0.0 for s in STRATEGIES} for b in BENCHMARKS},
    }
    for row in rows:
        b = row.get("benchmark", "").lower()
        s = row.get("strategy", "").lower()
        if b not in BENCHMARKS or s not in STRATEGIES:
            continue
        metrics["accuracy"][b][s] = as_float(row.get("accuracy"))
        metrics["latency"][b][s] = as_float(row.get("latency_mean_ms"))
        metrics["f1"][b][s] = as_float(row.get("f1"))
        metrics["agreement"][b][s] = as_float(row.get("agreement_rate"))
    return metrics


def write_bar_chart_accuracy(metrics: Dict[str, Dict[str, Dict[str, float]]]) -> Path:
    x = np.arange(len(STRATEGIES))
    width = 0.25
    fig, ax = plt.subplots(figsize=(12, 6))

    for idx, benchmark in enumerate(BENCHMARKS):
        vals = [metrics["accuracy"][benchmark][s] for s in STRATEGIES]
        ax.bar(x + (idx - 1) * width, vals, width, label=benchmark.upper())

    ax.set_xticks(x)
    ax.set_xticklabels([s.title() for s in STRATEGIES])
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Accuracy")
    ax.set_title("Accuracy by Strategy and Benchmark")
    ax.legend()
    ax.grid(axis="y", alpha=0.2)

    out = DOC_FIG_DIR / "accuracy_bar_chart.png"
    fig.tight_layout()
    fig.savefig(out, dpi=180)
    plt.close(fig)
    return out


def write_line_chart_latency(metrics: Dict[str, Dict[str, Dict[str, float]]]) -> Path:
    fig, ax = plt.subplots(figsize=(12, 6))
    x = np.arange(len(STRATEGIES))

    for benchmark in BENCHMARKS:
        vals = [metrics["latency"][benchmark][s] for s in STRATEGIES]
        ax.plot(x, vals, marker="o", linewidth=2, label=benchmark.upper())

    ax.set_xticks(x)
    ax.set_xticklabels([s.title() for s in STRATEGIES])
    ax.set_ylabel("Latency Mean (ms)")
    ax.set_title("Latency Trend by Strategy")
    ax.grid(alpha=0.2)
    ax.legend()

    out = DOC_FIG_DIR / "latency_line_chart.png"
    fig.tight_layout()
    fig.savefig(out, dpi=180)
    plt.close(fig)
    return out


def write_pie_chart_avg_accuracy(metrics: Dict[str, Dict[str, Dict[str, float]]]) -> Path:
    avg = []
    for strategy in STRATEGIES:
        vals = [metrics["accuracy"][b][strategy] for b in BENCHMARKS]
        avg.append(sum(vals) / len(vals))

    total = sum(avg)
    if total <= 0:
        avg = [1.0 for _ in STRATEGIES]

    fig, ax = plt.subplots(figsize=(8, 8))
    ax.pie(avg, labels=[s.title() for s in STRATEGIES], autopct="%1.1f%%", startangle=90)
    ax.set_title("Average Accuracy Share by Strategy")

    out = DOC_FIG_DIR / "accuracy_share_pie_chart.png"
    fig.tight_layout()
    fig.savefig(out, dpi=180)
    plt.close(fig)
    return out


def _sample_sort_key(sample_id: str) -> int:
    digits = "".join(ch for ch in str(sample_id) if ch.isdigit())
    return int(digits) if digits else 0


def write_progress_chart(raw_rows: List[Dict[str, str]]) -> Path:
    fig, ax = plt.subplots(figsize=(12, 6))

    for strategy in STRATEGIES:
        subset = [
            r
            for r in raw_rows
            if r.get("strategy", "").lower() == strategy and r.get("benchmark", "").lower() == "gsm8k"
        ]
        subset.sort(
            key=lambda r: (
                int(as_float(r.get("repetition"), 0.0)),
                _sample_sort_key(r.get("sample_id", "0")),
            )
        )
        if not subset:
            continue

        cumulative: List[float] = []
        running = 0.0
        for idx, row in enumerate(subset, start=1):
            running += as_float(row.get("correct"), 0.0)
            cumulative.append(running / idx)

        ax.plot(range(1, len(cumulative) + 1), cumulative, linewidth=2, label=strategy.title())

    ax.set_xlabel("GSM8K Query Index")
    ax.set_ylabel("Cumulative Accuracy")
    ax.set_ylim(0, 1.05)
    ax.set_title("Progress Chart: Cumulative Accuracy During GSM8K Run")
    ax.grid(alpha=0.2)
    ax.legend()

    out = DOC_FIG_DIR / "progress_cumulative_accuracy_line.png"
    fig.tight_layout()
    fig.savefig(out, dpi=180)
    plt.close(fig)
    return out


def write_optimization_chart() -> Path:
    baseline_rows = read_csv(OPT_DIR / "gsm8k_baseline_summary.csv")
    optimized_rows = read_csv(OPT_DIR / "gsm8k_optimized_summary.csv")

    base = {row["strategy"].lower(): row for row in baseline_rows}
    opt = {row["strategy"].lower(): row for row in optimized_rows}

    x = np.arange(len(STRATEGIES))
    width = 0.36

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 9), sharex=True)

    base_latency = [as_float(base.get(s, {}).get("latency_mean_ms", 0.0)) for s in STRATEGIES]
    opt_latency = [as_float(opt.get(s, {}).get("latency_mean_ms", 0.0)) for s in STRATEGIES]
    ax1.bar(x - width / 2, base_latency, width, label="Baseline")
    ax1.bar(x + width / 2, opt_latency, width, label="Optimized")
    ax1.set_ylabel("Latency (ms)")
    ax1.set_title("Optimization Progress: GSM8K Latency")
    ax1.grid(axis="y", alpha=0.2)
    ax1.legend()

    base_acc = [as_float(base.get(s, {}).get("accuracy", 0.0)) for s in STRATEGIES]
    opt_acc = [as_float(opt.get(s, {}).get("accuracy", 0.0)) for s in STRATEGIES]
    ax2.bar(x - width / 2, base_acc, width, label="Baseline")
    ax2.bar(x + width / 2, opt_acc, width, label="Optimized")
    ax2.set_ylabel("Accuracy")
    ax2.set_ylim(0, 1.05)
    ax2.set_title("Optimization Progress: GSM8K Accuracy")
    ax2.set_xticks(x)
    ax2.set_xticklabels([s.title() for s in STRATEGIES])
    ax2.grid(axis="y", alpha=0.2)
    ax2.legend()

    out = DOC_FIG_DIR / "optimization_progress_bar_chart.png"
    fig.tight_layout()
    fig.savefig(out, dpi=180)
    plt.close(fig)
    return out


def build_report_json(
    metrics: Dict[str, Dict[str, Dict[str, float]]],
    raw_rows: List[Dict[str, str]],
    significance_rows: List[Dict[str, str]],
    optimization: Dict[str, Dict[str, Dict[str, float]]],
) -> Dict[str, Any]:
    avg_accuracy = {}
    avg_latency = {}
    for strategy in STRATEGIES:
        acc_vals = [metrics["accuracy"][b][strategy] for b in BENCHMARKS]
        lat_vals = [metrics["latency"][b][strategy] for b in BENCHMARKS]
        avg_accuracy[strategy] = sum(acc_vals) / len(acc_vals)
        avg_latency[strategy] = sum(lat_vals) / len(lat_vals)

    progress = {}
    for strategy in STRATEGIES:
        subset = [
            r
            for r in raw_rows
            if r.get("strategy", "").lower() == strategy and r.get("benchmark", "").lower() == "gsm8k"
        ]
        subset.sort(
            key=lambda r: (
                int(as_float(r.get("repetition"), 0.0)),
                _sample_sort_key(r.get("sample_id", "0")),
            )
        )
        running = 0.0
        cumulative: List[float] = []
        for idx, row in enumerate(subset, start=1):
            running += as_float(row.get("correct"), 0.0)
            cumulative.append(running / idx)
        progress[strategy] = cumulative

    return {
        "run_id": RUN_ID,
        "benchmarks": BENCHMARKS,
        "strategies": STRATEGIES,
        "accuracy": metrics["accuracy"],
        "latency_ms": metrics["latency"],
        "f1": metrics["f1"],
        "agreement": metrics["agreement"],
        "avg_accuracy": avg_accuracy,
        "avg_latency_ms": avg_latency,
        "progress_gsm8k": progress,
        "significance": significance_rows,
        "optimization": optimization,
    }


def write_report_data(report: Dict[str, Any]) -> None:
    json_path = DOC_DATA_DIR / "report_data.json"
    js_path = DOC_DATA_DIR / "report_data.js"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    js_path.write_text("window.REPORT_DATA = " + json.dumps(report, indent=2) + ";\n", encoding="utf-8")


def write_paper_tables(metrics: Dict[str, Dict[str, Dict[str, float]]], significance_rows: List[Dict[str, str]]) -> None:
    avg_rows = []
    for strategy in STRATEGIES:
        acc = [metrics["accuracy"][b][strategy] for b in BENCHMARKS]
        f1 = [metrics["f1"][b][strategy] for b in BENCHMARKS]
        lat = [metrics["latency"][b][strategy] for b in BENCHMARKS]
        agr = [metrics["agreement"][b][strategy] for b in BENCHMARKS]
        avg_rows.append((strategy, sum(acc) / 3, sum(f1) / 3, sum(lat) / 3, sum(agr) / 3))

    table_lines = [
        "\\begin{tabular}{lcccc}",
        "\\hline",
        "Strategy & Avg Acc. & Avg F1 & Avg Latency (ms) & Avg Agreement \\\\",
        "\\hline",
    ]
    for strategy, acc, f1, lat, agr in avg_rows:
        table_lines.append(f"{strategy} & {acc:.3f} & {f1:.3f} & {lat:.1f} & {agr:.3f} \\\\")
    table_lines.extend(["\\hline", "\\end{tabular}"])
    (PAPER_TABLE_DIR / "aggregate_strategy_results.tex").write_text("\n".join(table_lines) + "\n", encoding="utf-8")

    sig = [
        row
        for row in significance_rows
        if (as_float(row.get("paired_t_p"), 1.0) < 0.05) or (as_float(row.get("wilcoxon_p"), 1.0) < 0.05)
    ]
    sig_lines = [
        "\\begin{tabular}{lccccc}",
        "\\hline",
        "Comparison & Mean $\\Delta$ & t-p & Wilcoxon p & t<0.05 & W<0.05 \\\\",
        "\\hline",
    ]
    for row in sig:
        comp = row.get("comparison", "")
        mean_delta = as_float(row.get("mean_delta"), float("nan"))
        t_p = as_float(row.get("paired_t_p"), float("nan"))
        w_p = as_float(row.get("wilcoxon_p"), float("nan"))
        t_sig = "Yes" if t_p < 0.05 else "No"
        w_sig = "Yes" if w_p < 0.05 else "No"
        sig_lines.append(f"{comp} & {mean_delta:.3f} & {t_p:.4f} & {w_p:.4f} & {t_sig} & {w_sig} \\\\")
    if not sig:
        sig_lines.append("No significant pairs & -- & -- & -- & -- & -- \\\\")
    sig_lines.extend(["\\hline", "\\end{tabular}"])
    (PAPER_TABLE_DIR / "significance_highlights.tex").write_text("\n".join(sig_lines) + "\n", encoding="utf-8")


def copy_figures_to_paper(figures: List[Path]) -> None:
    for fig in figures:
        shutil.copy2(fig, PAPER_FIG_DIR / fig.name)

    existing = [
        RUN_DIR / "overall_accuracy.png",
        RUN_DIR / "mmlu" / "metrics.png",
        RUN_DIR / "gsm8k" / "metrics.png",
        RUN_DIR / "truthfulqa" / "metrics.png",
    ]
    for src in existing:
        if src.exists():
            if src.name == "metrics.png":
                renamed = f"{src.parent.name}_metrics.png"
            else:
                renamed = src.name
            shutil.copy2(src, PAPER_FIG_DIR / renamed)
            shutil.copy2(src, DOC_FIG_DIR / renamed)


def main() -> None:
    prepare_dirs()

    overall_rows = read_csv(RUN_DIR / "overall_summary.csv")
    raw_rows = read_csv(RUN_DIR / "gsm8k" / "raw_records.csv")
    significance_rows = read_csv(RUN_DIR / "overall_significance.csv")

    metrics = build_matrices(overall_rows)
    baseline_rows = read_csv(OPT_DIR / "gsm8k_baseline_summary.csv")
    optimized_rows = read_csv(OPT_DIR / "gsm8k_optimized_summary.csv")

    generated = [
        write_bar_chart_accuracy(metrics),
        write_line_chart_latency(metrics),
        write_pie_chart_avg_accuracy(metrics),
        write_progress_chart(raw_rows),
        write_optimization_chart(),
    ]

    baseline_map = {
        row.get("strategy", "").lower(): {
            "accuracy": as_float(row.get("accuracy"), 0.0),
            "latency_mean_ms": as_float(row.get("latency_mean_ms"), 0.0),
        }
        for row in baseline_rows
    }
    optimized_map = {
        row.get("strategy", "").lower(): {
            "accuracy": as_float(row.get("accuracy"), 0.0),
            "latency_mean_ms": as_float(row.get("latency_mean_ms"), 0.0),
        }
        for row in optimized_rows
    }
    report = build_report_json(
        metrics,
        raw_rows,
        significance_rows,
        optimization={"baseline": baseline_map, "optimized": optimized_map},
    )
    write_report_data(report)
    write_paper_tables(metrics, significance_rows)
    copy_figures_to_paper(generated)

    print("Generated visual assets and paper tables.")
    for path in generated:
        print(path.relative_to(ROOT))


if __name__ == "__main__":
    main()
