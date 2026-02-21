"""Render a CandidateRule as a styled PNG image for video generation."""

from __future__ import annotations

import io
from typing import TYPE_CHECKING

from PIL import Image, ImageDraw, ImageFont
from pygments.lexers import PythonLexer
from pygments.token import Token

if TYPE_CHECKING:
    from code_ruler.llm.schemas import CandidateRule

# Monokai-inspired token colours
_TOKEN_COLORS: dict[Token, str] = {
    Token.Keyword: "#f92672",
    Token.Keyword.Namespace: "#f92672",
    Token.Name.Function: "#a6e22e",
    Token.Name.Class: "#a6e22e",
    Token.Name.Decorator: "#a6e22e",
    Token.Literal.String: "#e6db74",
    Token.Literal.String.Doc: "#e6db74",
    Token.Literal.String.Single: "#e6db74",
    Token.Literal.String.Double: "#e6db74",
    Token.Literal.Number: "#ae81ff",
    Token.Literal.Number.Integer: "#ae81ff",
    Token.Comment: "#75715e",
    Token.Comment.Single: "#75715e",
    Token.Operator: "#f92672",
    Token.Name.Builtin: "#66d9ef",
    Token.Name: "#f8f8f2",
    Token.Text: "#f8f8f2",
}

_BG_COLOR = "#1e1e2e"
_TEXT_COLOR = "#f8f8f2"
_RED_ACCENT = "#ff5555"
_GREEN_ACCENT = "#50fa7b"
_LEXER = PythonLexer()


def _get_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Try to load a monospace TTF; fall back to Pillow's default font."""
    import shutil

    mono_candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
        "/usr/share/fonts/TTF/DejaVuSansMono.ttf",
        "/System/Library/Fonts/Menlo.ttc",
    ]
    for path in mono_candidates:
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            continue

    # Try fc-match on Linux
    fc = shutil.which("fc-match")
    if fc:
        import subprocess

        result = subprocess.run(
            ["fc-match", "--format=%{file}", "monospace"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0 and result.stdout:
            try:
                return ImageFont.truetype(result.stdout.strip(), size)
            except (OSError, IOError):
                pass

    return ImageFont.load_default()


def _draw_code_block(
    draw: ImageDraw.ImageDraw,
    code: str,
    x: int,
    y: int,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    max_width: int,
) -> int:
    """Draw syntax-highlighted code and return the new y position."""
    line_height = font.size if hasattr(font, "size") else 14
    line_height = int(line_height * 1.4)

    for line in code.split("\n"):
        cx = x
        tokens = list(_LEXER.get_tokens(line))
        for tok_type, tok_value in tokens:
            color = _TEXT_COLOR
            parent = tok_type
            while parent is not Token:
                if parent in _TOKEN_COLORS:
                    color = _TOKEN_COLORS[parent]
                    break
                parent = parent.parent
            bbox = font.getbbox(tok_value)
            tw = bbox[2] - bbox[0]
            if cx + tw > x + max_width:
                break
            draw.text((cx, y), tok_value, fill=color, font=font)
            cx += tw
        y += line_height

    return y


def render_rule_image(
    rule: CandidateRule,
    width: int = 1280,
    height: int = 720,
) -> bytes:
    """Render a CandidateRule as a styled PNG image.

    Returns PNG bytes suitable for Minimax I2V first-frame input.
    """
    img = Image.new("RGB", (width, height), _BG_COLOR)
    draw = ImageDraw.Draw(img)

    title_font = _get_font(28)
    label_font = _get_font(20)
    code_font = _get_font(16)

    padding = 40
    y = padding

    # Title
    draw.text((padding, y), rule.title, fill=_TEXT_COLOR, font=title_font)
    y += 50

    # Slug + severity line
    meta = f"{rule.slug}  |  {rule.severity.upper()}  |  {rule.category}"
    draw.text((padding, y), meta, fill="#888888", font=label_font)
    y += 40

    code_max_width = width - padding * 2 - 20
    section_height = (height - y - padding) // 2 - 10

    # BAD section
    if rule.negative_example:
        draw.text((padding, y), "BAD", fill=_RED_ACCENT, font=label_font)
        y += 30
        draw.line([(padding, y), (padding + 60, y)], fill=_RED_ACCENT, width=2)
        y += 10
        y_end = _draw_code_block(
            draw, rule.negative_example, padding + 10, y, code_font, code_max_width
        )
        y = max(y_end, y + section_height)

    # GOOD section
    if rule.positive_example:
        draw.text((padding, y), "GOOD", fill=_GREEN_ACCENT, font=label_font)
        y += 30
        draw.line([(padding, y), (padding + 60, y)], fill=_GREEN_ACCENT, width=2)
        y += 10
        _draw_code_block(
            draw, rule.positive_example, padding + 10, y, code_font, code_max_width
        )

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
