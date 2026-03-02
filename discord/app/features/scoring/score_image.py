from __future__ import annotations

from io import BytesIO
import struct
import zlib

import discord

BASE_WIDTH = 460
BASE_HEIGHT = 160
RENDER_SCALE = 2
WIDTH = BASE_WIDTH * RENDER_SCALE
HEIGHT = BASE_HEIGHT * RENDER_SCALE

FONT_5X7 = {
    "0": ["01110", "10001", "10011", "10101", "11001", "10001", "01110"],
    "1": ["00100", "01100", "00100", "00100", "00100", "00100", "01110"],
    "2": ["01110", "10001", "00001", "00010", "00100", "01000", "11111"],
    "3": ["11110", "00001", "00001", "01110", "00001", "00001", "11110"],
    "4": ["00010", "00110", "01010", "10010", "11111", "00010", "00010"],
    "5": ["11111", "10000", "11110", "00001", "00001", "10001", "01110"],
    "6": ["00110", "01000", "10000", "11110", "10001", "10001", "01110"],
    "7": ["11111", "00001", "00010", "00100", "01000", "01000", "01000"],
    "8": ["01110", "10001", "10001", "01110", "10001", "10001", "01110"],
    "9": ["01110", "10001", "10001", "01111", "00001", "00010", "11100"],
    ".": ["00000", "00000", "00000", "00000", "00000", "01100", "01100"],
    "/": ["00001", "00010", "00010", "00100", "01000", "01000", "10000"],
}


def _lerp(a: int, b: int, t: float) -> int:
    return int(a + (b - a) * t)


def _clamp_score(score: float) -> float:
    return max(0.0, min(100.0, float(score)))


def _score_to_rgb(score: float) -> tuple[int, int, int]:
    value = _clamp_score(score)
    low = (239, 68, 68)
    orange = (249, 115, 22)
    blue = (125, 211, 252)
    violet = (139, 92, 246)
    yellow = (250, 204, 21)

    if value >= 100.0:
        return yellow
    if value < 50.0:
        ratio = value / 49.0 if value > 0.0 else 0.0
        start = low
        end = orange
    else:
        ratio = (value - 50.0) / 49.0
        start = blue
        end = violet

    smooth = ratio * ratio * (3.0 - (2.0 * ratio))
    return (
        _lerp(start[0], end[0], smooth),
        _lerp(start[1], end[1], smooth),
        _lerp(start[2], end[2], smooth),
    )


def _pick_font(draw, text: str, sizes: tuple[int, ...], max_width: int, stroke_width: int):
    try:
        from PIL import ImageFont
    except Exception:
        return None

    font_candidates = (
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/seguiemj.ttf",
        "C:/Windows/Fonts/segoeuib.ttf",
        "arialbd.ttf",
        "arial.ttf",
    )
    for size in sizes:
        for path in font_candidates:
            try:
                candidate = ImageFont.truetype(path, size)
            except Exception:
                continue
            left, _, right, _ = draw.textbbox((0, 0), text, font=candidate, stroke_width=stroke_width)
            if (right - left) <= max_width:
                return candidate
    return None


def _measure_block(text: str, scale: int) -> tuple[int, int]:
    return (_text_width(text, scale), 7 * scale)


def _fit_main_scale(text: str, max_width: int, preferred: int) -> int:
    scale = preferred
    while scale > 4 and _text_width(text, scale) > max_width:
        scale -= 1
    return scale


def _chunk(tag: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(tag)
    crc = zlib.crc32(data, crc)
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc & 0xFFFFFFFF)


def _make_png_bytes(width: int, height: int, pixels: bytearray) -> bytes:
    rows = []
    stride = width * 4
    for y in range(height):
        start = y * stride
        rows.append(b"\x00" + pixels[start : start + stride])
    raw = b"".join(rows)
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return b"".join(
        [
            b"\x89PNG\r\n\x1a\n",
            _chunk(b"IHDR", ihdr),
            _chunk(b"IDAT", zlib.compress(raw, 9)),
            _chunk(b"IEND", b""),
        ]
    )


def _set_pixel(pixels: bytearray, width: int, height: int, x: int, y: int, color: tuple[int, int, int, int]) -> None:
    if x < 0 or y < 0 or x >= width or y >= height:
        return
    idx = (y * width + x) * 4
    pixels[idx : idx + 4] = bytes(color)


def _fill_rect(
    pixels: bytearray,
    width: int,
    height: int,
    left: int,
    top: int,
    rect_width: int,
    rect_height: int,
    color: tuple[int, int, int, int],
) -> None:
    for y in range(top, top + rect_height):
        for x in range(left, left + rect_width):
            _set_pixel(pixels, width, height, x, y, color)


def _draw_text(
    pixels: bytearray,
    width: int,
    height: int,
    x: int,
    y: int,
    text: str,
    scale: int,
    color: tuple[int, int, int, int],
) -> None:
    cursor_x = x
    for ch in text:
        glyph = FONT_5X7.get(ch)
        if glyph is None:
            cursor_x += 6 * scale
            continue
        for row_idx, row in enumerate(glyph):
            for col_idx, bit in enumerate(row):
                if bit != "1":
                    continue
                _fill_rect(
                    pixels,
                    width,
                    height,
                    cursor_x + col_idx * scale,
                    y + row_idx * scale,
                    scale,
                    scale,
                    color,
                )
        cursor_x += 6 * scale


def _text_width(text: str, scale: int) -> int:
    return max(0, len(text) * 6 * scale - scale)


def _draw_outlined_text(
    pixels: bytearray,
    width: int,
    height: int,
    x: int,
    y: int,
    text: str,
    scale: int,
    fill: tuple[int, int, int, int],
    outline: tuple[int, int, int, int],
) -> None:
    for dx in (-2, -1, 0, 1, 2):
        for dy in (-2, -1, 0, 1, 2):
            if dx == 0 and dy == 0:
                continue
            _draw_text(pixels, width, height, x + dx, y + dy, text, scale, outline)
    _draw_text(pixels, width, height, x, y, text, scale, fill)


def _fallback_score_file(score: float) -> discord.File:
    width, height = WIDTH, HEIGHT
    pixels = bytearray(width * height * 4)
    score_value = _clamp_score(score)
    accent = _score_to_rgb(score_value)
    bg = (3, 19, 54, 255)
    inner_bg = (2, 17, 48, 255)
    border = (245, 155, 66, 255)
    inner_border = (255, 196, 110, 255)

    for y in range(height):
        for x in range(width):
            _set_pixel(pixels, width, height, x, y, bg)

    border_size = 3 * RENDER_SCALE
    inset = 10 * RENDER_SCALE
    inner_border_size = 2 * RENDER_SCALE

    _fill_rect(pixels, width, height, 0, 0, width, border_size, border)
    _fill_rect(pixels, width, height, 0, height - border_size, width, border_size, border)
    _fill_rect(pixels, width, height, 0, 0, border_size, height, border)
    _fill_rect(pixels, width, height, width - border_size, 0, border_size, height, border)
    _fill_rect(pixels, width, height, inset, inset, width - inset * 2, height - inset * 2, inner_bg)
    _fill_rect(pixels, width, height, inset, inset, width - inset * 2, inner_border_size, inner_border)
    _fill_rect(
        pixels,
        width,
        height,
        inset,
        height - inset - inner_border_size,
        width - inset * 2,
        inner_border_size,
        inner_border,
    )
    _fill_rect(pixels, width, height, inset, inset, inner_border_size, height - inset * 2, inner_border)
    _fill_rect(
        pixels,
        width,
        height,
        width - inset - inner_border_size,
        inset,
        inner_border_size,
        height - inset * 2,
        inner_border,
    )

    score_text = str(int(round(score_value)))
    suffix_text = "/100"
    main_scale = _fit_main_scale(score_text, 280 * RENDER_SCALE, 24)
    suffix_scale = 10
    fill = (*accent, 255)
    outline = (3, 7, 18, 255)
    suffix_fill = (232, 236, 244, 255)
    if int(round(score_value)) >= 100:
        suffix_fill = fill

    main_width, main_height = _measure_block(score_text, main_scale)
    suffix_width, suffix_height = _measure_block(suffix_text, suffix_scale)
    gap = 18 * RENDER_SCALE
    total_width = main_width + gap + suffix_width
    block_left = max(20 * RENDER_SCALE, (width - total_width) // 2)
    score_x = block_left
    score_y = max(28 * RENDER_SCALE, (height - main_height) // 2)
    suffix_x = score_x + main_width + gap
    suffix_y = score_y + main_height - suffix_height - (2 * RENDER_SCALE)

    _draw_outlined_text(pixels, width, height, score_x, score_y, score_text, main_scale, fill, outline)
    _draw_outlined_text(pixels, width, height, suffix_x, suffix_y, suffix_text, suffix_scale, suffix_fill, outline)

    buffer = BytesIO(_make_png_bytes(width, height, pixels))
    buffer.seek(0)
    return discord.File(fp=buffer, filename="score.png")


def make_score_png(score: float) -> discord.File | None:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception:
        return _fallback_score_file(score)

    width, height = WIDTH, HEIGHT
    score_value = _clamp_score(score)
    image = Image.new("RGBA", (width, height), (3, 19, 54, 255))
    draw = ImageDraw.Draw(image)

    outer_border = (245, 155, 66, 255)
    inner_border = (255, 196, 110, 220)
    panel_bg = (2, 17, 48, 255)
    accent = _score_to_rgb(score_value)

    draw.rounded_rectangle((0, 0, width - 1, height - 1), radius=24 * RENDER_SCALE, outline=outer_border, width=2 * RENDER_SCALE)
    draw.rounded_rectangle(
        (10 * RENDER_SCALE, 10 * RENDER_SCALE, width - (11 * RENDER_SCALE), height - (11 * RENDER_SCALE)),
        radius=18 * RENDER_SCALE,
        fill=panel_bg,
        outline=inner_border,
        width=2 * RENDER_SCALE,
    )

    glow_center_x = width // 2
    glow_center_y = height // 2
    for radius, alpha in ((92, 24), (74, 34), (56, 44)):
        draw.ellipse(
            (
                glow_center_x - (radius * RENDER_SCALE),
                glow_center_y - (radius * RENDER_SCALE),
                glow_center_x + (radius * RENDER_SCALE),
                glow_center_y + (radius * RENDER_SCALE),
            ),
            fill=(*accent, alpha),
        )

    font_score = _pick_font(
        draw,
        str(int(round(score_value))),
        sizes=(176, 164, 152, 140, 128),
        max_width=280 * RENDER_SCALE,
        stroke_width=8,
    )
    font_suffix = _pick_font(draw, "/100", sizes=(56, 52, 48), max_width=110 * RENDER_SCALE, stroke_width=3)
    if font_suffix is None:
        font_suffix = ImageFont.load_default()
    if font_score is None:
        font_score = ImageFont.load_default()

    score_text = str(int(round(score_value)))
    outline = (3, 7, 18, 255)
    fill = (*accent, 255)
    suffix_fill = (232, 236, 244, 255)
    if int(round(score_value)) >= 100:
        suffix_fill = fill

    main_box = draw.textbbox((0, 0), score_text, font=font_score, stroke_width=8)
    suffix_text = "/100"
    suffix_box = draw.textbbox((0, 0), suffix_text, font=font_suffix, stroke_width=3)
    main_width = main_box[2] - main_box[0]
    main_height = main_box[3] - main_box[1]
    suffix_width = suffix_box[2] - suffix_box[0]
    suffix_height = suffix_box[3] - suffix_box[1]
    gap = 18 * RENDER_SCALE
    total_width = main_width + gap + suffix_width
    left = max(20 * RENDER_SCALE, (width - total_width) // 2)
    baseline_top = max(28 * RENDER_SCALE, (height - main_height) // 2)
    suffix_top = baseline_top + main_height - suffix_height - (6 * RENDER_SCALE)

    draw.text(
        (left, baseline_top),
        score_text,
        fill=fill,
        font=font_score,
        stroke_width=8,
        stroke_fill=outline,
    )
    draw.text(
        (left + main_width + gap, suffix_top),
        suffix_text,
        fill=suffix_fill,
        font=font_suffix,
        stroke_width=3,
        stroke_fill=outline,
    )

    buffer = BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    return discord.File(fp=buffer, filename="score.png")
