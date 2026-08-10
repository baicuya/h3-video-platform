from __future__ import annotations

from pathlib import Path

import pytest

from app.models.video_job import VideoJob
from app.services.workflows import WorkflowService


WORKFLOW_ROOT = Path(__file__).resolve().parents[2] / "workflows"


@pytest.mark.parametrize("mode", ["t2v", "i2v", "ref2va"])
def test_build_supported_int8_workflows(mode: str):
    job = VideoJob(
        user_id="user-id",
        mode=mode,
        prompt="A calm cinematic lake",
        duration_seconds=5,
        aspect_ratio="16:9",
        resolution="480p",
        seed=42,
        steps=20,
        input_assets=[],
        workflow_name=f"h3_{mode}_int8.json",
    )

    workflow = WorkflowService(root=WORKFLOW_ROOT).build(
        job,
        comfy_image_name="input.png" if mode != "t2v" else None,
    )

    unet_name = workflow["1"]["inputs"]["unet_name"]
    assert "_int8_convrot.safetensors" in unet_name
    assert workflow["2"]["inputs"]["clip_name"].endswith("_nvfp4_awq.safetensors")


def test_rejects_unexpected_workflow_name():
    job = VideoJob(
        user_id="user-id",
        mode="t2v",
        prompt="unsafe",
        duration_seconds=5,
        aspect_ratio="16:9",
        resolution="480p",
        seed=42,
        steps=20,
        input_assets=[],
        workflow_name="h3_t2v_bf16.json",
    )

    with pytest.raises(ValueError, match="Unexpected workflow name"):
        WorkflowService(root=WORKFLOW_ROOT).build(job)
