#!/usr/bin/env bash
set -euo pipefail

ORCH_URL=${1:-http://127.0.0.1:8000}

echo "Orchestrator health:"
curl -s "${ORCH_URL}/health" | jq .

echo "Loaded agents:"
curl -s "${ORCH_URL}/agents" | jq .

