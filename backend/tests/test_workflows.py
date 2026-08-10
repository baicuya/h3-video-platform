from __future__ import annotations

from pathlib import Path

import pytest

from app.models.video_job import VideoJob
from app.services.workflows import WorkflowService


WORKFLOW_ROOT = Path(__file__).resolve().parents[2] / "workflows"


def make_job(mode: str) -> VideoJob:
    return VideoJob(
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


@pytest.mark.parametrize("mode", ["t2v", "i2v", "ref2va"])
def test_build_supported_int8_workflows(mode: str):
    comfy_assets = {
        "t2v": [],
        "i2v": [("image", "first.png"), ("image", "last.png")],
        "ref2va": [
            ("image", "person.png"),
            ("video", "motion.mp4"),
            ("audio", "voice.wav"),
        ],
    }[mode]

    workflow = WorkflowService(root=WORKFLOW_ROOT).build(make_job(mode), comfy_assets)

    unet_name = workflow["1"]["inputs"]["unet_name"]
    assert "_int8_convrot.safetensors" in unet_name
    assert workflow["2"]["inputs"]["clip_name"].endswith("_nvfp4_awq.safetensors")

    condition = workflow["5"]["inputs"]
    if mode == "i2v":
        assert condition["first_frame"] == ["15", 0]
        assert condition["last_frame"] == ["16", 0]
        assert workflow["15"]["inputs"]["image"] == "first.png"
        assert workflow["16"]["inputs"]["image"] == "last.png"
    elif mode == "ref2va":
        assert workflow["15"]["class_type"] == "LoadImage"
        assert workflow["16"]["class_type"] == "LoadVideo"
        assert workflow["17"]["class_type"] == "GetVideoComponents"
        assert workflow["18"]["class_type"] == "LoadAudio"
        assert condition["ref_images.ref_image_0"] == ["15", 0]
        assert condition["ref_videos.ref_video_0"] == ["17", 0]
        assert not any(key.startswith("ref_video_audios.") for key in condition)
        assert condition["ref_audios.ref_audio_0"] == ["18", 0]


def test_rejects_invalid_asset_shape():
    service = WorkflowService(root=WORKFLOW_ROOT)
    with pytest.raises(ValueError, match="i2v requires"):
        service.build(make_job("i2v"), [("video", "not-an-image.mp4")])
    with pytest.raises(ValueError, match="ref2va requires"):
        service.build(make_job("ref2va"), [])


def test_rejects_unexpected_workflow_name():
    job = make_job("t2v")
    job.workflow_name = "h3_t2v_bf16.json"

    with pytest.raises(ValueError, match="Unexpected workflow name"):
        WorkflowService(root=WORKFLOW_ROOT).build(job)
