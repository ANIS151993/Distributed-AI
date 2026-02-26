from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List

from .utils import normalize_answer, pairwise_agreement


@dataclass
class AggregationResult:
    strategy: str
    answer: str
    scores: Dict[str, float]
    agreement_rate: float
    winning_agents: List[str]
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class AggregationManager:
    def __init__(self, weights_path: str, learning_rate: float = 0.2) -> None:
        self.weights_path = Path(weights_path)
        self.learning_rate = learning_rate
        self.weights: Dict[str, float] = {}
        self.history: Dict[str, List[int]] = defaultdict(list)
        self._load_weights()

    def _load_weights(self) -> None:
        if not self.weights_path.exists():
            return
        try:
            data = json.loads(self.weights_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                self.weights = {str(k): float(v) for k, v in data.items()}
        except Exception:
            self.weights = {}

    def _save_weights(self) -> None:
        self.weights_path.parent.mkdir(parents=True, exist_ok=True)
        self.weights_path.write_text(json.dumps(self.weights, indent=2), encoding="utf-8")

    def initialize_weights(self, agents: List[Any]) -> None:
        changed = False
        for agent in agents:
            if agent.id not in self.weights:
                self.weights[agent.id] = float(agent.base_weight)
                changed = True
        if changed:
            self._save_weights()

    def _ensure_answer_fields(self, responses: List[Dict[str, Any]]) -> None:
        for resp in responses:
            answer = normalize_answer(resp.get("answer", ""))
            pred = normalize_answer(resp.get("predicted_majority", answer))
            resp["normalized_answer"] = answer
            resp["normalized_predicted_majority"] = pred or answer

    def majority_vote(self, responses: List[Dict[str, Any]]) -> AggregationResult:
        self._ensure_answer_fields(responses)
        votes = Counter(resp["normalized_answer"] for resp in responses if resp["normalized_answer"])
        if not votes:
            return AggregationResult(
                strategy="majority",
                answer="",
                scores={},
                agreement_rate=0.0,
                winning_agents=[],
                metadata={"error": "No valid votes"},
            )

        winner, _ = votes.most_common(1)[0]
        winners = [resp["agent_id"] for resp in responses if resp["normalized_answer"] == winner]
        agreement = pairwise_agreement([resp["normalized_answer"] for resp in responses])
        return AggregationResult(
            strategy="majority",
            answer=winner,
            scores={k: float(v) for k, v in votes.items()},
            agreement_rate=agreement,
            winning_agents=winners,
            metadata={"n_agents": len(responses)},
        )

    def weighted_vote(self, responses: List[Dict[str, Any]]) -> AggregationResult:
        self._ensure_answer_fields(responses)
        scores: Dict[str, float] = defaultdict(float)
        for resp in responses:
            answer = resp["normalized_answer"]
            if not answer:
                continue
            agent_weight = self.weights.get(resp["agent_id"], 1.0)
            confidence = float(resp.get("confidence", 0.5))
            scores[answer] += agent_weight * max(0.0, min(confidence, 1.0))

        if not scores:
            return AggregationResult(
                strategy="weighted",
                answer="",
                scores={},
                agreement_rate=0.0,
                winning_agents=[],
                metadata={"error": "No valid weighted votes"},
            )

        winner = max(scores.items(), key=lambda kv: kv[1])[0]
        winners = [resp["agent_id"] for resp in responses if resp["normalized_answer"] == winner]
        agreement = pairwise_agreement([resp["normalized_answer"] for resp in responses])
        return AggregationResult(
            strategy="weighted",
            answer=winner,
            scores={k: float(v) for k, v in scores.items()},
            agreement_rate=agreement,
            winning_agents=winners,
            metadata={"weights": {aid: float(self.weights.get(aid, 1.0)) for aid in self.weights}},
        )

    def inverse_surprising_popularity(self, responses: List[Dict[str, Any]]) -> AggregationResult:
        self._ensure_answer_fields(responses)
        n = max(1, len(responses))

        actual_counts = Counter(resp["normalized_answer"] for resp in responses if resp["normalized_answer"])
        predicted_counts = Counter(
            resp["normalized_predicted_majority"] for resp in responses if resp["normalized_predicted_majority"]
        )

        if not actual_counts:
            return AggregationResult(
                strategy="isp",
                answer="",
                scores={},
                agreement_rate=0.0,
                winning_agents=[],
                metadata={"error": "No valid votes for ISP"},
            )

        eps = 1e-6
        isp_scores: Dict[str, float] = {}
        for answer in set(actual_counts) | set(predicted_counts):
            actual_share = actual_counts.get(answer, 0) / n
            predicted_share = predicted_counts.get(answer, 0) / n
            # Inverse surprising popularity: amplify answers with higher-than-expected support.
            isp_scores[answer] = actual_share / (predicted_share + eps)

        winner = max(isp_scores.items(), key=lambda kv: kv[1])[0]
        winners = [resp["agent_id"] for resp in responses if resp["normalized_answer"] == winner]
        agreement = pairwise_agreement([resp["normalized_answer"] for resp in responses])

        return AggregationResult(
            strategy="isp",
            answer=winner,
            scores={k: float(v) for k, v in isp_scores.items()},
            agreement_rate=agreement,
            winning_agents=winners,
            metadata={
                "actual_share": {k: float(v / n) for k, v in actual_counts.items()},
                "predicted_share": {k: float(v / n) for k, v in predicted_counts.items()},
                "second_order_agreement": float(
                    sum(
                        1
                        for resp in responses
                        if resp["normalized_answer"] == resp["normalized_predicted_majority"]
                    )
                    / n
                ),
            },
        )

    def topic_weighted_vote(self, responses: List[Dict[str, Any]], topic: str) -> AggregationResult:
        result = self.weighted_vote(responses)
        result.strategy = "topic"
        result.metadata["topic"] = topic
        return result

    def aggregate(self, strategy: str, responses: List[Dict[str, Any]], topic: str | None = None) -> AggregationResult:
        strategy = strategy.lower()
        if strategy == "majority":
            return self.majority_vote(responses)
        if strategy == "weighted":
            return self.weighted_vote(responses)
        if strategy == "isp":
            return self.inverse_surprising_popularity(responses)
        if strategy == "topic":
            return self.topic_weighted_vote(responses, topic or "general")
        raise ValueError(f"Unsupported strategy: {strategy}")

    def update_weights_from_ground_truth(
        self,
        responses: List[Dict[str, Any]],
        ground_truth: str,
        min_weight: float = 0.1,
        max_weight: float = 5.0,
    ) -> Dict[str, float]:
        truth = normalize_answer(ground_truth)
        if not truth:
            return self.weights

        for resp in responses:
            aid = resp["agent_id"]
            pred = normalize_answer(resp.get("answer", ""))
            correct = int(pred == truth)
            self.history[aid].append(correct)
            if len(self.history[aid]) > 512:
                self.history[aid] = self.history[aid][-512:]

            old = self.weights.get(aid, 1.0)
            updated = (1 - self.learning_rate) * old + self.learning_rate * float(correct)
            self.weights[aid] = max(min_weight, min(max_weight, updated))

        self._save_weights()
        return self.weights
