from __future__ import annotations

import random
import re
from typing import Any, Dict, List


FALLBACK_GSM8K = [
    {
        "id": "gsm8k_001",
        "prompt": "If Alice has 12 apples and gives 5 to Bob, how many apples does she have left? Return only the number.",
        "answer": "7",
        "max_tokens": 24,
    },
    {
        "id": "gsm8k_002",
        "prompt": "A train travels 60 miles in 2 hours at constant speed. How far will it travel in 5 hours? Return only the number.",
        "answer": "150",
        "max_tokens": 24,
    },
    {
        "id": "gsm8k_003",
        "prompt": "There are 8 boxes with 6 pencils each. How many pencils total? Return only the number.",
        "answer": "48",
        "max_tokens": 24,
    },
    {
        "id": "gsm8k_004",
        "prompt": "Tom buys 3 notebooks for $4 each and 2 pens for $2 each. How much total did he spend? Return only the number.",
        "answer": "16",
        "max_tokens": 24,
    },
    {
        "id": "gsm8k_005",
        "prompt": "A class has 24 students. If 1/3 are absent, how many are present? Return only the number.",
        "answer": "16",
        "max_tokens": 24,
    },
]



def _normalize_numeric_answer(value: str) -> str:
    value = (value or "").strip()
    value = value.replace(",", "")
    match = re.search(r"-?\d+(?:\.\d+)?", value)
    return match.group(0) if match else value



def load_gsm8k_samples(limit: int = 50, seed: int = 42) -> List[Dict[str, Any]]:
    try:
        from datasets import load_dataset

        dataset = load_dataset("gsm8k", "main", split=f"test[:{limit}]")
        samples: List[Dict[str, Any]] = []
        for idx, row in enumerate(dataset):
            ans_raw = str(row.get("answer", "")).split("####")[-1].strip()
            samples.append(
                {
                    "id": f"gsm8k_{idx:04d}",
                    "prompt": row.get("question", "") + "\nReturn only the final numeric answer.",
                    "answer": _normalize_numeric_answer(ans_raw),
                    "max_tokens": 24,
                }
            )
        if samples:
            return samples
    except Exception:
        pass

    rnd = random.Random(seed)
    data = FALLBACK_GSM8K.copy()
    rnd.shuffle(data)
    return data[:limit]
