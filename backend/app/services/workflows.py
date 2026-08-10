from __future__ import annotations

import copy
import json
import secrets
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.models.video_job import VideoJob


WORKFLOW_NODE_MAP = {
    "t2v": {
        "condition": "5",
        "noise": "6",
        "scheduler": "8",
        "save_video": "14",
    },
    "i2v": {
        "condition": "5",
        "noise": "6",
        "scheduler": "8",
        "save_video": "14",
        "load_image": "15",
    },
    "ref2va": {
        "condition": "5",
        "noise": "6",
        "scheduler": "8",
        "save_video": "14",
        "load_image": "15",
    },
}

ASPECT_DIMENSIONS = {
    ("16:9", "480p"): (864, 480),
    ("16:9", "720p"): (1280, 736),
    ("16:9", "768p"): (1344, 768),
    ("9:16", "480p"): (480, 864),
    ("9:16", "720p"): (736, 1280),
    ("9:16", "768p"): (768, 1344),
    ("1:1", "480p"): (480, 480),
    ("1:1", "720p"): (704, 704),
    ("1:1", "768p"): (768, 768),
    ("4:3", "480p"): (640, 480),
    ("3:4", "480p"): (480, 640),
}


class WorkflowService:
    version = "comfy-template-0.11.31"

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or get_settings().workflow_root

    def build(self, job: VideoJob, comfy_image_name: str | None = None) -> dict[str, Any]:
        if job.mode not in WORKFLOW_NODE_MAP:
            raise ValueError(f"Unsupported workflow mode: {job.mode}")
        expected_name = f"h3_{job.mode}_int8.json"
        if job.workflow_name != expected_name:
            raise ValueError(f"Unexpected workflow name: {job.workflow_name}")
        template_path = self.root / expected_name
        with template_path.open("r", encoding="utf-8") as handle:
            workflow = copy.deepcopy(json.load(handle))
        node_map = WORKFLOW_NODE_MAP[job.mode]
        for node_id in node_map.values():
            if node_id not in workflow:
                raise ValueError(f"Workflow node {node_id} is missing")

        condition = workflow[node_map["condition"]]["inputs"]
        width, height = ASPECT_DIMENSIONS.get(
            (job.aspect_ratio, job.resolution),
            ASPECT_DIMENSIONS.get((job.aspect_ratio, "480p"), (864, 480)),
        )
        frames = max(5, round(job.duration_seconds * 24))
        frames += (5 - frames % 17) % 17
        condition.update(
            {
                "prompt": job.prompt,
                "width": width,
                "height": height,
                "length": frames,
            }
        )
        seed = job.seed if job.seed >= 0 else secrets.randbits(63)
        workflow[node_map["noise"]]["inputs"]["noise_seed"] = seed
        workflow[node_map["scheduler"]]["inputs"]["steps"] = job.steps
        workflow[node_map["save_video"]]["inputs"][
            "filename_prefix"
        ] = f"video/jobs/{job.id}"
        if job.mode in {"i2v", "ref2va"}:
            if not comfy_image_name:
                raise ValueError(f"{job.mode} requires an uploaded ComfyUI image name")
            workflow[node_map["load_image"]]["inputs"]["image"] = comfy_image_name
        return workflow
