from __future__ import annotations

import asyncio
import json
import os
import random
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .aggregator import AggregationManager
from .debate import DebateEngine
from .router import TopicRouter
from .utils import (
    AgentConfig,
    append_jsonl,
    approx_token_count,
    extract_answer,
    get_resource_usage,
    load_agent_config,
    normalize_answer,
    now_utc_iso,
    parse_confidence,
    safe_json_parse,
    set_global_seed,
    stable_choice,
)

BASE_DIR = Path(__file__).resolve().parents[1]
AGENT_CONFIG_PATH = Path(os.getenv("AGENT_CONFIG", BASE_DIR / "agents" / "agent_config.yaml"))
LOG_PATH = Path(os.getenv("QUERY_LOG_PATH", BASE_DIR / "logs" / "query_metrics.jsonl"))
WEIGHTS_PATH = Path(os.getenv("WEIGHTS_PATH", BASE_DIR / "logs" / "agent_weights.json"))


class QueryRequest(BaseModel):
    prompt: str
    strategy: Literal["majority", "weighted", "isp", "topic", "debate"] = "majority"
    temperature: float = 0.2
    deterministic: bool = True
    seed: int = 42
    max_tokens: int = 64
    max_agents: Optional[int] = None
    ground_truth: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    mock_mode: bool = False
    compute_all_direct: bool = False


class FeedbackRequest(BaseModel):
    ground_truth: str
    agent_answers: Dict[str, str]


class OrchestratorService:
    def __init__(self, config_path: Path) -> None:
        self.config_path = config_path
        self.global_cfg: Dict[str, Any] = {}
        self.agents: List[AgentConfig] = []
        self.router = TopicRouter.default()
        self.aggregator = AggregationManager(
            weights_path=str(WEIGHTS_PATH),
            learning_rate=float(os.getenv("WEIGHT_LEARNING_RATE", 0.2)),
        )
        self.debate_engine = DebateEngine(self.aggregator)
        self.request_timeout_s = 180.0
        self.reload_agents()

    def reload_agents(self) -> None:
        self.global_cfg, self.agents = load_agent_config(self.config_path)
        self.request_timeout_s = float(self.global_cfg.get("request_timeout_s", 180))
        self.aggregator.learning_rate = float(self.global_cfg.get("weight_learning_rate", 0.2))
        self.aggregator.initialize_weights(self.agents)

    @property
    def enabled_agents(self) -> List[AgentConfig]:
        return [agent for agent in self.agents if agent.enabled]

    def _build_prompt(self, query: str) -> str:
        return (
            "You are one model in a distributed local ensemble. "
            "Return only the final answer, very short, with no explanation.\n\n"
            f"Question:\n{query}"
        )

    async def _query_real_agent(
        self,
        client: httpx.AsyncClient,
        agent: AgentConfig,
        prompt: str,
        temperature: float,
        seed: int,
        max_tokens: int,
    ) -> Dict[str, Any]:
        url = f"http://{agent.host}:{agent.port}/api/generate"
        payload = {
            "model": agent.model,
            "prompt": self._build_prompt(prompt),
            "stream": False,
            "options": {
                "temperature": temperature,
                "seed": int(seed),
                "num_predict": int(max_tokens),
                "stop": ["\n\n", "\nExplanation:", "Explanation:"],
            },
        }

        started = time.perf_counter()
        try:
            resp = await client.post(url, json=payload, timeout=self.request_timeout_s)
            resp.raise_for_status()
            data = resp.json()
            raw_response = data.get("response", "")
            parsed = safe_json_parse(raw_response) or {}
            answer = extract_answer(raw_response, parsed)
            predicted_majority = parsed.get("predicted_majority", answer)
            confidence = parse_confidence(parsed.get("confidence", 0.55 if answer else 0.0))
            token_count = int(data.get("eval_count") or approx_token_count(raw_response))

            return {
                "agent_id": agent.id,
                "model_id": str(data.get("model", agent.model)),
                "response": raw_response,
                "answer": answer,
                "predicted_majority": predicted_majority,
                "confidence": confidence,
                "latency_ms": round((time.perf_counter() - started) * 1000.0, 3),
                "token_count": token_count,
                "error": None,
            }
        except Exception as exc:
            err_text = str(exc).strip() or exc.__class__.__name__
            return {
                "agent_id": agent.id,
                "model_id": agent.model,
                "response": "",
                "answer": "",
                "predicted_majority": "",
                "confidence": 0.0,
                "latency_ms": round((time.perf_counter() - started) * 1000.0, 3),
                "token_count": 0,
                "error": err_text,
            }

    async def _query_mock_agent(
        self,
        agent: AgentConfig,
        prompt: str,
        seed: int,
        stage: str,
    ) -> Dict[str, Any]:
        rnd = random.Random(f"{seed}-{agent.id}-{stage}-{prompt}")
        lowered = prompt.lower()

        if "2+2" in lowered or "2 + 2" in lowered:
            answer = "4"
        elif "capital of france" in lowered:
            answer = "paris"
        elif any(k in lowered for k in ["a.", "b.", "c.", "d."]):
            answer = stable_choice(["a", "b", "c", "d"], f"{seed}-{agent.id}-{prompt}")
        else:
            answer = stable_choice(
                ["true", "false", "42", "paris", "b"],
                f"{seed}-{agent.id}-{prompt}-{stage}",
            )

        predicted_majority = answer if rnd.random() > 0.25 else stable_choice(
            ["true", "false", "42", "paris", "b", "a", "c", "d"],
            f"{seed}-{agent.id}-pred-{prompt}",
        )
        confidence = round(0.45 + (rnd.random() * 0.5), 3)
        latency_ms = round(60 + rnd.random() * 220, 3)

        raw_response = json.dumps(
            {
                "answer": answer,
                "confidence": confidence,
                "predicted_majority": predicted_majority,
            }
        )
        return {
            "agent_id": agent.id,
            "model_id": agent.model,
            "response": raw_response,
            "answer": answer,
            "predicted_majority": predicted_majority,
            "confidence": confidence,
            "latency_ms": latency_ms,
            "token_count": approx_token_count(raw_response),
            "error": None,
        }

    async def _query_agent(
        self,
        agent: AgentConfig,
        prompt: str,
        temperature: float,
        seed: int,
        max_tokens: int,
        stage: str,
        mock_mode: bool,
        client: Optional[httpx.AsyncClient],
    ) -> Dict[str, Any]:
        if mock_mode:
            return await self._query_mock_agent(agent, prompt, seed, stage)
        if client is None:
            raise RuntimeError("HTTP client missing for non-mock execution")
        return await self._query_real_agent(client, agent, prompt, temperature, seed, max_tokens)

    async def collect_agent_responses(
        self,
        prompt: str,
        agents: List[AgentConfig],
        temperature: float,
        seed: int,
        max_tokens: int,
        mock_mode: bool,
        stage: str = "direct",
    ) -> List[Dict[str, Any]]:
        if not agents:
            return []

        if mock_mode:
            tasks = [
                self._query_agent(agent, prompt, temperature, seed, max_tokens, stage, True, None)
                for agent in agents
            ]
            return await asyncio.gather(*tasks)

        async with httpx.AsyncClient(timeout=self.request_timeout_s) as client:
            tasks = [
                self._query_agent(agent, prompt, temperature, seed, max_tokens, stage, False, client)
                for agent in agents
            ]
            return await asyncio.gather(*tasks)

    async def run_query(self, req: QueryRequest) -> Dict[str, Any]:
        started = time.perf_counter()
        if req.deterministic:
            req.temperature = 0.0
        set_global_seed(req.seed, req.deterministic)

        selected_agents = self.enabled_agents
        topic = "general"
        if req.strategy == "topic" and not req.compute_all_direct:
            topic, selected_agents = self.router.route(req.prompt, self.enabled_agents, req.max_agents)
        elif req.max_agents:
            selected_agents = selected_agents[: req.max_agents]

        if not selected_agents:
            raise HTTPException(status_code=400, detail="No enabled agents available")

        debate_trace = None
        all_aggregates: Optional[Dict[str, Any]] = None
        if req.strategy == "debate":
            if req.mock_mode:
                async def debate_query_fn(
                    agent: AgentConfig,
                    prompt: str,
                    temperature: float,
                    seed: int,
                    max_tokens: int,
                    stage: str,
                ) -> Dict[str, Any]:
                    return await self._query_mock_agent(agent, prompt, seed, stage)

                debate_trace = await self.debate_engine.run(
                    query=req.prompt,
                    agents=selected_agents,
                    query_fn=debate_query_fn,
                    temperature=req.temperature,
                    seed=req.seed,
                    max_tokens=req.max_tokens,
                )
            else:
                debate_timeout_s = min(self.request_timeout_s, 75.0)
                async with httpx.AsyncClient(timeout=debate_timeout_s) as debate_client:
                    async def debate_query_fn(
                        agent: AgentConfig,
                        prompt: str,
                        temperature: float,
                        seed: int,
                        max_tokens: int,
                        stage: str,
                    ) -> Dict[str, Any]:
                        return await self._query_real_agent(
                            debate_client,
                            agent,
                            prompt,
                            temperature,
                            seed,
                            max_tokens,
                        )

                    debate_trace = await self.debate_engine.run(
                        query=req.prompt,
                        agents=selected_agents,
                        query_fn=debate_query_fn,
                        temperature=req.temperature,
                        seed=req.seed,
                        max_tokens=req.max_tokens,
                    )

            round2_responses = debate_trace.get("round2") or []
            if round2_responses:
                agent_responses = round2_responses
            else:
                agent_responses = debate_trace.get("round1", [])
            aggregate = debate_trace["final"]
        else:
            agent_responses = await self.collect_agent_responses(
                prompt=req.prompt,
                agents=selected_agents,
                temperature=req.temperature,
                seed=req.seed,
                max_tokens=req.max_tokens,
                mock_mode=req.mock_mode,
            )
            if req.compute_all_direct:
                all_aggregates = {}
                for strategy_name in ("majority", "weighted", "isp"):
                    all_aggregates[strategy_name] = self.aggregator.aggregate(
                        strategy=strategy_name,
                        responses=agent_responses,
                        topic=topic,
                    ).to_dict()

                topic, topic_agents = self.router.route(req.prompt, selected_agents, None)
                topic_agent_ids = {agent.id for agent in topic_agents}
                topic_responses = [
                    response for response in agent_responses if response.get("agent_id") in topic_agent_ids
                ]
                if not topic_responses:
                    topic_responses = agent_responses
                all_aggregates["topic"] = self.aggregator.aggregate(
                    strategy="topic",
                    responses=topic_responses,
                    topic=topic,
                ).to_dict()
                aggregate = all_aggregates.get(req.strategy, all_aggregates["majority"])
            else:
                aggregate = self.aggregator.aggregate(
                    strategy=req.strategy,
                    responses=agent_responses,
                    topic=topic,
                ).to_dict()

        if req.ground_truth:
            self.aggregator.update_weights_from_ground_truth(agent_responses, req.ground_truth)

        total_latency_ms = round((time.perf_counter() - started) * 1000.0, 3)
        query_id = str(uuid.uuid4())
        resource_usage = get_resource_usage()

        result = {
            "query_id": query_id,
            "timestamp": now_utc_iso(),
            "strategy": req.strategy,
            "topic": topic,
            "aggregate": aggregate,
            "agent_responses": agent_responses,
            "weights": self.aggregator.weights,
            "total_latency_ms": total_latency_ms,
            "resource_usage": resource_usage,
            "metadata": req.metadata,
            "mock_mode": req.mock_mode,
        }
        if all_aggregates is not None:
            result["aggregates"] = all_aggregates
        if debate_trace is not None:
            result["debate"] = debate_trace

        log_payload = {
            "timestamp": result["timestamp"],
            "query_id": query_id,
            "independent_variables": {
                "strategy": req.strategy,
                "temperature": req.temperature,
                "deterministic": req.deterministic,
                "seed": req.seed,
                "max_agents": req.max_agents,
                "mock_mode": req.mock_mode,
            },
            "dependent_variables": {
                "aggregate_answer": aggregate.get("answer", ""),
                "agreement_rate": aggregate.get("agreement_rate", 0.0),
                "total_latency_ms": total_latency_ms,
                "resource_usage": resource_usage,
            },
            "ground_truth": req.ground_truth,
            "agent_responses": agent_responses,
        }
        append_jsonl(LOG_PATH, log_payload)
        return result

    async def health(self) -> Dict[str, Any]:
        statuses: List[Dict[str, Any]] = []
        async with httpx.AsyncClient(timeout=5.0) as client:
            for agent in self.enabled_agents:
                if agent.host == "mock":
                    statuses.append(
                        {
                            "agent_id": agent.id,
                            "model": agent.model,
                            "endpoint": f"http://{agent.host}:{agent.port}",
                            "healthy": True,
                        }
                    )
                    continue
                endpoint = f"http://{agent.host}:{agent.port}/api/tags"
                try:
                    response = await client.get(endpoint)
                    response.raise_for_status()
                    statuses.append(
                        {
                            "agent_id": agent.id,
                            "model": agent.model,
                            "endpoint": endpoint,
                            "healthy": True,
                        }
                    )
                except Exception as exc:
                    statuses.append(
                        {
                            "agent_id": agent.id,
                            "model": agent.model,
                            "endpoint": endpoint,
                            "healthy": False,
                            "error": str(exc),
                        }
                    )

        all_healthy = all(item["healthy"] for item in statuses) if statuses else False
        return {
            "status": "ok" if all_healthy else "degraded",
            "agent_count": len(statuses),
            "agents": statuses,
            "timestamp": now_utc_iso(),
        }


service = OrchestratorService(AGENT_CONFIG_PATH)
app = FastAPI(title="Distributed AI Orchestrator", version="1.0.0")


def _cors_origins() -> List[str]:
    default_origins = ",".join(
        [
            "https://anis151993.github.io",
            "http://localhost:8080",
            "http://127.0.0.1:8080",
        ]
    )
    raw = os.getenv("CORS_ALLOW_ORIGINS", default_origins)
    origins = [item.strip() for item in raw.split(",") if item.strip()]
    return origins or ["*"]


app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    max_age=600,
)


@app.get("/")
async def root() -> Dict[str, Any]:
    return {
        "name": "distributed-ai-orchestrator",
        "version": "1.0.0",
        "time": now_utc_iso(),
    }


@app.get("/health")
async def health() -> Dict[str, Any]:
    return await service.health()


@app.get("/agents")
async def agents() -> Dict[str, Any]:
    return {
        "agents": [
            {
                "id": agent.id,
                "host": agent.host,
                "port": agent.port,
                "model": agent.model,
                "enabled": agent.enabled,
                "topic_tags": agent.topic_tags,
            }
            for agent in service.agents
        ]
    }


@app.get("/weights")
async def weights() -> Dict[str, Any]:
    return {"weights": service.aggregator.weights}


@app.post("/reload-agents")
async def reload_agents() -> Dict[str, Any]:
    service.reload_agents()
    return {"status": "reloaded", "agent_count": len(service.agents)}


@app.post("/query")
async def query(req: QueryRequest) -> Dict[str, Any]:
    return await service.run_query(req)
