#!/usr/bin/env bash
set -euo pipefail
MODEL_ROOT=/home/ubuntu/models/minimax-h3
for model in \
  diffusion_models/minimax_h3_fl2va_pruned_int8_convrot.safetensors \
  diffusion_models/minimax_h3_ref2va_pruned_int8_convrot.safetensors \
  text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors \
  vae/minimax_h3_video_vae_fp16.safetensors \
  vae/minimax_h3_audio_vae_fp32.safetensors; do
  test -s "$MODEL_ROOT/$model" || {
    echo "Missing model: $MODEL_ROOT/$model" >&2
    exit 1
  }
done
curl --fail --silent --show-error http://127.0.0.1:8188/system_stats >/dev/null
curl --fail --silent --show-error http://127.0.0.1:8000/api/v1/health
curl --fail --silent --show-error http://127.0.0.1/login >/dev/null
echo
echo "All local health checks passed."

