"""MiniMax H3 helpers for two-pass 1080p sampling.

H3 stores video and audio in a single nested latent. Generic ComfyUI latent
upscalers assume an image VAE with an 8x spatial compression, while H3 video
uses 16x.  The second H3 pass must *not* sample a directly interpolated
latent: that creates correlated high-sigma noise (visible as colourful rings
or grids after VAE decoding).  The combined node below upscales video only,
re-noises it on the target grid at the pass-two sigma, and keeps audio clean.
"""

from __future__ import annotations

import torch
import torch.nn.functional as F

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
                "upscale_method": (["bilinear", "bicubic"], {"default": "bicubic"}),
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


class MiniMaxH3VideoLatentUpscaleReNoise:
    """H3-specific pass-two handoff: video upscale + CONST re-noise, audio lock.

    ``SamplerCustomAdvanced`` applies its own flow-noise mixing.  Therefore the
    returned latent is inverse-scaled so feeding it through ``DisableNoise``
    reconstructs ``sigma * video_noise + (1 - sigma) * upscaled_video``.  The
    audio stream receives zero noise and is pre-divided by ``1 - sigma`` so it
    enters pass two unchanged.  It intentionally does not use Comfy's inpaint
    mask to lock audio: that wrapper reinjects the pre-divided carry into H3's
    joint transformer and corrupts the video stream.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "samples": ("LATENT",),
                "model": ("MODEL",),
                "noise": ("NOISE",),
                "sigmas": ("SIGMAS",),
                "width": ("INT", {"default": 1920, "min": 32, "max": 16384, "step": 32}),
                "height": ("INT", {"default": 1088, "min": 32, "max": 16384, "step": 32}),
                "upscale_method": (["bilinear", "bicubic"], {"default": "bicubic"}),
            }
        }

    RETURN_TYPES = ("LATENT",)
    FUNCTION = "upscale_renoise"
    CATEGORY = "model/latent/minimax"

    def upscale_renoise(self, samples, model, noise, sigmas, width: int, height: int, upscale_method: str):
        packed = samples["samples"]
        if not getattr(packed, "is_nested", False):
            raise ValueError("MiniMax H3 re-noise requires a joint video+audio latent")
        if len(sigmas) < 2:
            raise ValueError("MiniMax H3 re-noise requires a non-empty second-pass sigma schedule")
        sigma = sigmas[0]
        sigma_value = float(sigma)
        if not 0.0 < sigma_value < 1.0:
            raise ValueError(f"MiniMax H3 second-pass sigma must be between 0 and 1, got {sigma_value}")

        video, audio = packed.unbind()
        if video.ndim != 5 or audio.ndim != 4:
            raise ValueError("MiniMax H3 latent has an unexpected video/audio shape")
        video = _upscale_video(video, width, height, upscale_method)
        handoff = _plain_latent(samples, NestedTensor((video, audio)))

        # Draw fresh, independent target-grid noise for video only.  Copying or
        # interpolating the low-resolution noise is precisely what causes grid /
        # ring artifacts during a high-sigma continuation.
        generated = noise.generate_noise(handoff)
        noise_video, _ = generated.unbind()
        noise_audio = torch.zeros_like(audio, device=noise_video.device)

        process_in = model.get_model_object("process_latent_in")
        process_out = model.get_model_object("process_latent_out")
        model_sampling = model.get_model_object("model_sampling")
        video_in, audio_in = process_in(handoff["samples"]).unbind()

        # CONST flow: SamplerCustomAdvanced will later multiply the supplied
        # latent by (1-sigma) because it receives DisableNoise.  Inverse-scale
        # now so the sampler starts exactly at the intended noisy video state.
        video_mixed = model_sampling.noise_scaling(sigma, noise_video.to(video_in), video_in)
        video_handoff = model_sampling.inverse_noise_scaling(sigma, video_mixed)
        audio_handoff = audio_in / (1.0 - sigma)
        combined = process_out(NestedTensor((video_handoff, audio_handoff)))

        return (_plain_latent(samples, combined),)


NODE_CLASS_MAPPINGS = {
    "MiniMaxH3SplitAVLatent": MiniMaxH3SplitAVLatent,
    "MiniMaxH3VideoLatentUpscale": MiniMaxH3VideoLatentUpscale,
    "MiniMaxH3CombineAVLatent": MiniMaxH3CombineAVLatent,
    "MiniMaxH3VideoLatentUpscaleReNoise": MiniMaxH3VideoLatentUpscaleReNoise,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "MiniMaxH3SplitAVLatent": "MiniMax H3 Split AV Latent",
    "MiniMaxH3VideoLatentUpscale": "MiniMax H3 Video Latent Upscale",
    "MiniMaxH3CombineAVLatent": "MiniMax H3 Combine AV Latent",
    "MiniMaxH3VideoLatentUpscaleReNoise": "MiniMax H3 Video Latent Upscale + Re-noise",
}
