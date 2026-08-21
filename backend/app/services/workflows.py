from __future__ import annotations

import copy
import json
import math
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

TURBO_LORA_NAME = "minimax_h3_turbo_v4_step600_ema.safetensors"
GENERATION_PROFILES = {
    "turbo": {"steps": 8, "accelerated": True},
    "fast": {"steps": 6, "accelerated": True},
    "quality": {"steps": 20, "accelerated": False},
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
    ("16:9", "1080p"): (1376, 768),
    ("9:16", "1080p"): (768, 1376),
    ("1:1", "1080p"): (768, 768),
    ("4:3", "1080p"): (1024, 768),
    ("3:4", "1080p"): (768, 1024),
}

H3_1080P_OUTPUT_DIMENSIONS = {
    "16:9": (1920, 1080),
    "9:16": (1080, 1920),
    "1:1": (1080, 1080),
    "4:3": (1440, 1080),
    "3:4": (1080, 1440),
}
H3_1080P_TOTAL_STEPS = 8
H3_1080P_FIRST_PASS_STEPS = 2


class WorkflowService:
    version = "comfy-template-0.11.31-turbo.1080p.1"

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or get_settings().workflow_root

    @staticmethod
    def workflow_name_for(mode: str, resolution: str) -> str:
        if resolution == "1080p":
            return f"h3_{mode}_1080p_latent_upscale_int8.json"
        return f"h3_{mode}_int8.json"

    @staticmethod
    def _round_up_to_canvas_multiple(value: int) -> int:
        return int(math.ceil(value / 32) * 32)

    def _1080p_dimensions(self, aspect_ratio: str) -> tuple[tuple[int, int], tuple[int, int], tuple[int, int]]:
        """Return (first-pass canvas, model canvas, exact encoded output)."""
        output = H3_1080P_OUTPUT_DIMENSIONS[aspect_ratio]
        short_edge = min(output)
        initial = tuple(max(32, round(axis * 768 / short_edge / 32) * 32) for axis in output)
        model_canvas = tuple(self._round_up_to_canvas_multiple(axis) for axis in output)
        return initial, model_canvas, output

    @staticmethod
    def _configure_1080p_workflow(
        workflow: dict[str, Any], *, model_width: int, model_height: int,
        output_width: int, output_height: int,
    ) -> None:
        """Add H3's two-pass video-only latent upscale graph to a base template."""
        workflow["8"]["inputs"]["steps"] = H3_1080P_TOTAL_STEPS
        workflow["10"]["inputs"]["sigmas"] = ["20", 0]
        workflow.update(
            {
                "20": {
                    "class_type": "SplitSigmas",
                    "inputs": {"sigmas": ["8", 0], "step": H3_1080P_FIRST_PASS_STEPS},
                    "_meta": {"title": "Split H3 Turbo sigmas after first pass"},
                },
                "22": {
                    "class_type": "MiniMaxH3VideoLatentUpscaleReNoise",
                    "inputs": {
                        "samples": ["10", 0], "model": ["900", 0], "noise": ["6", 0],
                        "sigmas": ["20", 1], "width": model_width, "height": model_height,
                        "upscale_method": "bicubic",
                    },
                    "_meta": {"title": "Upscale H3 video latent and re-noise video only"},
                },
                "24": {
                    "class_type": "DisableNoise",
                    "inputs": {},
                    "_meta": {"title": "Continue from split sigma without new noise"},
                },
                "25": {
                    "class_type": "SamplerCustomAdvanced",
                    "inputs": {
                        "noise": ["24", 0], "guider": ["9", 0], "sampler": ["7", 0],
                        "sigmas": ["20", 1], "latent_image": ["22", 0],
                    },
                    "_meta": {"title": "H3 second-pass detail sampling"},
                },
                "26": {
                    "class_type": "ImageCrop",
                    "inputs": {
                        "image": ["11", 0], "width": output_width, "height": output_height,
                        "x": (model_width - output_width) // 2,
                        "y": (model_height - output_height) // 2,
                    },
                    "_meta": {"title": "Crop model canvas to exact 1080p output"},
                },
                "27": {
                    "class_type": workflow["5"]["class_type"],
                    "inputs": copy.deepcopy(workflow["5"]["inputs"]),
                    "_meta": {"title": "MiniMax H3 target-resolution conditioning for second pass"},
                },
                "28": {
                    "class_type": "BasicGuider",
                    "inputs": {"model": ["900", 0], "conditioning": ["27", 0]},
                    "_meta": {"title": "H3 second-pass target-resolution guider"},
                },
            }
        )
        workflow["27"]["inputs"]["width"] = model_width
        workflow["27"]["inputs"]["height"] = model_height
        workflow["11"]["inputs"]["samples"] = ["25", 0]
        workflow["12"]["inputs"]["samples"] = ["25", 0]
        workflow["13"]["inputs"]["images"] = ["26", 0]
        workflow["25"]["inputs"]["guider"] = ["28", 0]

    def build(
        self,
        job: VideoJob,
        comfy_assets: list[tuple[str, str]] | None = None,
    ) -> dict[str, Any]:
        if job.mode not in WORKFLOW_NODE_MAP:
            raise ValueError(f"Unsupported workflow mode: {job.mode}")
        expected_name = self.workflow_name_for(job.mode, job.resolution)
        if job.workflow_name != expected_name:
            raise ValueError(f"Unexpected workflow name: {job.workflow_name}")
        template_path = self.root / f"h3_{job.mode}_int8.json"
        with template_path.open("r", encoding="utf-8") as handle:
            workflow = copy.deepcopy(json.load(handle))
        node_map = WORKFLOW_NODE_MAP[job.mode]
        for node_id in node_map.values():
            if node_id not in workflow:
                raise ValueError(f"Workflow node {node_id} is missing")

        condition = workflow[node_map["condition"]]["inputs"]
        profile = GENERATION_PROFILES.get(job.generation_profile)
        if profile is None:
            raise ValueError(f"Unsupported generation profile: {job.generation_profile}")
        expected_steps = int(profile["steps"])
        if job.steps != expected_steps:
            raise ValueError(
                f"Generation profile {job.generation_profile} requires {expected_steps} steps"
            )
        if job.resolution == "1080p" and job.generation_profile != "turbo":
            raise ValueError("1080p requires the fixed Turbo 8-step profile")


        if profile["accelerated"]:
            workflow["900"] = {
                "class_type": "MiniMaxH3TurboLoRA",
                "inputs": {
                    "model": ["1", 0],
                    "lora_name": TURBO_LORA_NAME,
                    "strength": 1.0,
                    "low_vram": False,
                },
                "_meta": {"title": "MiniMax H3 Turbo LoRA"},
            }
            workflow["7"] = {
                "class_type": "MiniMaxH3TurboSampler",
                "inputs": {},
                "_meta": {"title": "MiniMax H3 Turbo Sampler"},
            }
            workflow["8"]["inputs"]["model"] = ["900", 0]
            workflow["9"]["inputs"]["model"] = ["900", 0]
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
        workflow[node_map["scheduler"]]["inputs"]["steps"] = expected_steps
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
        if job.resolution == "1080p":
            _, (model_width, model_height), (output_width, output_height) = self._1080p_dimensions(job.aspect_ratio)
            self._configure_1080p_workflow(
                workflow, model_width=model_width, model_height=model_height,
                output_width=output_width, output_height=output_height,
            )
        return workflow
