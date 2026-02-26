#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR=${1:-/opt/distributed_ai}
SERVICE_USER=${2:-$USER}

sudo cp "${PROJECT_DIR}/deploy/systemd/orchestrator.service" /etc/systemd/system/orchestrator.service
sudo cp "${PROJECT_DIR}/deploy/systemd/ollama-agent.service" /etc/systemd/system/ollama-agent.service

sudo sed -i "s|__PROJECT_DIR__|${PROJECT_DIR}|g" /etc/systemd/system/orchestrator.service
sudo sed -i "s|__SERVICE_USER__|${SERVICE_USER}|g" /etc/systemd/system/orchestrator.service
sudo sed -i "s|__PROJECT_DIR__|${PROJECT_DIR}|g" /etc/systemd/system/ollama-agent.service
sudo sed -i "s|__SERVICE_USER__|${SERVICE_USER}|g" /etc/systemd/system/ollama-agent.service

sudo systemctl daemon-reload
sudo systemctl enable orchestrator.service
sudo systemctl enable ollama-agent.service

echo "Installed services. Start with:"
echo "  sudo systemctl start ollama-agent orchestrator"
