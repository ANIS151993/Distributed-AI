from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable, Dict, List

from .aggregator import AggregationManager

QueryFn = Callable[[Any, str, float, int, int, str], Awaitable[Dict[str, Any]]]


class DebateEngine:
    def __init__(self, aggregator: AggregationManager) -> None:
        self.aggregator = aggregator

    async def run(
        self,
        query: str,
        agents: List[Any],
        query_fn: QueryFn,
        temperature: float,
        seed: int,
        max_tokens: int,
    ) -> Dict[str, Any]:
        round1_prompt = (
            "You are in a multi-agent panel. Provide only your best final answer in one short line.\n\n"
            f"Question:\n{query}"
        )
        round1_tasks = [
            query_fn(agent, round1_prompt, temperature, seed, max_tokens, "round1")
            for agent in agents
        ]
        round1_responses = await asyncio.gather(*round1_tasks)
        round1_final = self.aggregator.majority_vote(round1_responses)

        # Skip critique round when first-round consensus is already perfect.
        if round1_final.answer and round1_final.agreement_rate >= 1.0:
            return {
                "strategy": "debate",
                "round1": round1_responses,
                "round2": [],
                "final": round1_final.to_dict(),
                "metadata": {"early_stop": True},
            }

        peer_summary_lines = []
        for response in round1_responses:
            peer_summary_lines.append(
                f"- {response['agent_id']} ({response['model_id']}): answer={response.get('answer','')} conf={response.get('confidence', 0.5)}"
            )
        peer_summary = "\n".join(peer_summary_lines)

        round2_tasks = []
        for agent in agents:
            previous = next((item for item in round1_responses if item["agent_id"] == agent.id), {})
            round2_prompt = (
                "Round 2 debate. Compare with peers and revise if needed.\n"
                f"Original question:\n{query}\n\n"
                f"Your previous answer: {previous.get('answer', '')}\n"
                f"Peer responses:\n{peer_summary}\n\n"
                "Return only your revised final answer in one short line."
            )
            round2_tasks.append(query_fn(agent, round2_prompt, temperature, seed + 7, max_tokens, "round2"))

        round2_responses = await asyncio.gather(*round2_tasks)
        final = self.aggregator.majority_vote(round2_responses)

        return {
            "strategy": "debate",
            "round1": round1_responses,
            "round2": round2_responses,
            "final": final.to_dict(),
        }
