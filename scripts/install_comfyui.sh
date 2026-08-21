#!/usr/bin/env bash
set -euo pipefail
COMFY_DIR=/home/ubuntu/ComfyUI
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ ! -d "$COMFY_DIR/.git" ]]; then
  git clone https://github.com/Comfy-Org/ComfyUI.git "$COMFY_DIR"
fi
uv venv "$COMFY_DIR/.venv" --python 3.12
uv pip install --python "$COMFY_DIR/.venv/bin/python" torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu130
uv pip install --python "$COMFY_DIR/.venv/bin/python" -r "$COMFY_DIR/requirements.txt"
H3_UPSCALE_NODE_SOURCE="$PROJECT_DIR/comfyui_custom_nodes/h3_latent_upscale"
H3_UPSCALE_NODE_TARGET="$COMFY_DIR/custom_nodes/h3_latent_upscale"
if [[ -L "$H3_UPSCALE_NODE_TARGET" ]]; then
  ln -sfn "$H3_UPSCALE_NODE_SOURCE" "$H3_UPSCALE_NODE_TARGET"
elif [[ -e "$H3_UPSCALE_NODE_TARGET" ]]; then
  echo "Refusing to replace existing ComfyUI node: $H3_UPSCALE_NODE_TARGET" >&2
  exit 1
else
  ln -s "$H3_UPSCALE_NODE_SOURCE" "$H3_UPSCALE_NODE_TARGET"
fi
echo "ComfyUI installed at $COMFY_DIR"

