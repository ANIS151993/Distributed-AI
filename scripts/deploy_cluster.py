#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import yaml


def run(cmd: List[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    print("+", " ".join(shlex.quote(part) for part in cmd), flush=True)
    return subprocess.run(cmd, text=True, check=check)


def run_capture(cmd: List[str], *, check: bool = True) -> str:
    print("+", " ".join(shlex.quote(part) for part in cmd), flush=True)
    proc = subprocess.run(cmd, text=True, capture_output=True)
    if check and proc.returncode != 0:
        raise subprocess.CalledProcessError(proc.returncode, cmd, output=proc.stdout, stderr=proc.stderr)
    return (proc.stdout or "").strip()


def ssh(user: str, host: str, port: int, command: str, *, check: bool = True) -> None:
    run(
        [
            "ssh",
            "-o",
            "StrictHostKeyChecking=accept-new",
            "-p",
            str(port),
            f"{user}@{host}",
            command,
        ],
        check=check,
    )


def ssh_capture(user: str, host: str, port: int, command: str, *, check: bool = True) -> str:
    return run_capture(
        [
            "ssh",
            "-o",
            "StrictHostKeyChecking=accept-new",
            "-p",
            str(port),
            f"{user}@{host}",
            command,
        ],
        check=check,
    )


def scp(local_path: str, user: str, host: str, port: int, remote_path: str) -> None:
    run(
        [
            "scp",
            "-o",
            "StrictHostKeyChecking=accept-new",
            "-P",
            str(port),
            local_path,
            f"{user}@{host}:{remote_path}",
        ]
    )


def rsync_project(local_path: str, user: str, host: str, port: int, remote_path: str) -> None:
    run(
        [
            "rsync",
            "-az",
            "--delete",
            "--exclude",
            ".venv",
            "--exclude",
            "results",
            "--exclude",
            "logs",
            "--exclude",
            "__pycache__",
            "--exclude",
            "*.pyc",
            "-e",
            f"ssh -o StrictHostKeyChecking=accept-new -p {port}",
            f"{local_path.rstrip('/')}/",
            f"{user}@{host}:{remote_path.rstrip('/')}/",
        ]
    )


def _default_topic_tags(model: str) -> List[str]:
    m = model.lower()
    if "phi" in m:
        return ["general", "coding", "math"]
    if "mistral" in m:
        return ["general", "science", "reasoning"]
    if "llama" in m:
        return ["general", "reasoning", "factual"]
    if "gemma" in m:
        return ["general", "factual", "science"]
    if "qwen" in m:
        return ["general", "reasoning", "coding"]
    return ["general"]


def _default_base_weight(model: str) -> float:
    m = model.lower()
    if any(k in m for k in ["9b", "8b"]):
        return 1.1
    if "7b" in m:
        return 1.0
    if any(k in m for k in ["3b", "2b"]):
        return 0.9
    if "mini" in m:
        return 0.85
    return 1.0


def _safe_float(text: str, default: float = 0.0) -> float:
    try:
        return float(text.strip())
    except Exception:
        return default


def probe_agent_resources(user: str, host: str, port: int) -> Dict[str, Any]:
    ram_cmd = r"awk '/MemTotal/ {printf \"%.1f\", $2/1024/1024}' /proc/meminfo"
    ram_out = ssh_capture(user, host, port, ram_cmd, check=False)
    ram_gb = _safe_float(ram_out, 0.0)

    gpu_cmd = "nvidia-smi --query-gpu=name,memory.total --format=csv,noheader,nounits 2>/dev/null | head -n1"
    gpu_out = ssh_capture(user, host, port, gpu_cmd, check=False)
    gpu_name = ""
    vram_gb = 0.0
    if gpu_out:
        parts = [p.strip() for p in gpu_out.split(",", 1)]
        if parts:
            gpu_name = parts[0]
        if len(parts) > 1:
            vram_gb = _safe_float(parts[1], 0.0) / 1024.0

    return {
        "ram_gb": round(ram_gb, 1),
        "gpu_name": gpu_name,
        "vram_gb": round(vram_gb, 1),
    }


def choose_model_for_agent(agent: Dict[str, Any], index: int, resources: Dict[str, Any]) -> str:
    requested = str(agent.get("model", "auto")).strip().lower()
    if requested not in {"", "auto", "adaptive"}:
        return str(agent["model"])

    preferred_model = str(agent.get("preferred_model", "")).strip()
    ram_gb = float(resources.get("ram_gb", 0.0))
    vram_gb = float(resources.get("vram_gb", 0.0))

    cpu_pool = ["llama3.2:3b", "qwen2.5:3b", "phi3:mini", "gemma2:2b"]
    mixed_pool = ["llama3:8b", "mistral:7b", "phi3:mini", "gemma2:2b"]
    gpu_pool = ["llama3:8b", "mistral:7b", "phi3:mini", "gemma:9b"]

    if vram_gb >= 14.0:
        pool = gpu_pool
    elif ram_gb >= 24.0:
        pool = mixed_pool
    else:
        pool = cpu_pool

    if preferred_model:
        low_pref = preferred_model.lower()
        if vram_gb >= 14.0:
            return preferred_model
        if any(k in low_pref for k in ["9b", "8b", "7b"]) and ram_gb < 24.0:
            pass
        else:
            return preferred_model

    return pool[index % len(pool)]


def print_resolved_agent_plan(agents: List[Dict[str, Any]]) -> None:
    print("Resolved agent plan:")
    for agent in agents:
        info = agent.get("detected_resources", {})
        print(
            f"- {agent['id']}: host={agent['host']} "
            f"model={agent.get('resolved_model', agent.get('model'))} "
            f"RAM={info.get('ram_gb', 'n/a')}GB "
            f"GPU={info.get('gpu_name') or 'none'} "
            f"VRAM={info.get('vram_gb', 0)}GB"
        )


def generate_agent_config(agents: List[Dict[str, Any]], request_timeout_s: int = 180) -> Dict[str, Any]:
    return {
        "global": {
            "seed": 42,
            "deterministic": True,
            "request_timeout_s": request_timeout_s,
            "weight_learning_rate": 0.2,
        },
        "agents": [
            {
                "id": str(agent["id"]),
                "host": str(agent["host"]),
                "port": 11434,
                "model": str(agent.get("resolved_model", agent.get("model", "phi3:mini"))),
                "temperature": 0.2,
                "max_tokens": 256,
                "base_weight": float(
                    agent.get(
                        "base_weight",
                        _default_base_weight(str(agent.get("resolved_model", agent.get("model", "")))),
                    )
                ),
                "topic_tags": list(
                    agent.get(
                        "topic_tags",
                        _default_topic_tags(str(agent.get("resolved_model", agent.get("model", "")))),
                    )
                ),
                "enabled": bool(agent.get("enabled", True)),
            }
            for agent in agents
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="One-command deployment for distributed_ai cluster")
    parser.add_argument("--config", required=True, help="Path to cluster config YAML")
    parser.add_argument(
        "--skip-benchmarks",
        action="store_true",
        help="Skip benchmark run even if config enables it",
    )
    parser.add_argument(
        "--mock-mode",
        action="store_true",
        help="Run post-deploy benchmark in mock mode",
    )
    parser.add_argument(
        "--only-sync",
        action="store_true",
        help="Only rsync project files to nodes",
    )
    return parser.parse_args()


def validate_config(cfg: Dict[str, Any]) -> None:
    if "project" not in cfg or "orchestrator" not in cfg or "agents" not in cfg:
        raise ValueError("Config must include project, orchestrator, and agents sections")
    if not isinstance(cfg.get("agents"), list) or len(cfg["agents"]) < 4:
        raise ValueError("Config must include at least 4 agents")


def remote_setup_vm(user: str, host: str, port: int, remote_path: str) -> None:
    cmd = (
        f"cd {shlex.quote(remote_path)} && "
        f"bash scripts/setup_vm.sh {shlex.quote(remote_path)}"
    )
    ssh(user, host, port, cmd)


def remote_install_ollama(user: str, host: str, port: int, remote_path: str, model: str) -> None:
    cmd = (
        f"cd {shlex.quote(remote_path)} && "
        f"bash scripts/install_ollama.sh {shlex.quote(model)}"
    )
    ssh(user, host, port, cmd)


def remote_install_orchestrator_services(
    user: str,
    host: str,
    port: int,
    remote_path: str,
) -> None:
    cmd = (
        f"cd {shlex.quote(remote_path)} && "
        f"bash scripts/install_systemd_services.sh {shlex.quote(remote_path)} {shlex.quote(user)} && "
        "sudo systemctl restart orchestrator"
    )
    ssh(user, host, port, cmd)


def remote_health_check(user: str, host: str, port: int, remote_path: str) -> None:
    cmd = (
        f"cd {shlex.quote(remote_path)} && "
        "bash scripts/health_check.sh http://127.0.0.1:8000"
    )
    ssh(user, host, port, cmd)


def remote_run_benchmarks(
    user: str,
    host: str,
    port: int,
    remote_path: str,
    benchmark_cfg: Dict[str, Any],
    mock_mode: bool,
) -> None:
    suites = benchmark_cfg.get("suites", ["mmlu", "gsm8k", "truthfulqa"])
    strategies = benchmark_cfg.get("strategies", ["majority", "weighted", "isp", "topic", "debate"])
    reps = int(benchmark_cfg.get("repetitions", 5))
    samples = int(benchmark_cfg.get("samples_per_benchmark", 20))
    seed = int(benchmark_cfg.get("seed", 42))
    deterministic = bool(benchmark_cfg.get("deterministic", True))

    cmd = (
        f"cd {shlex.quote(remote_path)} && "
        "source .venv/bin/activate && "
        "python run_experiments.py "
        "--orchestrator-url http://127.0.0.1:8000 "
        f"--benchmarks {shlex.quote(','.join(suites))} "
        f"--strategies {shlex.quote(','.join(strategies))} "
        f"--repetitions {reps} "
        f"--samples-per-benchmark {samples} "
        f"--seed {seed} "
        f"{'--deterministic ' if deterministic else ''}"
        f"{'--mock-mode ' if mock_mode else ''}"
    )
    ssh(user, host, port, f"bash -lc {shlex.quote(cmd)}")


def main() -> int:
    args = parse_args()
    cfg_path = Path(args.config).resolve()
    if not cfg_path.exists():
        print(f"Config not found: {cfg_path}", file=sys.stderr)
        return 1

    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    try:
        validate_config(cfg)
    except Exception as exc:
        print(f"Invalid config: {exc}", file=sys.stderr)
        return 1

    project = cfg["project"]
    local_path = str(Path(project["local_path"]).resolve())
    remote_path = str(project.get("remote_path", "/opt/distributed_ai"))

    orchestrator = cfg["orchestrator"]
    orch_host = str(orchestrator["host"])
    orch_user = str(orchestrator["user"])
    orch_port = int(orchestrator.get("port", 22))

    agents: List[Dict[str, Any]] = list(cfg["agents"])

    nodes = [{"host": orch_host, "user": orch_user, "port": orch_port}] + [
        {
            "host": str(agent["host"]),
            "user": str(agent["user"]),
            "port": int(agent.get("port", 22)),
        }
        for agent in agents
    ]

    # Sync project to every node first.
    for node in nodes:
        rsync_project(local_path, node["user"], node["host"], node["port"], remote_path)

    if args.only_sync:
        print("Sync complete (--only-sync set).")
        return 0

    # Setup orchestrator runtime.
    remote_setup_vm(orch_user, orch_host, orch_port, remote_path)

    # Setup each agent VM and install model.
    for idx, agent in enumerate(agents):
        remote_setup_vm(str(agent["user"]), str(agent["host"]), int(agent.get("port", 22)), remote_path)
        resources = probe_agent_resources(
            str(agent["user"]),
            str(agent["host"]),
            int(agent.get("port", 22)),
        )
        selected_model = choose_model_for_agent(agent, idx, resources)
        agent["resolved_model"] = selected_model
        agent["detected_resources"] = resources
        remote_install_ollama(
            str(agent["user"]),
            str(agent["host"]),
            int(agent.get("port", 22)),
            remote_path,
            str(selected_model),
        )

    print_resolved_agent_plan(agents)

    resolved_plan = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "orchestrator": {"host": orch_host, "user": orch_user, "port": orch_port},
        "agents": agents,
    }
    resolved_plan_path = Path(local_path) / "deploy" / "resolved_cluster_plan.yaml"
    resolved_plan_path.write_text(yaml.safe_dump(resolved_plan, sort_keys=False), encoding="utf-8")
    print(f"Saved resolved plan: {resolved_plan_path}")

    # Generate and upload orchestrator agent config from cluster spec.
    agent_cfg = generate_agent_config(agents)
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False, encoding="utf-8") as tmp:
        yaml.safe_dump(agent_cfg, tmp, sort_keys=False)
        tmp_path = tmp.name

    scp(
        tmp_path,
        orch_user,
        orch_host,
        orch_port,
        f"{remote_path.rstrip('/')}/agents/agent_config.yaml",
    )

    # Install and start orchestrator service.
    remote_install_orchestrator_services(orch_user, orch_host, orch_port, remote_path)

    # Reload orchestrator config.
    ssh(
        orch_user,
        orch_host,
        orch_port,
        "curl -fsS -X POST http://127.0.0.1:8000/reload-agents",
    )

    # Health check.
    remote_health_check(orch_user, orch_host, orch_port, remote_path)

    benchmark_cfg = cfg.get("benchmarks", {})
    run_after_deploy = bool(benchmark_cfg.get("run_after_deploy", True)) and not args.skip_benchmarks
    if run_after_deploy:
        remote_run_benchmarks(
            orch_user,
            orch_host,
            orch_port,
            remote_path,
            benchmark_cfg,
            args.mock_mode,
        )

    print("Cluster deployment complete.")
    print(f"Orchestrator: http://{orch_host}:8000")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
