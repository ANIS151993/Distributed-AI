from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

from .utils import AgentConfig


@dataclass
class TopicRouter:
    topic_keywords: Dict[str, List[str]]

    @classmethod
    def default(cls) -> "TopicRouter":
        return cls(
            topic_keywords={
                "math": ["math", "algebra", "equation", "calculate", "number", "proof", "gsm8k"],
                "factual": ["who", "when", "where", "capital", "history", "fact", "truthful", "truthfulqa"],
                "science": ["biology", "chemistry", "physics", "scientific", "experiment", "mmlu"],
                "coding": ["python", "code", "algorithm", "function", "debug", "program"],
                "reasoning": ["why", "reason", "logic", "infer", "deduce", "explain"],
            }
        )

    def detect_topic(self, query: str) -> str:
        text = query.lower()
        scores: Dict[str, int] = {topic: 0 for topic in self.topic_keywords}

        for topic, keys in self.topic_keywords.items():
            for key in keys:
                if key in text:
                    scores[topic] += 1

        best_topic, best_score = "general", 0
        for topic, score in scores.items():
            if score > best_score:
                best_topic, best_score = topic, score
        return best_topic

    def route(self, query: str, agents: List[AgentConfig], max_agents: int | None = None) -> Tuple[str, List[AgentConfig]]:
        topic = self.detect_topic(query)

        if topic == "general":
            candidates = [a for a in agents if a.enabled]
        else:
            candidates = [a for a in agents if a.enabled and (topic in a.topic_tags or "general" in a.topic_tags)]
            if not candidates:
                candidates = [a for a in agents if a.enabled]

        candidates = sorted(candidates, key=lambda a: a.base_weight, reverse=True)
        if max_agents is not None and max_agents > 0:
            candidates = candidates[:max_agents]
        return topic, candidates
