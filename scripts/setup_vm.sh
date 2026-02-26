#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR=${1:-/opt/distributed_ai}

echo "Updating Ubuntu packages"
sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-pip git curl jq build-essential

echo "Creating project directory: ${PROJECT_DIR}"
sudo mkdir -p "${PROJECT_DIR}"
sudo chown -R "$USER":"$USER" "${PROJECT_DIR}"

echo "Copy project files into ${PROJECT_DIR} before continuing if needed"
cd "${PROJECT_DIR}"

if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "VM setup complete"
