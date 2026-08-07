#!/usr/bin/env python3
"""Upload one reference image and run a real MiniMax H3 Ref2VA INT8 workflow."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from comfyui_test_client import ComfyUITestClient, load_workflow, output_files


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    parser.add_argument("--base-url", default="http://127.0.0.1:8188")
    parser.add_argument("--workflow", type=Path, default=PROJECT_ROOT / "workflows" / "h3_ref2va_int8.json")
    parser.add_argument("--timeout", type=float, default=1_800)
    parser.add_argument("--seed", type=int, default=20260831)
    parser.add_argument(
        "--prompt",
        default=(
            "Use <Picture 1> as the exact visual reference. Preserve the subject, identity, "
            "style, lighting and palette. Create one continuous cinematic shot with natural "
            "motion and matching native audio. No text, no logo."
        ),
    )
    args = parser.parse_args()
    if not args.image.is_file():
        raise SystemExit(f"Input image does not exist: {args.image}")

    client = ComfyUITestClient(args.base_url, timeout_seconds=args.timeout)
    stats = client.health_check()
    uploaded_name = client.upload_image(args.image)
    workflow = load_workflow(args.workflow)
    workflow["15"]["inputs"]["image"] = uploaded_name
    workflow["5"]["inputs"]["prompt"] = args.prompt
    workflow["6"]["inputs"]["noise_seed"] = args.seed
    workflow["14"]["inputs"]["filename_prefix"] = "video/Phase8_H3_REF2VA_API"

    prompt_id = client.submit_workflow(workflow)
    print(f"uploaded={uploaded_name} submitted prompt_id={prompt_id}", flush=True)
    history = client.wait_for_completion(prompt_id)
    print(json.dumps({
        "prompt_id": prompt_id,
        "status": history["status"]["status_str"],
        "uploaded_image": uploaded_name,
        "outputs": output_files(history),
        "comfyui_version": stats["system"]["comfyui_version"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

