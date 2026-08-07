#!/usr/bin/env python3
"""Submit and wait for a real MiniMax H3 INT8 text-to-video workflow."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from comfyui_test_client import ComfyUITestClient, load_workflow, output_files


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8188")
    parser.add_argument(
        "--workflow",
        type=Path,
        default=PROJECT_ROOT / "workflows" / "h3_t2v_int8.json",
    )
    parser.add_argument("--timeout", type=float, default=1_800)
    parser.add_argument("--seed", type=int, default=20260809)
    parser.add_argument(
        "--prompt",
        default=(
            "A cinematic close view of wild grass moving in a gentle morning breeze, "
            "warm sunlight and shallow depth of field, slow camera movement, no text, "
            "no logo. Audio: soft wind and distant birds."
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    client = ComfyUITestClient(args.base_url, timeout_seconds=args.timeout)
    stats = client.health_check()
    workflow = load_workflow(args.workflow)
    workflow["5"]["inputs"]["prompt"] = args.prompt
    workflow["6"]["inputs"]["noise_seed"] = args.seed
    workflow["14"]["inputs"]["filename_prefix"] = "video/Phase4_H3_T2V_API"

    prompt_id = client.submit_workflow(workflow)
    print(f"submitted prompt_id={prompt_id}", flush=True)
    history = client.wait_for_completion(prompt_id)
    result = {
        "prompt_id": prompt_id,
        "status": history["status"]["status_str"],
        "outputs": output_files(history),
        "comfyui_version": stats["system"]["comfyui_version"],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
