import tempfile
import unittest
from pathlib import Path

from PIL import Image

from app.services.pdf_export import (
    _FlowableBuilder,
    _build_styles,
    _latex_markup,
    _normalize_math_delimiters,
    _register_fonts,
    _resolve_image_path,
    _safe_text,
    render_note_pdf,
)


class PdfExportTests(unittest.TestCase):
    def test_renders_markdown_directly_to_pdf(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            screenshot_dir = root / "screenshots"
            screenshot_dir.mkdir()
            Image.new("RGBA", (640, 360), (37, 99, 235, 180)).save(
                screenshot_dir / "示例.png"
            )
            output = root / "note.pdf"
            markdown = """# 示例视频

## 中文排版与内联格式

正文包含 **粗体**、*斜体*、~~删除线~~、`inline_code()`、特殊字符 & < >，以及 [安全链接](https://example.com)。

- 一级列表
  - 二级列表
  - [x] 已完成事项

1. 第一步
2. 第二步

> 引用段落保留层级与边界。

```python
def hello(name: str) -> str:
    return f"你好，{name}"
```

| 项目 | 说明 | 数值 |
| --- | --- | ---: |
| 中文 | 一段需要自动换行的较长表格内容 | 123 |

行内公式 $E=mc^2$。

$$
\\begin{aligned}
a &= b + c \\\\
d &= e
\\end{aligned}
$$

![示例截图](/api/note_results/screenshots/%E7%A4%BA%E4%BE%8B.png)
"""

            render_note_pdf(markdown, "示例视频", output, root)

            self.assertTrue(output.is_file())
            self.assertGreater(output.stat().st_size, 5_000)
            self.assertEqual(output.read_bytes()[:5], b"%PDF-")

            try:
                from pypdf import PdfReader
            except ImportError:
                return
            extracted = "\n".join(page.extract_text() or "" for page in PdfReader(output).pages)
            self.assertIn("中文排版", extracted)
            self.assertIn("inline_code", extracted)
            self.assertIn("E=mc", extracted)
            self.assertIn("mc2", extracted.replace(" ", ""))

    def test_image_paths_cannot_escape_note_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            outside = root.parent / f"{root.name}-outside.png"
            outside.write_bytes(b"not-an-image")
            try:
                self.assertIsNone(_resolve_image_path("../outside.png", root))
                self.assertIsNone(_resolve_image_path("https://example.com/a.png", root))
                self.assertIsNone(_resolve_image_path("/etc/passwd", root))
            finally:
                outside.unlink(missing_ok=True)

    def test_math_delimiters_do_not_change_code(self):
        markdown = """```text
\\(fenced_literal\\)
```

`\\(inline_literal\\)` and \\(x^2\\)

    \\[indented_literal\\]
"""

        normalized = _normalize_math_delimiters(markdown)

        self.assertIn("\\(fenced_literal\\)", normalized)
        self.assertIn("`\\(inline_literal\\)`", normalized)
        self.assertIn("    \\[indented_literal\\]", normalized)
        self.assertIn("and $x^2$", normalized)

    def test_math_alphabet_characters_are_not_replaced_as_icons(self):
        self.assertEqual(_safe_text("𝑥 + 𝔸 = 😀"), "x + A = [图标]")

    def test_complex_display_math_uses_vector_layout_when_available(self):
        try:
            from reportlab.graphics.shapes import Drawing
            import ziamath  # noqa: F401
            import svglib  # noqa: F401
        except ImportError:
            self.skipTest("optional vector math renderer is not installed")

        builder = _FlowableBuilder(
            _register_fonts(),
            _build_styles(_register_fonts()),
            Path("."),
        )
        flowable = builder._math_block(
            r"\begin{cases}x^2 & x>0 \\ 0 & x\le 0\end{cases}"
        )
        self.assertIsInstance(flowable, Drawing)
        self.assertGreater(flowable.width, 0)

    def test_vector_math_glyphs_stay_inside_drawing_bounds(self):
        """Regression: svglib used to drop ziamath's <symbol>/<use> viewport
        scaling, drawing every glyph far above the declared formula box."""
        try:
            from reportlab.graphics.shapes import Drawing, Group, Rect
            import ziamath  # noqa: F401
            import svglib  # noqa: F401
        except ImportError:
            self.skipTest("optional vector math renderer is not installed")

        builder = _FlowableBuilder(
            _register_fonts(),
            _build_styles(_register_fonts()),
            Path("."),
        )
        drawing = builder._math_block(
            r"x_1 = \frac{a - \sqrt{a^2-4}}{2}, \quad x_2 = \frac{a + \sqrt{a^2-4}}{2}"
        )
        self.assertIsInstance(drawing, Drawing)

        min_x, min_y = float("inf"), float("inf")
        max_x, max_y = float("-inf"), float("-inf")

        def walk(node, tx=0.0, ty=0.0, sx=1.0, sy=1.0):
            nonlocal min_x, min_y, max_x, max_y
            transform = getattr(node, "transform", None)
            if transform:
                a, b, c, d, e, f = transform
                tx, ty, sx, sy = a * tx + c * ty + e, b * tx + d * ty + f, a * sx, d * sy
            points = getattr(node, "points", None)
            if points:
                for index in range(0, len(points), 2):
                    x, y = points[index] * sx + tx, points[index + 1] * sy + ty
                    min_x, max_x, min_y, max_y = (
                        min(min_x, x), max(max_x, x), min(min_y, y), max(max_y, y),
                    )
            if isinstance(node, Rect):
                x, y = node.x * sx + tx, node.y * sy + ty
                min_x, max_x, min_y, max_y = (
                    min(min_x, x),
                    max(max_x, x + node.width * sx),
                    min(min_y, y),
                    max(max_y, y + node.height * sy),
                )
            if isinstance(node, Group):
                for child in node.contents:
                    walk(child, tx, ty, sx, sy)

        for child in drawing.contents:
            walk(child)

        self.assertGreaterEqual(min_x, -0.5)
        self.assertGreaterEqual(min_y, -0.5)
        self.assertLessEqual(max_x, drawing.width + 0.5)
        self.assertLessEqual(max_y, drawing.height + 0.5)

    def test_inline_latex_becomes_super_subscript_markup(self):
        self.assertEqual(_latex_markup(r"a^2-4"), "a<super>2</super>-4")
        self.assertEqual(_latex_markup(r"x_1"), "x<sub>1</sub>")
        self.assertEqual(_latex_markup(r"b^{n+1}"), "b<super>n+1</super>")
        self.assertEqual(_latex_markup(r"30^{\circ}"), "30°")
        self.assertEqual(_latex_markup(r"\frac{\Delta}{2}\le 0"), "(Δ)/(2)≤ 0")

    def test_cjk_math_falls_back_to_markup_paragraph(self):
        try:
            import ziamath  # noqa: F401
            import svglib  # noqa: F401
        except ImportError:
            self.skipTest("optional vector math renderer is not installed")

        from reportlab.platypus import Paragraph

        builder = _FlowableBuilder(
            _register_fonts(),
            _build_styles(_register_fonts()),
            Path("."),
        )
        flowable = builder._math_block(r"\text{当 } x^2 > 0")
        self.assertIsInstance(flowable, Paragraph)
        self.assertIn("<super>2</super>", flowable.text)


if __name__ == "__main__":
    unittest.main()
