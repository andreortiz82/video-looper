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


def _rgba_border_frame(
    t,
    mono,
    global_max_rms,
    canvas_size,
    video_x,
    video_y,
    video_w,
    video_h,
    color,
    border_min=BORDER_MIN,
    border_max=BORDER_MAX,
):
    energy = _energy_at(t, mono, global_max_rms)
    thickness = int(border_min + energy * (border_max - border_min))

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
    mono,
    global_max_rms,
    duration,
    canvas_size,
    video_x,
    video_y,
    video_w,
    video_h,
    color,
    *,
    border_min=BORDER_MIN,
    border_max=BORDER_MAX,
):
    def make_frame(t):
        rgb, _ = _rgba_border_frame(
            t,
            mono,
            global_max_rms,
            canvas_size,
            video_x,
            video_y,
            video_w,
            video_h,
            color,
            border_min=border_min,
            border_max=border_max,
        )
        return rgb

    def make_mask(t):
        _, alpha = _rgba_border_frame(
            t,
            mono,
            global_max_rms,
            canvas_size,
            video_x,
            video_y,
            video_w,
            video_h,
            color,
            border_min=border_min,
            border_max=border_max,
        )
        return alpha

    clip = VideoClip(make_frame, duration=duration)
    mask = VideoClip(make_mask, duration=duration, is_mask=True)
    return clip.with_mask(mask)


def make_rotating_background_clip(
    image: Image.Image,
    duration: float,
    canvas_size: tuple[int, int],
    *,
    revolutions: float = 1.0,
):
    """Full-bleed background that spins; oversized source hides rotation corners."""
    cw, ch = canvas_size
    diag = int(math.ceil(math.hypot(cw, ch))) + 4
    src = image.convert("RGB")
    scale = max(diag / src.width, diag / src.height)
    spun_size = max(diag, int(max(src.width, src.height) * scale))
    base = src.resize((spun_size, spun_size), Image.Resampling.LANCZOS)
    cx = (spun_size - cw) // 2
    cy = (spun_size - ch) // 2

    def make_frame(t):
        angle = -360.0 * revolutions * (t / duration if duration > 0 else 0)
        rotated = base.rotate(angle, resample=Image.Resampling.BILINEAR, expand=False)
        frame = rotated.crop((cx, cy, cx + cw, cy + ch))
        return np.array(frame)

    return VideoClip(make_frame, duration=duration)


def make_pulse_still_background_clip(
    image: Image.Image,
    mono: np.ndarray,
    global_max_rms: float,
    duration: float,
    canvas_size: tuple[int, int],
):
    """Full-bleed still with RMS zoom + brightness/saturation pulse."""
    cw, ch = canvas_size
    fitted = image.convert("RGB").resize((cw, ch), Image.Resampling.LANCZOS)

    def make_frame(t):
        energy = _energy_at(t, mono, global_max_rms)
        zoom = 1.0 + energy * 0.035
        crop_w = cw / zoom
        crop_h = ch / zoom
        ox = (cw - crop_w) / 2
        oy = (ch - crop_h) / 2
        cropped = fitted.crop((int(ox), int(oy), int(ox + crop_w), int(oy + crop_h)))
        framed = cropped.resize((cw, ch), Image.Resampling.LANCZOS)
        framed = ImageEnhance.Brightness(framed).enhance(1.0 + energy * 0.12)
        framed = ImageEnhance.Color(framed).enhance(1.0 + energy * 0.18)
        return np.array(framed)

    return VideoClip(make_frame, duration=duration)


# Peak-driven hard cuts: ignore micro-spikes, keep cuts musically spaced.
CUT_MIN_GAP = 2.0
CUT_PEAK_THRESHOLD = 0.42
CUT_RISE = 0.08
CUT_HOP_SEC = 0.05


def detect_cut_times(
    mono: np.ndarray,
    global_max_rms: float,
    duration: float,
    *,
    min_gap: float = CUT_MIN_GAP,
    peak_threshold: float = CUT_PEAK_THRESHOLD,
) -> list[float]:
    """Return cut timestamps on volume peaks / sharp rises (not a fixed timer)."""
    if duration <= 0 or len(mono) == 0:
        return []

    hop = max(1, int(SAMPLE_RATE * CUT_HOP_SEC))
    window = max(hop, int(SAMPLE_RATE * 0.04))
    energies: list[tuple[float, float]] = []
    for i in range(0, len(mono) - window, hop):
        t = i / SAMPLE_RATE
        if t >= duration:
            break
        rms = float(np.sqrt(np.mean(mono[i : i + window] ** 2)))
        energies.append((t, float(np.clip(rms / global_max_rms, 0, 1))))

    if len(energies) < 3:
        return []

    cuts: list[float] = []
    last_cut = -min_gap
    for i in range(1, len(energies) - 1):
        t, e = energies[i]
        prev_e = energies[i - 1][1]
        next_e = energies[i + 1][1]
        is_peak = e >= prev_e and e >= next_e
        rising = e - prev_e >= CUT_RISE
        if not (is_peak or rising):
            continue
        if e < peak_threshold and not (rising and e >= peak_threshold * 0.75):
            continue
        if t - last_cut < min_gap:
            continue
        # Skip a cut at t≈0 — start on first still, cut later on peaks.
        if t < 0.35:
            continue
        cuts.append(t)
        last_cut = t

    # If the track is quiet/flat, fall back to a few evenly spaced cuts.
    if len(cuts) < 2:
        step = max(min_gap, duration / 4)
        cuts = [t for t in np.arange(step, duration, step).tolist() if t < duration - 0.25]

    return cuts


def _still_index_at(t: float, cut_times: list[float]) -> int:
    # Number of cuts that have already happened.
    idx = 0
    for cut in cut_times:
        if t >= cut:
            idx += 1
        else:
            break
    return idx


def _prepare_bg_bases(
    stills: list[Image.Image],
    canvas_size: tuple[int, int],
    *,
    rotate: bool,
) -> list[Image.Image]:
    cw, ch = canvas_size
    prepared: list[Image.Image] = []
    if rotate:
        # Extra headroom for rotation + music zoom.
        diag = int(math.ceil(math.hypot(cw, ch) * 1.12)) + 4
        for image in stills:
            src = image.convert("RGB")
            scale = max(diag / src.width, diag / src.height)
            size = max(diag, int(max(src.width, src.height) * scale))
            prepared.append(src.resize((size, size), Image.Resampling.LANCZOS))
    else:
        for image in stills:
            prepared.append(image.convert("RGB").resize((cw, ch), Image.Resampling.LANCZOS))
    return prepared


def build_hard_cut_background_sequence(
    stills: list[Image.Image],
    mono: np.ndarray,
    global_max_rms: float,
    total_duration: float,
    canvas_size: tuple[int, int],
    *,
    rotate: bool = False,
    revolutions: float = 1.0,
    min_gap: float = CUT_MIN_GAP,
):
    """Cycle backgrounds with hard cuts on musical peaks; pulse zoom to RMS.

    Style A: rotate continuously + zoom/bounce + brightness/sat.
    Style B: zoom/bounce + brightness/sat (no rotate).
    """
    n = len(stills)
    if n == 0:
        raise ValueError("No background stills to animate")

    cw, ch = canvas_size
    cut_times = detect_cut_times(mono, global_max_rms, total_duration, min_gap=min_gap)
    print(f"  Background cuts: {len(cut_times)} peak-driven hard cuts")
    bases = _prepare_bg_bases(stills, canvas_size, rotate=rotate)

    def make_frame(t):
        energy = _energy_at(t, mono, global_max_rms)
        still_i = _still_index_at(t, cut_times) % n
        base = bases[still_i]
        zoom = 1.0 + energy * 0.05

        if rotate:
            angle = -360.0 * revolutions * (t / total_duration if total_duration > 0 else 0)
            rotated = base.rotate(angle, resample=Image.Resampling.BILINEAR, expand=False)
            crop_w = cw / zoom
            crop_h = ch / zoom
            ox = (rotated.width - crop_w) / 2
            oy = (rotated.height - crop_h) / 2
            framed = rotated.crop((int(ox), int(oy), int(ox + crop_w), int(oy + crop_h)))
            framed = framed.resize((cw, ch), Image.Resampling.LANCZOS)
            framed = ImageEnhance.Brightness(framed).enhance(1.0 + energy * 0.14)
            framed = ImageEnhance.Color(framed).enhance(1.0 + energy * 0.2)
            return np.array(framed)

        crop_w = cw / zoom
        crop_h = ch / zoom
        ox = (cw - crop_w) / 2
        oy = (ch - crop_h) / 2
        cropped = base.crop((int(ox), int(oy), int(ox + crop_w), int(oy + crop_h)))
        framed = cropped.resize((cw, ch), Image.Resampling.LANCZOS)
        framed = ImageEnhance.Brightness(framed).enhance(1.0 + energy * 0.12)
        framed = ImageEnhance.Color(framed).enhance(1.0 + energy * 0.18)
        return np.array(framed)

    return VideoClip(make_frame, duration=total_duration)


def pick_accent_color(rng: random.Random) -> tuple[int, int, int]:
    from art.palette import ACCENTS, assert_not_tan

    color = rng.choice(ACCENTS)
    assert_not_tan(color, context="accent")
    return color


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
