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
    },
    "ref2va": {
        "condition": "5",
        "noise": "6",
        "scheduler": "8",
        "save_video": "14",
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
    version = "comfy-template-0.11.31-ref2va.2"

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or get_settings().workflow_root

    def build(
        self,
        job: VideoJob,
        comfy_assets: list[tuple[str, str]] | None = None,
    ) -> dict[str, Any]:
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
        assets = comfy_assets or []
        if job.mode == "i2v":
            images = [name for kind, name in assets if kind == "image"]
            if len(images) not in {1, 2} or len(images) != len(assets):
                raise ValueError(
                    "i2v requires one first-frame image and optionally one last-frame image"
                )
            for index, name in enumerate(images):
                node_id = str(15 + index)
                label = "First frame" if index == 0 else "Last frame"
                workflow[node_id] = {
                    "class_type": "LoadImage",
                    "inputs": {"image": name},
                    "_meta": {"title": label},
                }
                condition["first_frame" if index == 0 else "last_frame"] = [node_id, 0]
        elif job.mode == "ref2va":
            if not assets:
                raise ValueError("ref2va requires uploaded ComfyUI reference assets")
            workflow.pop("15", None)
            for key in tuple(condition):
                if key.startswith(
                    ("ref_images.", "ref_videos.", "ref_video_audios.", "ref_audios.")
                ):
                    del condition[key]

            grouped = {
                kind: [name for asset_kind, name in assets if asset_kind == kind]
                for kind in ("image", "video", "audio")
            }
            if sum(len(names) for names in grouped.values()) != len(assets):
                raise ValueError("ref2va received an unsupported asset type")

            next_node = 15
            for index, name in enumerate(grouped["image"]):
                node_id = str(next_node)
                next_node += 1
                workflow[node_id] = {
                    "class_type": "LoadImage",
                    "inputs": {"image": name},
                    "_meta": {"title": f"Reference image {index + 1}"},
                }
                condition[f"ref_images.ref_image_{index}"] = [node_id, 0]

            for index, name in enumerate(grouped["video"]):
                load_node = str(next_node)
                components_node = str(next_node + 1)
                next_node += 2
                workflow[load_node] = {
                    "class_type": "LoadVideo",
                    "inputs": {"file": name},
                    "_meta": {"title": f"Reference video {index + 1}"},
                }
                workflow[components_node] = {
                    "class_type": "GetVideoComponents",
                    "inputs": {"video": [load_node, 0]},
                    "_meta": {"title": f"Reference video {index + 1} components"},
                }
                condition[f"ref_videos.ref_video_{index}"] = [components_node, 0]

            for index, name in enumerate(grouped["audio"]):
                node_id = str(next_node)
                next_node += 1
                workflow[node_id] = {
                    "class_type": "LoadAudio",
                    "inputs": {"audio": name},
                    "_meta": {"title": f"Reference audio {index + 1}"},
                }
                condition[f"ref_audios.ref_audio_{index}"] = [node_id, 0]
        return workflow
