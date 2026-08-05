import colorsys
import math
import random

import numpy as np
from moviepy import ColorClip, VideoClip, concatenate_videoclips
from moviepy.video.fx.CrossFadeIn import CrossFadeIn
from PIL import Image, ImageEnhance, ImageDraw

SAMPLE_RATE = 22050
BORDER_MIN = 3
BORDER_MAX = 18
DISSOLVE_DURATION = 0.75
# Visible hold between transition starts; cycles stills 1→2→3→1…
SEGMENT_HOLD = 4.0


def _saturated_pixels(frame: np.ndarray) -> list[tuple[int, int, int]]:
    pixels = frame.reshape(-1, 3).astype(float)
    step = max(1, len(pixels) // 6000)
    colors = []
    for r, g, b in pixels[::step]:
        h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
        if s >= 0.18 and v >= 0.2:
            colors.append((int(r), int(g), int(b)))
    return colors or [(224, 68, 71)]


def sample_canvas_color(frames: list[np.ndarray], rng: random.Random | None = None) -> tuple[int, int, int]:
    """Pick a saturated color from stills. Tan is never used (eye sclera only)."""
    from art.palette import RED, is_tan

    rng = rng or random.Random()
    pool: list[tuple[int, int, int]] = []
    for frame in frames:
        pool.extend(c for c in _saturated_pixels(frame) if not is_tan(c))
    return rng.choice(pool) if pool else RED


def make_solid_background_clip(duration: float, canvas_size: tuple[int, int], color: tuple[int, int, int]):
    return ColorClip(size=canvas_size, color=color, duration=duration)


def _energy_at(t: float, mono: np.ndarray, global_max_rms: float) -> float:
    center = int(t * SAMPLE_RATE)
    window = int(SAMPLE_RATE * 0.04)
    start = max(0, center - window // 2)
    chunk = mono[start:min(len(mono), start + window)]
    if len(chunk) == 0:
        return 0.0
    rms = float(np.sqrt(np.mean(chunk ** 2)))
    return float(np.clip(rms / global_max_rms, 0, 1))


def make_camera_still_clip(
    image: Image.Image,
    mono: np.ndarray,
    global_max_rms: float,
    duration: float,
    panel_size: int,
    *,
    drift_seed: int = 0,
):
    """Ken-burns camera on a still; RMS gently pulses zoom and brightness."""
    src = image.convert("RGB")
    src_w, src_h = src.size
    rng = random.Random(drift_seed)
    # Start with enough headroom for zoom out/in
    base_scale = max(panel_size / src_w, panel_size / src_h) * 1.12
    pan_x = rng.uniform(-0.08, 0.08)
    pan_y = rng.uniform(-0.08, 0.08)
    zoom_dir = 1 if rng.random() < 0.5 else -1

    def make_frame(t):
        energy = _energy_at(t, mono, global_max_rms)
        progress = t / duration if duration > 0 else 0
        zoom = base_scale * (1.0 + zoom_dir * 0.06 * progress + energy * 0.04)
        crop_w = panel_size / zoom
        crop_h = panel_size / zoom
        max_ox = max(0.0, src_w - crop_w)
        max_oy = max(0.0, src_h - crop_h)
        ox = max_ox * (0.5 + pan_x * progress)
        oy = max_oy * (0.5 + pan_y * progress)
        ox = float(np.clip(ox, 0, max_ox))
        oy = float(np.clip(oy, 0, max_oy))

        cropped = src.crop((int(ox), int(oy), int(ox + crop_w), int(oy + crop_h)))
        framed = cropped.resize((panel_size, panel_size), Image.Resampling.LANCZOS)

        brightness = 1.0 + energy * 0.08
        saturation = 1.0 + energy * 0.1
        framed = ImageEnhance.Brightness(framed).enhance(brightness)
        framed = ImageEnhance.Color(framed).enhance(saturation)
        return np.array(framed)

    return VideoClip(make_frame, duration=duration)


def _rgba_border_frame(t, mono, global_max_rms, canvas_size, video_x, video_y, video_w, video_h, color):
    energy = _energy_at(t, mono, global_max_rms)
    thickness = int(BORDER_MIN + energy * (BORDER_MAX - BORDER_MIN))

    img = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    for i in range(thickness):
        draw.rectangle(
            [
                video_x - thickness + i,
                video_y - thickness + i,
                video_x + video_w + thickness - i,
                video_y + video_h + thickness - i,
            ],
            outline=(*color, 255),
        )
    arr = np.array(img)
    return arr[:, :, :3], arr[:, :, 3].astype(float) / 255.0


def make_pulsing_border_clip(
    mono, global_max_rms, duration, canvas_size, video_x, video_y, video_w, video_h, color
):
    def make_frame(t):
        rgb, _ = _rgba_border_frame(
            t, mono, global_max_rms, canvas_size, video_x, video_y, video_w, video_h, color
        )
        return rgb

    def make_mask(t):
        _, alpha = _rgba_border_frame(
            t, mono, global_max_rms, canvas_size, video_x, video_y, video_w, video_h, color
        )
        return alpha

    clip = VideoClip(make_frame, duration=duration)
    mask = VideoClip(make_mask, duration=duration, is_mask=True)
    return clip.with_mask(mask)


def build_art_sequence(
    stills: list[Image.Image],
    mono: np.ndarray,
    global_max_rms: float,
    total_duration: float,
    panel_size: int,
    master_seed: int,
    dissolve: float = DISSOLVE_DURATION,
    segment_hold: float = SEGMENT_HOLD,
):
    """Cycle stills with short crossfades: 1→2→3→1… for the full duration."""
    n = len(stills)
    if n == 0:
        raise ValueError("No stills to animate")

    if n == 1:
        return make_camera_still_clip(
            stills[0],
            mono,
            global_max_rms,
            total_duration,
            panel_size,
            drift_seed=master_seed + 100,
        )

    dissolve = min(dissolve, segment_hold / 2)
    # With padding=-dissolve: out = count*seg - (count-1)*dissolve
    # seg = hold + dissolve → out = count*hold + dissolve
    seg = segment_hold + dissolve
    count = max(n, math.ceil((total_duration - dissolve) / segment_hold))

    clips = []
    for i in range(count):
        image = stills[i % n]
        clip = make_camera_still_clip(
            image,
            mono,
            global_max_rms,
            seg,
            panel_size,
            drift_seed=master_seed + 100 + i,
        )
        if i > 0:
            clip = clip.with_effects([CrossFadeIn(dissolve)])
        clips.append(clip)

    sequence = concatenate_videoclips(clips, method="compose", padding=-dissolve)
    return sequence.with_duration(total_duration)
