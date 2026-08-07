#!/usr/bin/env bash
set -euo pipefail
sudo systemctl start h3-comfyui h3-backend h3-worker h3-frontend nginx
sudo systemctl --no-pager --full status h3-comfyui h3-backend h3-worker h3-frontend nginx

