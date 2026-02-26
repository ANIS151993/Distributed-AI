#!/usr/bin/env bash
set -euo pipefail

AGENT1_URL=${AGENT1_URL:-http://127.0.0.1:11435}
AGENT2_URL=${AGENT2_URL:-http://127.0.0.1:11436}
AGENT3_URL=${AGENT3_URL:-http://127.0.0.1:11437}
AGENT4_URL=${AGENT4_URL:-http://127.0.0.1:11438}

MODEL1=${MODEL1:-llama3.2:3b}
MODEL2=${MODEL2:-qwen2.5:3b}
MODEL3=${MODEL3:-phi3:mini}
MODEL4=${MODEL4:-gemma2:2b}

wait_for_agent() {
  local url="$1"
  local retries=60
  local delay=2

  for _ in $(seq 1 "$retries"); do
    if curl -fsS "${url}/api/tags" >/dev/null 2>&1; then
      return 0
    fi
    sleep "$delay"
  done
  echo "Agent not ready: ${url}" >&2
  return 1
}

pull_model() {
  local url="$1"
  local model="$2"
  echo "Pulling ${model} on ${url}"
  curl -fsS -X POST "${url}/api/pull" \
    -H 'Content-Type: application/json' \
    -d "{\"model\":\"${model}\",\"stream\":false}" >/tmp/pull_$(echo "$model" | tr ':/' '__').json
}

wait_for_agent "$AGENT1_URL"
wait_for_agent "$AGENT2_URL"
wait_for_agent "$AGENT3_URL"
wait_for_agent "$AGENT4_URL"

pull_model "$AGENT1_URL" "$MODEL1"
pull_model "$AGENT2_URL" "$MODEL2"
pull_model "$AGENT3_URL" "$MODEL3"
pull_model "$AGENT4_URL" "$MODEL4"

echo "Model pulls completed."
