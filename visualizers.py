import colorsys
import random

import numpy as np
from moviepy import VideoClip
from PIL import Image, ImageDraw

SAMPLE_RATE = 22050
N_SPOKES = 72
BORDER_MIN = 3
BORDER_MAX = 18


def _saturated_pixels(frame: np.ndarray) -> list[tuple[int, int, int]]:
    pixels = frame.reshape(-1, 3).astype(float)
    step = max(1, len(pixels) // 6000)
    colors = []
    for r, g, b in pixels[::step]:
        h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
        if s >= 0.18 and v >= 0.2:
            colors.append((int(r), int(g), int(b)))
    return colors or [(200, 80, 40)]


def _color_distance(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5


def sample_random_colors(frame: np.ndarray) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    pool = _saturated_pixels(frame)
    bg_color = random.choice(pool)
    radial_pool = [c for c in pool if _color_distance(c, bg_color) > 60] or pool
    radial_color = random.choice(radial_pool)
    if _color_distance(bg_color, radial_color) < 50:
        radial_color = (255, 255, 255)
    return bg_color, radial_color


def _fft_spoke_vals(chunk, n_spokes=N_SPOKES):
    window = int(SAMPLE_RATE * 0.04)
    hann = np.hanning(window)
    padded = np.zeros(window)
    padded[:len(chunk)] = chunk
    fft = np.abs(np.fft.rfft(padded * hann))
    if len(fft) < n_spokes:
        return np.zeros(n_spokes)
    edges = np.linspace(0, len(fft) - 1, n_spokes + 1, dtype=int)
    vals = np.array([np.mean(fft[edges[i]:edges[i + 1] + 1]) for i in range(n_spokes)])
    return vals / (np.max(vals) + 1e-6)


def make_radial_background_clip(
    mono,
    global_max_rms,
    duration,
    canvas_size,
    bg_color,
    radial_color,
    center_x,
    center_y,
    inner_radius,
    outer_radius,
):
    angles = np.linspace(0, 2 * np.pi, N_SPOKES, endpoint=False)
    cos_a = np.cos(angles)
    sin_a = np.sin(angles)

    def make_frame(t):
        img = Image.new("RGB", canvas_size, bg_color)
        draw = ImageDraw.Draw(img)

        center = int(t * SAMPLE_RATE)
        window = int(SAMPLE_RATE * 0.04)
        start = max(0, center - window // 2)
        chunk = mono[start:min(len(mono), start + window)]

        if len(chunk) > 1:
            vals = _fft_spoke_vals(chunk)
            rms = np.sqrt(np.mean(chunk ** 2))
            energy = np.clip(rms / global_max_rms, 0, 1)
            stroke = max(4, int(5 + energy * 4))

            for i, val in enumerate(vals):
                length = inner_radius + val * (outer_radius - inner_radius) * (0.55 + energy * 0.45)
                x0 = center_x + int(cos_a[i] * inner_radius)
                y0 = center_y + int(sin_a[i] * inner_radius)
                x1 = center_x + int(cos_a[i] * length)
                y1 = center_y + int(sin_a[i] * length)
                draw.line([(x0, y0), (x1, y1)], fill=radial_color, width=stroke)

        return np.array(img)

    return VideoClip(make_frame, duration=duration)


def _rgba_border_frame(t, mono, global_max_rms, canvas_size, video_x, video_y, video_w, video_h, color):
    center = int(t * SAMPLE_RATE)
    window = int(SAMPLE_RATE * 0.04)
    start = max(0, center - window // 2)
    chunk = mono[start:min(len(mono), start + window)]
    rms = np.sqrt(np.mean(chunk ** 2)) if len(chunk) > 0 else 0
    norm = np.clip(rms / global_max_rms, 0, 1)
    thickness = int(BORDER_MIN + norm * (BORDER_MAX - BORDER_MIN))

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
