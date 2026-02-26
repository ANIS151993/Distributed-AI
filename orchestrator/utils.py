from __future__ import annotations

import json
import os
import random
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import numpy as np
except Exception:  # pragma: no cover
    np = None

try:
    import psutil
except Exception:  # pragma: no cover
    psutil = None

try:
    import torch
except Exception:  # pragma: no cover
    torch = None

try:
    import pynvml
except Exception:  # pragma: no cover
    pynvml = None

import yaml

_JSON_PATTERN = re.compile(r"\{.*\}", re.DOTALL)
_NON_ALNUM = re.compile(r"[^a-z0-9\-\.\s]")
_WS = re.compile(r"\s+")


@dataclass
class AgentConfig:
    id: str
    host: str
    port: int
    model: str
    temperature: float = 0.2
    max_tokens: int = 256
    base_weight: float = 1.0
    topic_tags: List[str] = field(default_factory=lambda: ["general"])
    enabled: bool = True



def load_agent_config(path: str | Path) -> Tuple[Dict[str, Any], List[AgentConfig]]:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Agent config not found: {path}")
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    global_cfg = raw.get("global", {})
    agents: List[AgentConfig] = []
    for item in raw.get("agents", []):
        agents.append(
            AgentConfig(
                id=str(item["id"]),
                host=str(item.get("host", "127.0.0.1")),
                port=int(item.get("port", 11434)),
                model=str(item["model"]),
                temperature=float(item.get("temperature", 0.2)),
                max_tokens=int(item.get("max_tokens", 256)),
                base_weight=float(item.get("base_weight", 1.0)),
                topic_tags=list(item.get("topic_tags", ["general"])),
                enabled=bool(item.get("enabled", True)),
            )
        )
    return global_cfg, agents



def ensure_parent(path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)



def append_jsonl(path: str | Path, payload: Dict[str, Any]) -> None:
    ensure_parent(path)
    with Path(path).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=True) + "\n")



def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()



def safe_json_parse(text: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None
    text = text.strip()
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass
    match = _JSON_PATTERN.search(text)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(0))
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        return None
    return None



def normalize_answer(value: Any) -> str:
    if value is None:
        value = ""
    if not isinstance(value, str):
        value = str(value)
    value = value.strip().lower()
    value = value.replace("**", "").replace("`", "")

    # Preserve MCQ option letters when models answer like "B", "B.", or "B. ...".
    single_option = re.fullmatch(r"\s*([a-d])\s*[\.\)\:\-]?\s*", value)
    if single_option:
        return single_option.group(1)
    prefixed_option = re.match(r"^\s*([a-d])\s*[\.\)\:\-]\s+.+$", value)
    if prefixed_option:
        return prefixed_option.group(1)

    value = _NON_ALNUM.sub(" ", value)
    value = _WS.sub(" ", value).strip()
    value = value.rstrip(".")
    return value



def extract_answer(raw_text: str, parsed: Optional[Dict[str, Any]] = None) -> str:
    if parsed and "answer" in parsed:
        parsed_answer = parsed.get("answer")
        if parsed_answer is not None:
            answer_text = str(parsed_answer).strip()
            if answer_text:
                return answer_text

    patterns = [
        r"final answer\s*[:\-]\s*(.+)",
        r"answer\s*[:\-]\s*(.+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, raw_text, flags=re.IGNORECASE)
        if match:
            return match.group(1).splitlines()[0].strip()

    lines = [ln.strip() for ln in raw_text.splitlines() if ln.strip()]
    if not lines:
        return ""
    return lines[0][:256]



def parse_confidence(value: Any, default: float = 0.5) -> float:
    try:
        conf = float(value)
    except Exception:
        conf = default
    return max(0.0, min(1.0, conf))



def approx_token_count(text: str) -> int:
    return max(1, len(re.findall(r"\w+", text or "")))



def set_global_seed(seed: int, deterministic: bool = True) -> None:
    os.environ["PYTHONHASHSEED"] = str(seed)
    random.seed(seed)
    if np is not None:
        np.random.seed(seed)
    if torch is not None:
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
        if deterministic:
            torch.backends.cudnn.deterministic = True
            torch.backends.cudnn.benchmark = False



def pairwise_agreement(answers: List[str]) -> float:
    clean = [normalize_answer(ans) for ans in answers if normalize_answer(ans)]
    n = len(clean)
    if n <= 1:
        return 1.0

    agree = 0
    total = 0
    for i in range(n):
        for j in range(i + 1, n):
            total += 1
            if clean[i] == clean[j]:
                agree += 1
    if total == 0:
        return 1.0
    return agree / total



def most_common(items: List[str]) -> Tuple[str, int]:
    if not items:
        return "", 0
    counts = Counter(items)
    winner, count = counts.most_common(1)[0]
    return winner, count



def token_f1(prediction: str, truth: str) -> float:
    pred_tokens = normalize_answer(prediction).split()
    truth_tokens = normalize_answer(truth).split()
    if not pred_tokens and not truth_tokens:
        return 1.0
    if not pred_tokens or not truth_tokens:
        return 0.0

    pred_counts = Counter(pred_tokens)
    truth_counts = Counter(truth_tokens)
    common = sum((pred_counts & truth_counts).values())
    if common == 0:
        return 0.0

    precision = common / len(pred_tokens)
    recall = common / len(truth_tokens)
    return 2 * precision * recall / (precision + recall)



def _gpu_usage_via_nvml() -> List[Dict[str, Any]]:
    if pynvml is None:
        return []
    devices: List[Dict[str, Any]] = []
    try:
        pynvml.nvmlInit()
        count = pynvml.nvmlDeviceGetCount()
        for idx in range(count):
            handle = pynvml.nvmlDeviceGetHandleByIndex(idx)
            util = pynvml.nvmlDeviceGetUtilizationRates(handle)
            mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
            name = pynvml.nvmlDeviceGetName(handle)
            if isinstance(name, bytes):
                name = name.decode("utf-8", errors="ignore")
            devices.append(
                {
                    "index": idx,
                    "name": str(name),
                    "utilization_percent": float(util.gpu),
                    "memory_used_mb": round(mem.used / (1024**2), 2),
                    "memory_total_mb": round(mem.total / (1024**2), 2),
                }
            )
    except Exception:
        return []
    finally:
        try:
            pynvml.nvmlShutdown()
        except Exception:
            pass
    return devices



def get_resource_usage() -> Dict[str, Any]:
    usage: Dict[str, Any] = {
        "cpu_percent": None,
        "memory_percent": None,
        "memory_used_mb": None,
        "gpu": [],
    }
    if psutil is not None:
        try:
            usage["cpu_percent"] = float(psutil.cpu_percent(interval=None))
            vm = psutil.virtual_memory()
            usage["memory_percent"] = float(vm.percent)
            usage["memory_used_mb"] = round(float(vm.used) / (1024**2), 2)
        except Exception:
            pass
    usage["gpu"] = _gpu_usage_via_nvml()
    return usage



def stable_choice(options: List[str], key: str) -> str:
    if not options:
        return ""
    idx = abs(hash(key)) % len(options)
    return options[idx]
