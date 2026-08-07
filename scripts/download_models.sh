#!/usr/bin/env bash
set -euo pipefail
MODEL_ROOT=/home/ubuntu/models/minimax-h3
REVISION=eb8a16107c595128b3a578f82d2ce2f75920c355
HF=/home/ubuntu/ComfyUI/.venv/bin/hf
mkdir -p "$MODEL_ROOT/diffusion_models" "$MODEL_ROOT/text_encoders" "$MODEL_ROOT/vae"
"$HF" download Comfy-Org/MiniMax-H3 diffusion_models/minimax_h3_fl2va_pruned_int8_convrot.safetensors diffusion_models/minimax_h3_ref2va_pruned_int8_convrot.safetensors text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors vae/minimax_h3_video_vae_fp16.safetensors vae/minimax_h3_audio_vae_fp32.safetensors --revision "$REVISION" --local-dir "$MODEL_ROOT"
echo "Models downloaded at pinned revision $REVISION"



