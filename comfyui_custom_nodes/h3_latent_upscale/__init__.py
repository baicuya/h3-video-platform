"""MiniMax H3 helpers for two-pass 1080p sampling.

H3 stores video and audio in a single nested latent. Generic ComfyUI latent
upscalers assume an image VAE with an 8x spatial compression, while H3 video
uses 16x.  ``SamplerCustomAdvanced`` already emits a flow-aligned latent at
the end of the first pass.  The continuation node below spatially interpolates
only its video stream; the second sampler performs the one required flow-scale
restore through ``DisableNoise``.  Adding either another inverse scale or new
noise at the near-1.0 split sigma causes severe artefacts.
"""

from __future__ import annotations

import torch
import torch.nn.functional as F

import comfy.utils
from comfy.nested_tensor import NestedTensor


def _plain_latent(latent: dict, samples):
    """Copy latent metadata without sharing the ``samples`` value."""
    result = latent.copy()
    result["samples"] = samples
    return result


def _upscale_video(video: torch.Tensor, width: int, height: int, method: str) -> torch.Tensor:
    """Resize H3 video [B, C, T, H/16, W/16] per-frame at fp32 precision."""
    if getattr(video, "is_nested", False) or video.ndim != 5:
        raise ValueError("MiniMax H3 video upscale requires a separated 5-D video latent")
    if width % 32 or height % 32:
        raise ValueError("MiniMax H3 target canvas must use 32-pixel multiples")

    batch, channels, frames, _, _ = video.shape
    target_size = (height // 16, width // 16)
    frame_batch = video.permute(0, 2, 1, 3, 4).reshape(
        -1, channels, video.shape[-2], video.shape[-1]
    )
    if method == "bislerp":
        upscaled = comfy.utils.common_upscale(
            frame_batch.float(), target_size[1], target_size[0], method, "disabled"
        ).to(dtype=video.dtype)
    else:
        upscaled = F.interpolate(
            frame_batch.float(), size=target_size, mode=method, align_corners=False
        ).to(dtype=video.dtype)
    return upscaled.reshape(batch, frames, channels, *target_size).permute(0, 2, 1, 3, 4)


class MiniMaxH3SplitAVLatent:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"samples": ("LATENT",)}}

    RETURN_TYPES = ("LATENT", "LATENT")
    RETURN_NAMES = ("video", "audio")
    FUNCTION = "split"
    CATEGORY = "model/latent/minimax"

    def split(self, samples):
        packed = samples["samples"]
        if not getattr(packed, "is_nested", False):
            raise ValueError("MiniMax H3 split requires a joint video+audio latent")
        video, audio = packed.unbind()
        if video.ndim != 5 or audio.ndim != 4:
            raise ValueError("MiniMax H3 latent has an unexpected video/audio shape")
        return (_plain_latent(samples, video), _plain_latent(samples, audio))


class MiniMaxH3VideoLatentUpscale:
    """Resize H3 video [B, C, T, H/16, W/16] to a target pixel canvas."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "samples": ("LATENT",),
                "width": ("INT", {"default": 1920, "min": 32, "max": 16384, "step": 32}),
                "height": ("INT", {"default": 1088, "min": 32, "max": 16384, "step": 32}),
                "upscale_method": (["bilinear", "bicubic", "bislerp"], {"default": "bislerp"}),
            }
        }

    RETURN_TYPES = ("LATENT",)
    FUNCTION = "upscale"
    CATEGORY = "model/latent/minimax"

    def upscale(self, samples, width: int, height: int, upscale_method: str):
        return (_plain_latent(samples, _upscale_video(samples["samples"], width, height, upscale_method)),)


class MiniMaxH3CombineAVLatent:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"video": ("LATENT",), "audio": ("LATENT",)}}

    RETURN_TYPES = ("LATENT",)
    FUNCTION = "combine"
    CATEGORY = "model/latent/minimax"

    def combine(self, video, audio):
        video_samples = video["samples"]
        audio_samples = audio["samples"]
        if getattr(video_samples, "is_nested", False) or getattr(audio_samples, "is_nested", False):
            raise ValueError("MiniMax H3 combine requires separated video and audio latents")
        if video_samples.ndim != 5 or audio_samples.ndim != 4:
            raise ValueError("MiniMax H3 latent has an unexpected video/audio shape")
        return (_plain_latent(video, NestedTensor((video_samples, audio_samples))),)


class MiniMaxH3VideoLatentUpscaleContinuation:
    """H3 pass-two handoff: video-only latent upscale without re-noising."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "samples": ("LATENT",),
                "width": ("INT", {"default": 1920, "min": 32, "max": 16384, "step": 32}),
                "height": ("INT", {"default": 1088, "min": 32, "max": 16384, "step": 32}),
                "upscale_method": (["bilinear", "bicubic", "bislerp"], {"default": "bislerp"}),
            }
        }

    RETURN_TYPES = ("LATENT",)
    FUNCTION = "upscale_continue"
    CATEGORY = "model/latent/minimax"

    def upscale_continue(self, samples, width: int, height: int, upscale_method: str):
        packed = samples["samples"]
        if not getattr(packed, "is_nested", False):
            raise ValueError("MiniMax H3 continuation requires a joint video+audio latent")

        video, audio = packed.unbind()
        if video.ndim != 5 or audio.ndim != 4:
            raise ValueError("MiniMax H3 latent has an unexpected video/audio shape")
        video = _upscale_video(video, width, height, upscale_method)
        return (_plain_latent(samples, NestedTensor((video, audio))),)


NODE_CLASS_MAPPINGS = {
    "MiniMaxH3SplitAVLatent": MiniMaxH3SplitAVLatent,
    "MiniMaxH3VideoLatentUpscale": MiniMaxH3VideoLatentUpscale,
    "MiniMaxH3CombineAVLatent": MiniMaxH3CombineAVLatent,
    "MiniMaxH3VideoLatentUpscaleContinuation": MiniMaxH3VideoLatentUpscaleContinuation,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "MiniMaxH3SplitAVLatent": "MiniMax H3 Split AV Latent",
    "MiniMaxH3VideoLatentUpscale": "MiniMax H3 Video Latent Upscale",
    "MiniMaxH3CombineAVLatent": "MiniMax H3 Combine AV Latent",
    "MiniMaxH3VideoLatentUpscaleContinuation": "MiniMax H3 Video Latent Upscale + Continue",
}
