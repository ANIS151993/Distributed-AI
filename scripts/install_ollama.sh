#!/usr/bin/env bash
set -euo pipefail

MODELS=("$@")
if [ ${#MODELS[@]} -eq 0 ]; then
  MODELS=("llama3:8b" "mistral:7b" "phi3:mini")
fi

if [ "$(id -u)" -eq 0 ]; then
  SUDO=""
else
  SUDO="sudo"
fi

echo "[1/4] Installing Ollama"
curl -fsSL https://ollama.com/install.sh | sh

echo "[2/4] Configuring Ollama for LAN access on port 11434"
${SUDO} mkdir -p /etc/systemd/system/ollama.service.d
cat <<'OVERRIDE' | ${SUDO} tee /etc/systemd/system/ollama.service.d/override.conf >/dev/null
[Service]
Environment="OLLAMA_HOST=0.0.0.0:11434"
Environment="OLLAMA_KEEP_ALIVE=30m"
OVERRIDE

echo "[3/4] Enabling service"
${SUDO} systemctl daemon-reload
${SUDO} systemctl enable --now ollama
sleep 2

echo "[4/4] Pulling models"
for model in "${MODELS[@]}"; do
  echo "Pulling ${model}"
  ollama pull "$model"
done

echo "Done. Verify with: curl http://127.0.0.1:11434/api/tags"
