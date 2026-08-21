from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.models.video_job import VideoJob
from app.schemas.video_job import VideoJobCreate
from app.services.workflows import WorkflowService


WORKFLOW_ROOT = Path(__file__).resolve().parents[2] / "workflows"


def make_job(mode: str, profile: str = "quality") -> VideoJob:
    steps = {"turbo": 8, "fast": 6, "quality": 20}[profile]
    return VideoJob(
        user_id="user-id",
        mode=mode,
        prompt="A calm cinematic lake",
        duration_seconds=5,
        aspect_ratio="16:9",
        resolution="480p",
        generation_profile=profile,
        seed=42,
        steps=steps,
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


@pytest.mark.parametrize(("profile", "steps"), [("turbo", 8), ("fast", 6)])
@pytest.mark.parametrize("mode", ["t2v", "i2v", "ref2va"])
def test_build_turbo_profiles(mode: str, profile: str, steps: int):
    comfy_assets = {
        "t2v": [],
        "i2v": [("image", "first.png")],
        "ref2va": [("image", "person.png")],
    }[mode]

    workflow = WorkflowService(root=WORKFLOW_ROOT).build(
        make_job(mode, profile), comfy_assets
    )

    assert workflow["900"] == {
        "class_type": "MiniMaxH3TurboLoRA",
        "inputs": {
            "model": ["1", 0],
            "lora_name": "minimax_h3_turbo_v4_step600_ema.safetensors",
            "strength": 1.0,
            "low_vram": False,
        },
        "_meta": {"title": "MiniMax H3 Turbo LoRA"},
    }
    assert workflow["7"]["class_type"] == "MiniMaxH3TurboSampler"
    assert workflow["8"]["inputs"]["model"] == ["900", 0]
    assert workflow["8"]["inputs"]["steps"] == steps
    assert workflow["9"]["inputs"]["model"] == ["900", 0]


def test_quality_profile_does_not_load_turbo_lora():
    workflow = WorkflowService(root=WORKFLOW_ROOT).build(make_job("t2v"))

    assert "900" not in workflow
    assert workflow["7"]["inputs"]["sampler_name"] == "res_multistep"
    assert workflow["8"]["inputs"]["model"] == ["1", 0]
    assert workflow["8"]["inputs"]["steps"] == 20


@pytest.mark.parametrize("mode", ["t2v", "i2v", "ref2va"])
def test_1080p_uses_target_renoise_and_target_conditioning(mode: str):
    job = make_job(mode, "turbo")
    job.resolution = "1080p"
    job.workflow_name = f"h3_{mode}_1080p_latent_upscale_int8.json"
    assets = {
        "t2v": [],
        "i2v": [("image", "first.png"), ("image", "last.png")],
        "ref2va": [("image", "person.png"), ("video", "motion.mp4")],
    }[mode]

    workflow = WorkflowService(root=WORKFLOW_ROOT).build(job, assets)

    assert workflow["20"]["inputs"]["step"] == 2
    assert workflow["8"]["inputs"]["scheduler"] == "beta"
    assert workflow["8"]["inputs"]["steps"] == 8
    assert workflow["22"]["class_type"] == "MiniMaxH3VideoLatentUpscaleContinuation"
    assert workflow["22"]["inputs"]["samples"] == ["10", 0]
    assert "noise" not in workflow["22"]["inputs"]
    assert "model" not in workflow["22"]["inputs"]
    assert "sigmas" not in workflow["22"]["inputs"]
    assert workflow["22"]["inputs"]["upscale_method"] == "bislerp"
    assert workflow["25"]["inputs"]["noise"] == ["24", 0]
    assert workflow["25"]["inputs"]["guider"] == ["28", 0]
    assert workflow["27"]["inputs"]["width"] == 1920
    assert workflow["27"]["inputs"]["height"] == 1088
    assert workflow["27"]["inputs"]["length"] == workflow["5"]["inputs"]["length"]
    assert workflow["28"]["inputs"] == {"model": ["900", 0], "conditioning": ["27", 0]}
    assert workflow["13"]["inputs"]["images"] == ["26", 0]


def test_profile_rejects_mismatched_steps():
    job = make_job("t2v", "turbo")
    job.steps = 20

    with pytest.raises(ValueError, match="requires 8 steps"):
        WorkflowService(root=WORKFLOW_ROOT).build(job)


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


@pytest.mark.parametrize(
    ("duration_seconds", "expected_frames"),
    [(1, 39), (5, 124), (8, 192), (10, 243), (15, 362)],
)
def test_duration_uses_h3_frame_grid(duration_seconds: int, expected_frames: int):
    job = make_job("t2v")
    job.duration_seconds = duration_seconds

    workflow = WorkflowService(root=WORKFLOW_ROOT).build(job)

    frames = workflow["5"]["inputs"]["length"]
    assert frames == expected_frames
    assert (frames - 5) % 17 == 0


@pytest.mark.parametrize("duration_seconds", [1, 15])
def test_duration_accepts_one_through_fifteen_seconds(duration_seconds: int):
    payload = VideoJobCreate(mode="t2v", prompt="A calm lake", duration_seconds=duration_seconds)
    assert payload.duration_seconds == duration_seconds


@pytest.mark.parametrize("duration_seconds", [0, 16])
def test_duration_rejects_values_outside_supported_range(duration_seconds: int):
    with pytest.raises(ValidationError, match="时长必须在 1～15 秒之间"):
        VideoJobCreate(mode="t2v", prompt="A calm lake", duration_seconds=duration_seconds)
