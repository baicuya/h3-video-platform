#!/usr/bin/env bash
set -euo pipefail
COMFY_DIR=/home/ubuntu/ComfyUI
if [[ ! -d "$COMFY_DIR/.git" ]]; then
  git clone https://github.com/Comfy-Org/ComfyUI.git "$COMFY_DIR"
fi
uv venv "$COMFY_DIR/.venv" --python 3.12
uv pip install --python "$COMFY_DIR/.venv/bin/python" torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu130
uv pip install --python "$COMFY_DIR/.venv/bin/python" -r "$COMFY_DIR/requirements.txt"
echo "ComfyUI installed at $COMFY_DIR"

