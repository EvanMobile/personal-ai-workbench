"""Pillow renderer for knowledge card images.

The card is a presentation of authoritative structured data, never the source
of truth. Rendering is deterministic for a given content hash.
"""

from __future__ import annotations

import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

WIDTH = 1200
HEIGHT = 1600
MARGIN = 80
BG = (10, 11, 14)
PANEL = (17, 18, 21)
BORDER = (42, 44, 50)
TEXT = (232, 232, 235)
MUTED = (139, 141, 147)
ACCENT = (124, 92, 255)
ACCENT_SOFT = (54, 44, 96)
GREEN = (110, 231, 168)
MOCK_ORANGE = (255, 176, 64)

FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
]


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for candidate in FONT_CANDIDATES:
        if Path(candidate).exists():
            try:
                return ImageFont.truetype(candidate, size=size)
            except OSError:
                continue
    return ImageFont.load_default(size=size)


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    lines: list[str] = []
    for paragraph in text.split("\n"):
        if not paragraph.strip():
            lines.append("")
            continue
        current = ""
        for char in paragraph:
            trial = current + char
            if draw.textlength(trial, font=font) <= max_width or not current:
                current = trial
            else:
                lines.append(current)
                current = char
        if current:
            lines.append(current)
    return lines


def _draw_paragraph(
    draw: ImageDraw.ImageDraw,
    text: str,
    font,
    x: int,
    y: int,
    max_width: int,
    fill=TEXT,
    line_gap: int = 10,
    max_y: int = HEIGHT - 180,
) -> int:
    line_height = font.size + line_gap
    for line in _wrap(draw, text, font, max_width):
        if y + line_height > max_y:
            draw.text((x, y), "…", font=font, fill=fill)
            return max_y
        draw.text((x, y), line, font=font, fill=fill)
        y += line_height
    return y


def _clean_markdown(body: str) -> list[tuple[str, str]]:
    """Return (kind, text) blocks: heading / bullet / paragraph."""
    blocks: list[tuple[str, str]] = []
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#"):
            blocks.append(("heading", line.lstrip("#").strip()))
        elif line.startswith(("- ", "* ")):
            blocks.append(("bullet", line[2:].strip()))
        else:
            blocks.append(("paragraph", line))
    return blocks


def format_source_line(
    *,
    category: str,
    provider: str,
    model: str,
    version: int,
    processing_mode: str,
    is_mock: bool | None,
) -> str:
    if is_mock is True:
        return f"MOCK · {processing_mode.upper()} · {provider} · {model} · v{version}"
    if is_mock is None:
        return f"UNKNOWN · LEGACY RECORD · {provider} · {model} · v{version}"
    return f"{category}  ·  {provider} · {model}  ·  v{version}"


def render_knowledge_card(
    path: Path,
    *,
    title: str,
    summary: str,
    conclusion: str,
    body_markdown: str,
    category: str,
    tags: list[str],
    provider: str,
    model: str,
    version: int,
    processing_mode: str,
    is_mock: bool | None,
    footer_note: str = "",
) -> None:
    image = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(image)

    # subtle dot grid
    for gx in range(40, WIDTH, 40):
        for gy in range(40, HEIGHT, 40):
            draw.point((gx, gy), fill=(24, 25, 29))

    draw.rectangle([MARGIN, 70, MARGIN + 36, 74], fill=ACCENT)
    draw.text(
        (MARGIN + 52, 58),
        "PERSONAL LLM WIKI  /  KNOWLEDGE CARD",
        font=_font(18),
        fill=MUTED,
    )
    if is_mock is True:
        draw.rounded_rectangle(
            [WIDTH - MARGIN - 96, 50, WIDTH - MARGIN, 86],
            radius=4,
            fill=MOCK_ORANGE,
        )
        draw.text((WIDTH - MARGIN - 82, 58), "MOCK", font=_font(18), fill=(12, 12, 14))
        draw.text(
            (WIDTH - MARGIN - 240, 58),
            "RULE-BASED · NO LLM",
            font=_font(15),
            fill=MOCK_ORANGE,
        )
    elif is_mock is None:
        draw.rounded_rectangle(
            [WIDTH - MARGIN - 128, 50, WIDTH - MARGIN, 86],
            radius=4,
            fill=PANEL,
            outline=BORDER,
        )
        draw.text((WIDTH - MARGIN - 116, 58), "UNKNOWN", font=_font(16), fill=MUTED)
        draw.text(
            (WIDTH - MARGIN - 330, 58),
            "LEGACY RECORD · SOURCE UNKNOWN",
            font=_font(15),
            fill=MUTED,
        )
    else:
        draw.text((WIDTH - MARGIN - 130, 58), "P1.M1", font=_font(18), fill=MUTED)

    y = 130
    y = _draw_paragraph(draw, title, _font(60), MARGIN, y, WIDTH - MARGIN * 2, TEXT, 14, 430) + 18

    draw.rounded_rectangle(
        [MARGIN, y, MARGIN + 8, y + 120], radius=4, fill=ACCENT
    )
    y = _draw_paragraph(
        draw, summary, _font(28), MARGIN + 30, y + 4, WIDTH - MARGIN * 2 - 30, MUTED, 10, 640
    ) + 24

    chip_x = MARGIN
    chip_y = y
    for tag in (tags or [])[:5]:
        label = tag.upper()
        width = int(draw.textlength(label, font=_font(18))) + 28
        if chip_x + width > WIDTH - MARGIN:
            chip_x = MARGIN
            chip_y += 44
        draw.rounded_rectangle(
            [chip_x, chip_y, chip_x + width, chip_y + 34], radius=17, fill=PANEL, outline=BORDER
        )
        draw.text((chip_x + 14, chip_y + 8), label, font=_font(18), fill=GREEN)
        chip_x += width + 10
    y = chip_y + 60

    draw.line([MARGIN, y, WIDTH - MARGIN, y], fill=BORDER, width=2)
    y += 34

    body_blocks = _clean_markdown(body_markdown)
    heading_font = _font(24)
    body_font = _font(22)
    bullet_font = _font(22)
    for kind, text in body_blocks:
        if kind == "heading":
            if y > HEIGHT - 330:
                break
            y += 14
            draw.text((MARGIN, y), text.upper(), font=heading_font, fill=ACCENT)
            y += 42
        elif kind == "bullet":
            if y > HEIGHT - 300:
                break
            draw.text((MARGIN, y), "•", font=bullet_font, fill=GREEN)
            y = _draw_paragraph(
                draw, text, bullet_font, MARGIN + 26, y, WIDTH - MARGIN * 2 - 26, TEXT, 6, HEIGHT - 300
            ) + 4
        else:
            if y > HEIGHT - 300:
                break
            y = _draw_paragraph(
                draw, text, body_font, MARGIN, y, WIDTH - MARGIN * 2, TEXT, 6, HEIGHT - 300
            ) + 10

    # footer
    footer_y = HEIGHT - 190
    if is_mock is True:
        draw.text(
            (MARGIN, footer_y - 30),
            "规则模拟 · 未调用真实 LLM · 不代表真实语义分析",
            font=_font(16),
            fill=MOCK_ORANGE,
        )
    elif is_mock is None:
        draw.text(
            (MARGIN, footer_y - 30),
            "历史记录来源未知，不能视为真实 LLM 分析",
            font=_font(16),
            fill=MUTED,
        )
    draw.line([MARGIN, footer_y, WIDTH - MARGIN, footer_y], fill=BORDER, width=1)
    source_line = format_source_line(
        category=category,
        provider=provider,
        model=model,
        version=version,
        processing_mode=processing_mode,
        is_mock=is_mock,
    )
    source_color = MOCK_ORANGE if is_mock is True else MUTED
    draw.text((MARGIN, footer_y + 22), source_line, font=_font(18), fill=source_color)
    draw.text(
        (WIDTH - MARGIN - 190, footer_y + 22),
        "HUMAN PUBLISHED",
        font=_font(16),
        fill=GREEN,
    )
    _draw_paragraph(
        draw,
        conclusion,
        _font(17),
        MARGIN,
        footer_y + 58,
        WIDTH - MARGIN * 2,
        MUTED,
        6,
        HEIGHT - 20,
    )

    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="PNG", optimize=True)
