"""Generate selectable-text PDFs directly from Markdown with ReportLab."""

from __future__ import annotations

import base64
import binascii
import html
import logging
import os
import re
import tempfile
import threading
import unicodedata
from dataclasses import dataclass
from datetime import date
from io import BytesIO
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import unquote, urlsplit

import mistune
from mistune.plugins.formatting import strikethrough
from mistune.plugins.math import math
from mistune.plugins.table import table
from mistune.plugins.task_lists import task_lists
from mistune.plugins.url import url
from PIL import Image as PILImage
from PIL import ImageOps, UnidentifiedImageError
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.graphics.shapes import Drawing
from reportlab.platypus import (
    HRFlowable,
    Image,
    ListFlowable,
    ListItem,
    LongTable,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    TableStyle,
)


logger = logging.getLogger(__name__)

_PAGE_WIDTH, _PAGE_HEIGHT = A4
_LEFT_MARGIN = 16 * mm
_RIGHT_MARGIN = 16 * mm
_TOP_MARGIN = 18 * mm
_BOTTOM_MARGIN = 15 * mm
_CONTENT_WIDTH = _PAGE_WIDTH - _LEFT_MARGIN - _RIGHT_MARGIN
_MAX_IMAGE_HEIGHT = 205 * mm
_MAX_IMAGE_BYTES = 30 * 1024 * 1024
_MAX_IMAGE_PIXELS = 50_000_000
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
_NON_BMP = re.compile(r"[\U00010000-\U0010ffff]")
_FONT_LOCK = threading.Lock()
_FONT_CACHE: "_Fonts | None" = None


@dataclass(frozen=True)
class _Fonts:
    regular: str
    bold: str
    mono: str


def _font_candidates() -> list[tuple[Path, Path | None]]:
    custom_regular = os.getenv("PDF_FONT_PATH")
    custom_bold = os.getenv("PDF_BOLD_FONT_PATH")
    candidates: list[tuple[Path, Path | None]] = []
    if custom_regular:
        candidates.append(
            (
                Path(custom_regular).expanduser(),
                Path(custom_bold).expanduser() if custom_bold else None,
            )
        )

    windows_fonts = Path(os.getenv("WINDIR", "C:/Windows")) / "Fonts"
    candidates.extend(
        [
            (windows_fonts / "msyh.ttc", windows_fonts / "msyhbd.ttc"),
            (windows_fonts / "NotoSansSC-VF.ttf", None),
            (Path("/System/Library/Fonts/PingFang.ttc"), None),
            (Path("/System/Library/Fonts/STHeiti Medium.ttc"), None),
            (
                Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
                Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"),
            ),
            (Path("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"), None),
        ]
    )
    return candidates


def _register_fonts() -> _Fonts:
    """Register an embedded CJK font family, with a portable CID fallback."""

    global _FONT_CACHE
    if _FONT_CACHE is not None:
        return _FONT_CACHE

    with _FONT_LOCK:
        if _FONT_CACHE is not None:
            return _FONT_CACHE

        for regular_path, bold_path in _font_candidates():
            if not regular_path.is_file():
                continue
            try:
                regular_name = "VideoNoteCJK"
                bold_name = "VideoNoteCJKBold"
                pdfmetrics.registerFont(TTFont(regular_name, str(regular_path), subfontIndex=0))
                if bold_path and bold_path.is_file():
                    pdfmetrics.registerFont(TTFont(bold_name, str(bold_path), subfontIndex=0))
                else:
                    bold_name = regular_name
                pdfmetrics.registerFontFamily(
                    regular_name,
                    normal=regular_name,
                    bold=bold_name,
                    italic=regular_name,
                    boldItalic=bold_name,
                )
                _FONT_CACHE = _Fonts(regular_name, bold_name, regular_name)
                logger.info("PDF 使用中文字体: %s", regular_path)
                return _FONT_CACHE
            except Exception as exc:
                logger.warning("PDF 字体注册失败 %s: %s", regular_path, exc)

        fallback_name = "STSong-Light"
        if fallback_name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(UnicodeCIDFont(fallback_name))
        pdfmetrics.registerFontFamily(
            fallback_name,
            normal=fallback_name,
            bold=fallback_name,
            italic=fallback_name,
            boldItalic=fallback_name,
        )
        _FONT_CACHE = _Fonts(fallback_name, fallback_name, fallback_name)
        logger.warning("未找到可嵌入的中文字体，PDF 使用 STSong-Light 后备字体")
        return _FONT_CACHE


def _build_styles(fonts: _Fonts) -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    body = ParagraphStyle(
        "NoteBody",
        parent=base["BodyText"],
        fontName=fonts.regular,
        fontSize=10.2,
        leading=16,
        textColor=colors.HexColor("#374151"),
        spaceAfter=6,
        wordWrap="CJK",
    )
    return {
        "body": body,
        "title": ParagraphStyle(
            "NoteTitle",
            parent=body,
            fontName=fonts.bold,
            fontSize=21,
            leading=28,
            textColor=colors.HexColor("#111827"),
            spaceAfter=5,
            keepWithNext=True,
        ),
        "meta": ParagraphStyle(
            "NoteMeta",
            parent=body,
            fontSize=8.5,
            leading=12,
            textColor=colors.HexColor("#94A3B8"),
            spaceAfter=8,
        ),
        "h1": ParagraphStyle(
            "NoteHeading1",
            parent=body,
            fontName=fonts.bold,
            fontSize=17,
            leading=23,
            textColor=colors.HexColor("#111827"),
            spaceBefore=13,
            spaceAfter=6,
            keepWithNext=True,
        ),
        "h2": ParagraphStyle(
            "NoteHeading2",
            parent=body,
            fontName=fonts.bold,
            fontSize=14,
            leading=20,
            textColor=colors.HexColor("#111827"),
            spaceBefore=11,
            spaceAfter=5,
            keepWithNext=True,
        ),
        "h3": ParagraphStyle(
            "NoteHeading3",
            parent=body,
            fontName=fonts.bold,
            fontSize=11.5,
            leading=17,
            textColor=colors.HexColor("#1F2937"),
            spaceBefore=9,
            spaceAfter=4,
            keepWithNext=True,
        ),
        "quote": ParagraphStyle(
            "NoteQuote",
            parent=body,
            leftIndent=10,
            rightIndent=8,
            borderColor=colors.HexColor("#CBD5E1"),
            borderWidth=0.6,
            borderPadding=7,
            backColor=colors.HexColor("#F8FAFC"),
            textColor=colors.HexColor("#475569"),
            spaceBefore=4,
            spaceAfter=7,
        ),
        "code": ParagraphStyle(
            "NoteCode",
            parent=body,
            fontName=fonts.mono,
            fontSize=8.2,
            leading=11.5,
            leftIndent=8,
            rightIndent=8,
            borderColor=colors.HexColor("#E2E8F0"),
            borderWidth=0.5,
            borderPadding=7,
            backColor=colors.HexColor("#F8FAFC"),
            textColor=colors.HexColor("#1F2937"),
            spaceBefore=5,
            spaceAfter=8,
        ),
        "math": ParagraphStyle(
            "NoteMath",
            parent=body,
            fontName=fonts.mono,
            fontSize=9,
            leading=13,
            leftIndent=10,
            rightIndent=10,
            alignment=TA_CENTER,
            borderColor=colors.HexColor("#E2E8F0"),
            borderWidth=0.5,
            borderPadding=7,
            backColor=colors.HexColor("#F8FAFC"),
            spaceBefore=5,
            spaceAfter=8,
        ),
        "table": ParagraphStyle(
            "NoteTableCell",
            parent=body,
            fontSize=8.5,
            leading=12,
            spaceAfter=0,
        ),
        "table_head": ParagraphStyle(
            "NoteTableHead",
            parent=body,
            fontName=fonts.bold,
            fontSize=8.5,
            leading=12,
            textColor=colors.HexColor("#111827"),
            spaceAfter=0,
        ),
        "missing_image": ParagraphStyle(
            "NoteMissingImage",
            parent=body,
            fontSize=8.5,
            leading=12,
            textColor=colors.HexColor("#94A3B8"),
            alignment=TA_CENTER,
            spaceBefore=5,
            spaceAfter=7,
        ),
    }


def _safe_text(value: str) -> str:
    value = _CONTROL_CHARS.sub("", value or "")
    value = value.replace("\ufe0f", "")
    replacements = {
        "⏱": "时间",
        "📷": "截图",
        "📋": "笔记",
        "✅": "[完成]",
        "☑": "[完成]",
        "☐": "[ ]",
    }
    for source, target in replacements.items():
        value = value.replace(source, target)

    def normalize_non_bmp(match: re.Match[str]) -> str:
        char = match.group(0)
        codepoint = ord(char)
        if 0x1F000 <= codepoint <= 0x1FAFF:
            return "[图标]"
        normalized = unicodedata.normalize("NFKC", char)
        return normalized if normalized != char else char

    return _NON_BMP.sub(normalize_non_bmp, value)


def _escape_text(value: str) -> str:
    return html.escape(_safe_text(value), quote=False).replace("\n", " ")


_LATEX_SYMBOLS = {
    "\\Delta": "Δ",
    "\\delta": "δ",
    "\\alpha": "α",
    "\\beta": "β",
    "\\gamma": "γ",
    "\\theta": "θ",
    "\\lambda": "λ",
    "\\mu": "μ",
    "\\pi": "π",
    "\\sigma": "σ",
    "\\phi": "φ",
    "\\omega": "ω",
    "\\leq": "≤",
    "\\le": "≤",
    "\\geq": "≥",
    "\\ge": "≥",
    "\\neq": "≠",
    "\\ne": "≠",
    "\\approx": "≈",
    "\\times": "×",
    "\\cdot": "·",
    "\\pm": "±",
    "\\infty": "∞",
    "\\rightarrow": "→",
    "\\to": "→",
    "\\Rightarrow": "⇒",
    "\\in": "∈",
    "\\notin": "∉",
    "\\sum": "Σ",
    "\\circ": "∘",
    "\\cdots": "⋯",
    "\\ldots": "…",
    "\\dots": "…",
    "\\prime": "′",
}


def _latex_to_text(value: str) -> str:
    """Make common LaTeX readable while retaining unknown commands verbatim."""

    text = _safe_text(value)
    text = text.replace("\\left", "").replace("\\right", "")
    text = re.sub(r"\\(?:middle|displaystyle|limits|nolimits)\b", "", text)
    text = re.sub(r"\^\{?\\circ\}?", "°", text)
    for _ in range(4):
        updated = re.sub(
            r"\\(?:d|t)?frac\{([^{}]*)\}\{([^{}]*)\}",
            r"(\1)/(\2)",
            text,
        )
        if updated == text:
            break
        text = updated
    text = re.sub(r"\\sqrt\{([^{}]*)\}", r"√(\1)", text)
    text = re.sub(
        r"\\(?:text|mathrm|mathbf|operatorname)\{([^{}]*)\}",
        r"\1",
        text,
    )
    for source, target in sorted(_LATEX_SYMBOLS.items(), key=lambda item: -len(item[0])):
        text = re.sub(rf"{re.escape(source)}(?![A-Za-z])", target, text)
    text = re.sub(r"\^\{([^{}])\}", r"^\1", text)
    text = re.sub(r"_\{([^{}])\}", r"_\1", text)
    text = re.sub(r"\\(?:quad|qquad)\b", " ", text)
    text = re.sub(r"\\[,;!]", " ", text)
    return text.replace("\\{", "{").replace("\\}", "}").strip()


def _latex_markup(value: str, line_breaks: bool = False) -> str:
    """Convert common LaTeX to paragraph XML with real super/subscripts.

    ``_latex_to_text`` output still carries ``^``/``_`` markers; ReportLab's
    ``<super>``/``<sub>`` tags render them as raised/lowered text instead.
    """

    text = html.escape(_latex_to_text(value), quote=False)
    text = re.sub(r"\^\{([^{}]*)\}", r"<super>\1</super>", text)
    text = re.sub(r"_\{([^{}]*)\}", r"<sub>\1</sub>", text)
    text = re.sub(r"\^(\w)", r"<super>\1</super>", text)
    text = re.sub(r"_([\w)\]])", r"<sub>\1</sub>", text)
    text = text.replace("\n", "<br/>" if line_breaks else " ")
    return text.strip()


def _safe_link(url: str) -> str | None:
    cleaned = _CONTROL_CHARS.sub("", (url or "").strip())
    if urlsplit(cleaned).scheme.lower() not in {"http", "https", "mailto"}:
        return None
    return cleaned


def _inline_xml(tokens: list[dict[str, Any]], fonts: _Fonts) -> str:
    parts: list[str] = []
    for token in tokens:
        token_type = token.get("type", "")
        children = token.get("children") or []
        if token_type == "text":
            parts.append(_escape_text(token.get("raw", "")))
        elif token_type == "softbreak":
            parts.append(" ")
        elif token_type in {"linebreak", "hardbreak"}:
            parts.append("<br/>")
        elif token_type == "strong":
            parts.append(f"<b>{_inline_xml(children, fonts)}</b>")
        elif token_type == "emphasis":
            parts.append(f"<i>{_inline_xml(children, fonts)}</i>")
        elif token_type == "strikethrough":
            parts.append(f"<strike>{_inline_xml(children, fonts)}</strike>")
        elif token_type == "codespan":
            code = _escape_text(token.get("raw", ""))
            parts.append(f'<font name="{fonts.mono}" color="#0F172A">{code}</font>')
        elif token_type == "inline_math":
            parts.append(
                f'<font name="{fonts.mono}" color="#334155">'
                f"{_latex_markup(token.get('raw', ''))}</font>"
            )
        elif token_type == "link":
            label = _inline_xml(children, fonts)
            url = _safe_link((token.get("attrs") or {}).get("url", ""))
            if url:
                parts.append(
                    f'<link href="{html.escape(url, quote=True)}" color="#2563EB">{label}</link>'
                )
            else:
                parts.append(label)
        elif token_type == "image":
            alt = _plain_text(token).strip() or "图片"
            parts.append(f"[{_escape_text(alt)}]")
        elif token_type in {"inline_html", "raw_html"}:
            parts.append(_escape_text(token.get("raw", "")))
        elif children:
            parts.append(_inline_xml(children, fonts))
        elif token.get("raw"):
            parts.append(_escape_text(str(token["raw"])))
    return "".join(parts).strip()


def _plain_text(token: dict[str, Any]) -> str:
    if token.get("children"):
        return "".join(_plain_text(child) for child in token["children"])
    return _safe_text(str(token.get("raw", "")))


def _resolve_image_path(source: str, image_root: Path) -> Path | None:
    parsed = urlsplit(source)
    if parsed.scheme or parsed.netloc:
        return None

    normalized = unquote(parsed.path).replace("\\", "/")
    prefixes = (
        "/api/note_results/screenshots/",
        "/static/screenshots/",
        "/screenshots/",
    )
    relative: PurePosixPath
    for prefix in prefixes:
        if normalized.startswith(prefix):
            relative = PurePosixPath("screenshots") / normalized[len(prefix) :]
            break
    else:
        if normalized.startswith("/"):
            return None
        relative = PurePosixPath(normalized)

    if not relative.parts or any(part in {"", ".", ".."} for part in relative.parts):
        return None

    root = image_root.resolve()
    candidate = root.joinpath(*relative.parts).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    return candidate if candidate.is_file() else None


def _image_bytes(source: str, image_root: Path) -> bytes | None:
    if source.startswith("data:"):
        # Reject oversized payloads before regex copies and base64 decoding.
        max_encoded_size = ((_MAX_IMAGE_BYTES + 2) // 3) * 4 + 1024
        if len(source) > max_encoded_size:
            return None
        match = re.fullmatch(
            r"data:image/(?:png|jpe?g|webp|gif);base64,([A-Za-z0-9+/=\s]+)",
            source,
            flags=re.IGNORECASE,
        )
        if not match:
            return None
        try:
            data = base64.b64decode(re.sub(r"\s+", "", match.group(1)), validate=True)
        except (binascii.Error, ValueError):
            return None
        return data if len(data) <= _MAX_IMAGE_BYTES else None

    path = _resolve_image_path(source, image_root)
    if path is None or path.stat().st_size > _MAX_IMAGE_BYTES:
        return None
    return path.read_bytes()


def _make_image(
    source: str,
    alt: str,
    image_root: Path,
    styles: dict[str, ParagraphStyle],
    buffers: list[BytesIO],
) -> list[Any]:
    data = _image_bytes(source, image_root)
    if data is None:
        label = (alt.strip() or Path(urlsplit(source).path).name or "图片")[:120]
        logger.warning("PDF 跳过不可用图片: %s", source[:160])
        return [Paragraph(f"[图片不可用: {_escape_text(label)}]", styles["missing_image"])]

    try:
        with PILImage.open(BytesIO(data)) as opened:
            width, height = opened.size
            if width <= 0 or height <= 0 or width * height > _MAX_IMAGE_PIXELS:
                raise ValueError("图片尺寸无效或像素过大")
            image = ImageOps.exif_transpose(opened)
            image.thumbnail((2400, 2400))
            has_alpha = image.mode in {"RGBA", "LA"} or (
                image.mode == "P" and "transparency" in image.info
            )
            converted = image.convert("RGBA" if has_alpha else "RGB")
            buffer = BytesIO()
            if has_alpha:
                converted.save(buffer, format="PNG", optimize=True)
            else:
                converted.save(buffer, format="JPEG", quality=90, optimize=True)
            pixel_width, pixel_height = converted.size
        buffer.seek(0)
    except (PILImage.DecompressionBombError, UnidentifiedImageError, OSError, ValueError) as exc:
        logger.warning("PDF 图片解码失败 %s: %s", source[:160], exc)
        label = alt.strip() or "图片"
        return [Paragraph(f"[图片不可用: {_escape_text(label)}]", styles["missing_image"])]

    width_points = pixel_width * 0.75
    height_points = pixel_height * 0.75
    scale = min(
        1.0,
        _CONTENT_WIDTH / max(width_points, 1),
        _MAX_IMAGE_HEIGHT / max(height_points, 1),
    )
    flowable = Image(
        buffer,
        width=width_points * scale,
        height=height_points * scale,
    )
    flowable.hAlign = "CENTER"
    flowable.spaceBefore = 5
    flowable.spaceAfter = 7
    buffers.append(buffer)
    return [flowable]


class _FlowableBuilder:
    def __init__(self, fonts: _Fonts, styles: dict[str, ParagraphStyle], image_root: Path):
        self.fonts = fonts
        self.styles = styles
        self.image_root = image_root
        self.image_buffers: list[BytesIO] = []

    def render(self, tokens: list[dict[str, Any]]) -> list[Any]:
        flowables: list[Any] = []
        for token in tokens:
            token_type = token.get("type", "")
            if token_type == "blank_line":
                continue
            if token_type == "heading":
                level = int((token.get("attrs") or {}).get("level", 2))
                style = self.styles["h1" if level <= 1 else "h2" if level == 2 else "h3"]
                text = _inline_xml(token.get("children") or [], self.fonts)
                if text:
                    flowables.append(Paragraph(text, style))
            elif token_type in {"paragraph", "block_text"}:
                flowables.extend(self._paragraph(token, self.styles["body"]))
            elif token_type == "block_quote":
                flowables.extend(self._quote(token))
            elif token_type == "list":
                rendered_list = self._list(token)
                if rendered_list is not None:
                    flowables.append(rendered_list)
            elif token_type == "block_code":
                code = _safe_text(token.get("raw", "")).rstrip("\n") or " "
                flowables.append(
                    Preformatted(
                        code,
                        self.styles["code"],
                        maxLineLength=92,
                        splitChars=" .,:;+-_/\\",
                        newLineChars="-> ",
                    )
                )
            elif token_type == "block_math":
                formula = _safe_text(token.get("raw", "")).strip() or " "
                flowables.append(self._math_block(formula))
            elif token_type == "table":
                table = self._table(token)
                if table is not None:
                    flowables.append(table)
            elif token_type == "thematic_break":
                flowables.extend(
                    [
                        Spacer(1, 3),
                        HRFlowable(
                            width="100%",
                            thickness=0.6,
                            color=colors.HexColor("#CBD5E1"),
                            spaceBefore=4,
                            spaceAfter=7,
                        ),
                    ]
                )
            elif token_type in {"block_html", "raw_html"}:
                raw = _escape_text(token.get("raw", "")).strip()
                if raw:
                    flowables.append(Paragraph(raw, self.styles["body"]))
            elif token.get("children"):
                flowables.extend(self.render(token["children"]))
        return flowables

    def _math_block(self, formula: str) -> Any:
        """Render display math as vector paths, with a selectable fallback."""

        fallback = _latex_markup(
            formula.replace("\\\\", "\n").replace("&=", "="),
            line_breaks=True,
        ).strip() or " "
        try:
            # STIXTwoMath intentionally handles the layout of fractions,
            # radicals, matrices, cases, and aligned equations. Chinese text
            # inside \text{} is outside that font's coverage, so keep the
            # readable fallback for those expressions.
            if re.search(r"[\u3400-\u9fff]", formula):
                raise ValueError("CJK text in formula")
            import ziamath
            from svglib.svglib import svg2rlg

            # ziamath's SVG2 output references glyphs via <symbol>/<use>, but
            # svglib ignores the symbol viewBox-to-<use> width/height scaling,
            # drawing every glyph far outside the formula box. SVG 1.1 output
            # inlines positioned <path> elements, which svglib handles correctly.
            ziamath.config.svg2 = False
            expression = ziamath.Latex(formula, size=13, color="#334155")
            drawing = svg2rlg(BytesIO(expression.svg().encode("utf-8")))
            if not isinstance(drawing, Drawing) or drawing.width <= 0 or drawing.height <= 0:
                raise ValueError("公式 SVG 为空")
            max_width = max(1.0, _CONTENT_WIDTH - 18)
            scale = min(1.0, max_width / drawing.width)
            if scale < 1.0:
                original_width, original_height = drawing.width, drawing.height
                drawing.scale(scale, scale)
                drawing.width = original_width * scale
                drawing.height = original_height * scale
            drawing.hAlign = "CENTER"
            return drawing
        except Exception as exc:
            logger.warning("公式矢量渲染失败，使用文本后备: %s", exc)
            return Paragraph(fallback, self.styles["math"])

    def _paragraph(
        self,
        token: dict[str, Any],
        style: ParagraphStyle,
        prefix: str = "",
    ) -> list[Any]:
        flowables: list[Any] = []
        inline_tokens: list[dict[str, Any]] = []

        def flush() -> None:
            text = _inline_xml(inline_tokens, self.fonts)
            if prefix and not flowables:
                text = f"{_escape_text(prefix)}{text}"
            if text:
                flowables.append(Paragraph(text, style))
            inline_tokens.clear()

        for child in token.get("children") or []:
            if child.get("type") == "image":
                flush()
                attrs = child.get("attrs") or {}
                flowables.extend(
                    _make_image(
                        attrs.get("url", ""),
                        _plain_text(child),
                        self.image_root,
                        self.styles,
                        self.image_buffers,
                    )
                )
            else:
                inline_tokens.append(child)
        flush()
        return flowables

    def _quote(self, token: dict[str, Any]) -> list[Any]:
        result: list[Any] = []
        for child in token.get("children") or []:
            if child.get("type") in {"paragraph", "block_text"}:
                result.extend(self._paragraph(child, self.styles["quote"]))
            elif child.get("type") == "list":
                rendered = self._list(child)
                if rendered is not None:
                    result.append(rendered)
            else:
                result.extend(self.render([child]))
        return result

    def _list(self, token: dict[str, Any]) -> ListFlowable | None:
        ordered = bool((token.get("attrs") or {}).get("ordered"))
        items: list[ListItem] = []
        for item in token.get("children") or []:
            checked = (item.get("attrs") or {}).get("checked")
            prefix = "[完成] " if checked is True else "[ ] " if checked is False else ""
            item_flowables: list[Any] = []
            for child in item.get("children") or []:
                if child.get("type") in {"paragraph", "block_text"}:
                    item_flowables.extend(
                        self._paragraph(
                            child,
                            self.styles["body"],
                            prefix=prefix if not item_flowables else "",
                        )
                    )
                elif child.get("type") == "list":
                    nested = self._list(child)
                    if nested is not None:
                        item_flowables.append(nested)
                else:
                    item_flowables.extend(self.render([child]))
            if not item_flowables:
                item_flowables.append(Paragraph(_escape_text(prefix or " "), self.styles["body"]))
            items.append(ListItem(item_flowables, leftIndent=0, spaceAfter=1))

        if not items:
            return None
        attrs = token.get("attrs") or {}
        return ListFlowable(
            items,
            bulletType="1" if ordered else "bullet",
            start=attrs.get("start", 1) if ordered else "circle",
            leftIndent=18,
            bulletIndent=3,
            bulletFontName=self.fonts.regular,
            bulletFontSize=8.5,
            bulletColor=colors.HexColor("#64748B"),
            spaceBefore=2,
            spaceAfter=5,
        )

    def _table(self, token: dict[str, Any]) -> LongTable | None:
        rows: list[list[dict[str, Any]]] = []
        header_rows = 0
        for section in token.get("children") or []:
            if section.get("type") == "table_head":
                rows.append(section.get("children") or [])
                header_rows = 1
            elif section.get("type") == "table_body":
                for row in section.get("children") or []:
                    rows.append(row.get("children") or [])
        rows = [row for row in rows if row]
        if not rows:
            return None

        column_count = max(len(row) for row in rows)
        data: list[list[Paragraph]] = []
        display_widths = [4] * column_count
        alignments: dict[tuple[int, int], str] = {}
        for row_index, row in enumerate(rows):
            rendered_row: list[Paragraph] = []
            for column_index in range(column_count):
                cell = row[column_index] if column_index < len(row) else {"children": []}
                text = _inline_xml(cell.get("children") or [], self.fonts)
                plain = _plain_text(cell)
                display_widths[column_index] = max(
                    display_widths[column_index],
                    min(36, sum(2 if ord(char) > 255 else 1 for char in plain)),
                )
                style = self.styles["table_head" if row_index < header_rows else "table"]
                rendered_row.append(Paragraph(text or " ", style))
                alignment = (cell.get("attrs") or {}).get("align")
                if alignment in {"left", "center", "right"}:
                    alignments[(column_index, row_index)] = alignment.upper()
            data.append(rendered_row)

        if column_count >= 8:
            column_widths = [_CONTENT_WIDTH / column_count] * column_count
        else:
            minimum = min(52.0, _CONTENT_WIDTH / column_count)
            available = max(0.0, _CONTENT_WIDTH - minimum * column_count)
            total_weight = sum(display_widths)
            column_widths = [
                minimum + available * width / total_weight for width in display_widths
            ]

        commands: list[tuple[Any, ...]] = [
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("GRID", (0, 0), (-1, -1), 0.45, colors.HexColor("#CBD5E1")),
            (
                "ROWBACKGROUNDS",
                (0, header_rows),
                (-1, -1),
                [colors.white, colors.HexColor("#F8FAFC")],
            ),
        ]
        if header_rows:
            commands.append(("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E2E8F0")))
        for (column_index, row_index), alignment in alignments.items():
            commands.append(
                ("ALIGN", (column_index, row_index), (column_index, row_index), alignment)
            )

        return LongTable(
            data,
            colWidths=column_widths,
            repeatRows=header_rows,
            splitByRow=1,
            splitInRow=1,
            hAlign="LEFT",
            style=TableStyle(commands),
            spaceBefore=5,
            spaceAfter=8,
        )


def _normalize_math_delimiters(markdown_text: str) -> str:
    """Convert TeX delimiters without changing fenced, indented, or inline code."""

    output: list[str] = []
    fence_char = ""
    fence_length = 0
    inline_ticks = 0

    for line in markdown_text.splitlines(keepends=True):
        fence_match = re.match(r"^ {0,3}(`{3,}|~{3,})", line)
        if fence_char:
            output.append(line)
            if re.match(
                rf"^ {{0,3}}{re.escape(fence_char)}{{{fence_length},}}[ \t]*(?:\r?\n)?$",
                line,
            ):
                fence_char = ""
                fence_length = 0
            continue
        if fence_match and not inline_ticks:
            marker = fence_match.group(1)
            fence_char = marker[0]
            fence_length = len(marker)
            output.append(line)
            continue
        if not inline_ticks and (line.startswith("    ") or line.startswith("\t")):
            output.append(line)
            continue

        converted: list[str] = []
        index = 0
        while index < len(line):
            if line[index] == "`":
                end = index + 1
                while end < len(line) and line[end] == "`":
                    end += 1
                run_length = end - index
                if inline_ticks == 0:
                    inline_ticks = run_length
                elif inline_ticks == run_length:
                    inline_ticks = 0
                converted.append(line[index:end])
                index = end
                continue
            if not inline_ticks and (index == 0 or line[index - 1] != "\\"):
                marker = line[index : index + 2]
                if marker in {r"\(", r"\)"}:
                    converted.append("$")
                    index += 2
                    continue
                if marker in {r"\[", r"\]"}:
                    converted.append("$$")
                    index += 2
                    continue
            converted.append(line[index])
            index += 1
        output.append("".join(converted))

    return "".join(output)


def _markdown_tokens(markdown_text: str) -> list[dict[str, Any]]:
    markdown_text = _normalize_math_delimiters(markdown_text)
    parser = mistune.create_markdown(
        renderer="ast",
        plugins=[table, strikethrough, task_lists, math, url],
    )
    return parser(markdown_text)


def _normalized_title(value: str) -> str:
    return re.sub(r"[\s\W_]+", "", value or "", flags=re.UNICODE).casefold()


def _drop_duplicate_heading(tokens: list[dict[str, Any]], title: str) -> list[dict[str, Any]]:
    first_index = next(
        (index for index, token in enumerate(tokens) if token.get("type") != "blank_line"),
        None,
    )
    if first_index is None or tokens[first_index].get("type") != "heading":
        return tokens
    heading = _plain_text(tokens[first_index])
    normalized_heading = _normalized_title(heading)
    normalized_title = _normalized_title(title)
    if normalized_heading and (
        normalized_heading == normalized_title
        or normalized_heading in normalized_title
        or normalized_title in normalized_heading
    ):
        return tokens[:first_index] + tokens[first_index + 1 :]
    return tokens


def _draw_footer(canvas: Any, document: SimpleDocTemplate, fonts: _Fonts) -> None:
    canvas.saveState()
    canvas.setFont(fonts.regular, 8)
    canvas.setFillColor(colors.HexColor("#94A3B8"))
    canvas.drawCentredString(_PAGE_WIDTH / 2, 8 * mm, f"{document.page}")
    canvas.restoreState()


def render_note_pdf(
    markdown_text: str,
    title: str,
    output_path: Path,
    image_root: Path,
) -> None:
    """Write one Markdown note as a PDF without a browser or frontend server.

    Mistune parses Markdown into an AST and ReportLab lays it out as native PDF
    text. Display math is drawn as vector paths via ziamath; inline math and
    any formula that fails vector rendering become readable text with real
    superscripts/subscripts, and unknown commands remain visible/selectable.
    """

    if not markdown_text or not markdown_text.strip():
        raise ValueError("笔记内容为空")

    fonts = _register_fonts()
    styles = _build_styles(fonts)
    tokens = _drop_duplicate_heading(_markdown_tokens(markdown_text), title)
    builder = _FlowableBuilder(fonts, styles, Path(image_root))
    safe_title = _safe_text(title).strip() or "笔记"
    story: list[Any] = [
        Paragraph(_escape_text(safe_title), styles["title"]),
        Paragraph(f"AI 视频笔记　{date.today().isoformat()}", styles["meta"]),
        HRFlowable(
            width="100%",
            thickness=1.1,
            color=colors.HexColor("#334155"),
            spaceAfter=10,
        ),
    ]
    story.extend(builder.render(tokens))

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix=f".{output_path.stem}.",
            suffix=".pdf",
            dir=output_path.parent,
            delete=False,
        ) as temp_file:
            temp_path = Path(temp_file.name)

        document = SimpleDocTemplate(
            str(temp_path),
            pagesize=A4,
            rightMargin=_RIGHT_MARGIN,
            leftMargin=_LEFT_MARGIN,
            topMargin=_TOP_MARGIN,
            bottomMargin=_BOTTOM_MARGIN,
            title=safe_title,
            author="Video AI Note",
            subject="AI 视频笔记",
            allowSplitting=True,
        )

        footer = lambda canvas, doc: _draw_footer(canvas, doc, fonts)
        document.build(story, onFirstPage=footer, onLaterPages=footer)
        os.replace(temp_path, output_path)
        temp_path = None
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
