# Distributed AI: Local Multi-Agent LLM Ensemble on Proxmox

A publication-oriented, fully local distributed AI system for ensemble LLM inference, benchmarking, and statistical reporting.

This repository documents and implements a real deployment on Ubuntu 24.04 VMs in a Proxmox LAN, with an orchestrator + multiple Ollama agents.

## 0. Quick Story (What We Built)

You asked for an IEEE-conference-grade distributed AI infrastructure where:

- One orchestrator receives a query.
- Query is distributed to multiple local AI agent nodes.
- Each agent uses a different LLM (local-only inference).
- Responses are aggregated by multiple ensemble algorithms.
- Metrics are logged for statistical benchmarking.
- Outputs are reproducible and paper-ready.

That is exactly what this system now does.

## 1. Real Deployment Topology (Live Environment)

### VM Mapping

- `vm-orchestrator` -> `172.16.185.223` (VM ID 105)
- `vm-agent-llama3` -> `172.16.185.209` (VM ID 101)
- `vm-agent-mistral` -> `172.16.185.218` (VM ID 102)
- `vm-agent-phi3` -> `172.16.185.220` (VM ID 103)
- `vm-agent-gemma` -> `172.16.185.222` (VM ID 104)

### ASCII Architecture Diagram

```text
                              +------------------------------------------+
User / Bench Runner ---------->| Orchestrator VM (172.16.185.223)        |
 /query, /health              | FastAPI + Async Fan-out + Aggregation    |
                              | Strategies: majority, weighted, isp,     |
                              | topic, debate                            |
                              +-------------------+----------------------+
                                                  |
         ----------------------------------------------------------------------------------
         |                                 |                               |              |
+---------------------------+  +---------------------------+  +---------------------------+  +---------------------------+
| Agent 1 (172.16.185.209)  |  | Agent 2 (172.16.185.218)  |  | Agent 3 (172.16.185.220)  |  | Agent 4 (172.16.185.222)  |
| Ollama :11434             |  | Ollama :11434             |  | Ollama :11434             |  | Ollama :11434             |
| llama3.2:3b               |  | qwen2.5:3b                |  | phi3:mini                 |  | gemma2:2b                 |
+---------------------------+  +---------------------------+  +---------------------------+  +---------------------------+
```

## 2. What We Did, and Why

This section is written as an interactive engineering log so you can use it directly in project documentation.

### Phase A: Base Deployment

1. Synchronized project to orchestrator and all agent VMs.
2. Installed Python environment and dependencies.
3. Installed Ollama on all agent VMs.
4. Pulled local CPU-friendly models on each agent.
5. Installed systemd services for auto-start.

Why:
- Needed a reproducible base cluster with autonomous restart behavior.
- Needed full local-only inference (no cloud inference dependency).

### Phase B: Connectivity Fixes

Observed issue:
- Orchestrator health showed two agents unhealthy.

Root cause:
- Ollama on some agents listened on `127.0.0.1:11434` only.

Fix:
- Configured Ollama systemd override with:
  - `OLLAMA_HOST=0.0.0.0:11434`
- Restarted Ollama services.

Why:
- Orchestrator needs LAN reachability to every agent.

### Phase C: Runtime Bottleneck Fixes

Observed issue:
- Large benchmark runs were very slow on CPU-only profile.
- Debate strategy timed out often.

Fixes implemented:

1. **Lightweight answer protocol**
- Prompt changed to short final-answer style.
- Lower default `max_tokens`.
- Added stop sequences.

Why:
- Reduces generation length and latency.

2. **Direct strategy sharing (major speedup)**
- One inference fan-out now computes all direct strategies:
  - `majority`, `weighted`, `isp`, `topic`
- Avoids repeating expensive model calls four times.

Why:
- Keeps benchmark methodology, cuts redundant compute.

3. **Debate early-stop + bounded runtime**
- If round-1 consensus is already perfect, skip round-2 critique.
- Debate timeout constrained.
- In benchmarks, debate defaults to lighter panel when needed.

Why:
- Debate is the most expensive strategy; this prevents long-tail stalls.

4. **Answer normalization improvements**
- Handles forms like `B.` and `A. 30` more robustly.

Why:
- Reduces false mismatch penalties in MCQ-style benchmarks.

5. **Timeout tuning**
- Request timeout reduced from `180s` to `120s` globally.

Why:
- Improves throughput under heavy load by limiting stalled calls.

## 3. Ensemble Strategies Implemented

- `majority`: self-consistency style majority vote.
- `weighted`: adaptive weighted vote using accuracy history.
- `isp`: inverse surprising popularity with second-order agreement.
- `topic`: topic routing + weighted aggregation.
- `debate`: two-round multi-agent critique protocol (with early-stop optimization).

## 4. Evaluation and Statistical Framework

Benchmarks:
- MMLU
- GSM8K
- TruthfulQA

Metrics tracked:
- Accuracy
- F1
- Latency (mean/std)
- Agreement rate
- CPU/GPU resource usage

Statistical tests:
- Paired t-test
- Wilcoxon signed-rank
- 95% confidence intervals

## 5. Outputs Generated

Each run writes outputs under `results/run_*/...`.

Outputs generated as:
- CSV
- JSON
- PNG plots
- IEEE LaTeX tables

Typical files:
- `raw_records.csv`, `raw_records.json`
- `summary.csv`, `summary.json`
- `significance.csv`, `significance.json`
- `metrics.png`
- `summary_table.tex`, `significance_table.tex`
- `overall_summary.csv`, `overall_significance.csv`, `overall_summary_table.tex`

## 6. Repository Structure

```text
Distributed-AI/
├── orchestrator/
│   ├── main.py
│   ├── aggregator.py
│   ├── router.py
│   ├── debate.py
│   ├── evaluator.py
│   └── utils.py
├── agents/
│   ├── agent_config.yaml
│   └── agent_config.docker.yaml
├── benchmarks/
│   ├── gsm8k_runner.py
│   ├── mmlu_runner.py
│   └── truthfulqa_runner.py
├── deploy/
│   ├── systemd/
│   └── cluster_config.example.yaml
├── scripts/
│   ├── setup_vm.sh
│   ├── install_ollama.sh
│   ├── install_systemd_services.sh
│   ├── health_check.sh
│   ├── pull_models_docker.sh
│   └── deploy_cluster.py
├── logs/
├── results/
├── run_experiments.py
├── docker-compose.yml
└── README.md
```

## 7. Step-by-Step Testing (Interactive)

Use these commands from your control terminal.

### Step 1: Create helper SSH function

```bash
PASS='MARC@151995$'
ORCH='172.16.185.223'
orch() { sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no -o PreferredAuthentications=password -o PubkeyAuthentication=no root@"$ORCH" "$@"; }
```

### Step 2: Health test

```bash
orch "curl -s http://127.0.0.1:8000/health | jq ."
orch "curl -s http://127.0.0.1:8000/agents | jq ."
```

Expected:
- `status: ok`
- 4 healthy agents.

### Step 3: Query test

```bash
orch "curl -s -X POST http://127.0.0.1:8000/query \
  -H 'Content-Type: application/json' \
  -d '{\"prompt\":\"What is 2+2? Return only the number.\",\"strategy\":\"majority\",\"seed\":42,\"deterministic\":true,\"temperature\":0.0,\"max_tokens\":24}' \
  | jq '{query_id,strategy,aggregate,total_latency_ms}'"
```

### Step 4: Test all strategies

```bash
orch "bash -lc 'for s in majority weighted isp topic debate; do
  echo ===$s===;
  curl -s -X POST http://127.0.0.1:8000/query \
    -H \"Content-Type: application/json\" \
    -d \"{\\\"prompt\\\":\\\"What is the capital of France?\\\",\\\"strategy\\\":\\\"$s\\\",\\\"seed\\\":42,\\\"deterministic\\\":true,\\\"temperature\\\":0.0,\\\"max_tokens\\\":24,\\\"max_agents\\\":2}\" \
    | jq \"{strategy,answer:.aggregate.answer,latency_ms:.total_latency_ms,agreement:.aggregate.agreement_rate}\";
done'"
```

### Step 5: Benchmark smoke test

```bash
orch "cd /root/distributed_ai && .venv/bin/python run_experiments.py \
  --orchestrator-url http://127.0.0.1:8000 \
  --benchmarks mmlu,gsm8k,truthfulqa \
  --strategies majority,weighted,isp,topic,debate \
  --repetitions 1 \
  --samples-per-benchmark 2 \
  --seed 42 \
  --deterministic \
  --max-agents 2"
```

### Step 6: Full publication run

```bash
orch "cd /root/distributed_ai && .venv/bin/python run_experiments.py \
  --orchestrator-url http://127.0.0.1:8000 \
  --benchmarks mmlu,gsm8k,truthfulqa \
  --strategies majority,weighted,isp,topic,debate \
  --repetitions 5 \
  --samples-per-benchmark 20 \
  --seed 42 \
  --deterministic"
```

## 8. Reproducibility Controls

- Seed control at request and benchmark levels.
- Deterministic mode (`temperature=0.0` when enabled).
- Independent/dependent variables logged in `logs/query_metrics.jsonl`.
- Fixed benchmark runners and output schema.

## 9. Security and Deployment Best Practices

- Keep orchestrator/agent ports LAN-restricted.
- Put external access through Cloudflare Tunnel + strict policies.
- Avoid public exposure of raw agent ports.
- Rotate credentials and SSH keys.
- Keep VM snapshots for experiment checkpoints.

## 10. GPU or CPU Mode

- CPU mode: smaller models (`3b` / `mini`) used by default.
- GPU mode: switch to larger models (`8b`, `9b`) in `agents/agent_config.yaml`.
- NVIDIA passthrough instructions are included in this repo’s deployment scripts and setup notes.

## 11. Why This Design Is Publication-Ready

- Modular, switchable aggregation strategies.
- Deterministic and repeatable run controls.
- Logged independent vs dependent variables.
- Statistical significance tests built into pipeline.
- Export-ready CSV/JSON/PNG/LaTeX artifacts.

## 12. Copyright

Copyright (c) 2026 Md Anisur Rahman Chowdhury  
Email: chowdhur014@gannon.edu  
Affiliation: Gannon University

All rights reserved.
