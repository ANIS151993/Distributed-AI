from __future__ import annotations

import random
from typing import Any, Dict, List


FALLBACK_MMLU = [
    {
        "id": "mmlu_001",
        "prompt": "What is the capital of Japan?\nA. Beijing\nB. Seoul\nC. Tokyo\nD. Bangkok\nAnswer with only the option letter.",
        "answer": "c",
        "max_tokens": 24,
    },
    {
        "id": "mmlu_002",
        "prompt": "Which gas is most abundant in Earth's atmosphere?\nA. Oxygen\nB. Nitrogen\nC. Carbon dioxide\nD. Argon\nAnswer with only the option letter.",
        "answer": "b",
        "max_tokens": 24,
    },
    {
        "id": "mmlu_003",
        "prompt": "Who wrote 'Pride and Prejudice'?\nA. Jane Austen\nB. Charles Dickens\nC. Mark Twain\nD. Virginia Woolf\nAnswer with only the option letter.",
        "answer": "a",
        "max_tokens": 24,
    },
    {
        "id": "mmlu_004",
        "prompt": "What is 15 * 3?\nA. 30\nB. 45\nC. 35\nD. 60\nAnswer with only the option letter.",
        "answer": "b",
        "max_tokens": 24,
    },
    {
        "id": "mmlu_005",
        "prompt": "Which organ pumps blood through the body?\nA. Liver\nB. Kidney\nC. Heart\nD. Lung\nAnswer with only the option letter.",
        "answer": "c",
        "max_tokens": 24,
    },
]


def _format_mmlu_prompt(question: str, choices: List[str]) -> str:
    letters = ["A", "B", "C", "D"]
    lines = [question]
    for idx, choice in enumerate(choices[:4]):
        lines.append(f"{letters[idx]}. {choice}")
    lines.append("Answer with only the option letter.")
    return "\n".join(lines)



def load_mmlu_samples(limit: int = 50, seed: int = 42) -> List[Dict[str, Any]]:
    try:
        from datasets import load_dataset

        dataset = load_dataset("cais/mmlu", "all", split=f"test[:{limit}]")
        samples: List[Dict[str, Any]] = []
        for idx, row in enumerate(dataset):
            choices = row.get("choices", [])
            answer_idx = int(row.get("answer", 0))
            answer_letter = ["a", "b", "c", "d"][answer_idx] if 0 <= answer_idx <= 3 else "a"
            samples.append(
                {
                    "id": f"mmlu_{idx:04d}",
                    "prompt": _format_mmlu_prompt(row.get("question", ""), choices),
                    "answer": answer_letter,
                    "max_tokens": 24,
                }
            )
        if samples:
            return samples
    except Exception:
        pass

    rnd = random.Random(seed)
    data = FALLBACK_MMLU.copy()
    rnd.shuffle(data)
    return data[:limit]
