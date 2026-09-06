import unittest

from app.services.note_format import normalize_note_markdown


class NoteFormatTests(unittest.TestCase):
    def test_collapses_blank_lines_and_trims_edges(self):
        source = "\n\n## 标题\n\n\n正文\n\n\n## AI 总结\n\n"

        self.assertEqual(
            normalize_note_markdown(source),
            "## 标题\n\n正文\n\n## AI 总结",
        )

    def test_preserves_blank_lines_inside_fenced_code(self):
        source = "## 示例\n\n```python\n第一行\n\n第三行\n```\n\n正文"

        self.assertEqual(
            normalize_note_markdown(source),
            source,
        )

    def test_preserves_display_math_block_contents(self):
        source = "## 推导\n\n$$\n\\begin{aligned}\na &= b \\\\\n\\\\\nc &= d\n\\end{aligned}\n$$\n\n结论"

        self.assertEqual(
            normalize_note_markdown(source),
            source,
        )

    def test_removes_think_blocks(self):
        source = "前文\n\n<think>内部推理\n不应出现</think>\n\n后文"

        self.assertEqual(normalize_note_markdown(source), "前文\n\n后文")

    def test_normalizes_heading_levels_and_list_indentation(self):
        source = (
            "# 主标题\n"
            "正文\n"
            "#### 小节 ###\n"
            "* 父项\n"
            "    + 子项\n"
            "        1) 第一步\n"
            "- 第二项"
        )

        self.assertEqual(
            normalize_note_markdown(source),
            "## 主标题\n\n"
            "正文\n\n"
            "### 小节\n\n"
            "- 父项\n"
            "  - 子项\n"
            "    1. 第一步\n"
            "- 第二项",
        )

    def test_adds_block_spacing_but_keeps_list_items_together(self):
        source = "## 标题\n段落\n- 一项\n\n\n- 二项\n\n下一段"

        self.assertEqual(
            normalize_note_markdown(source),
            "## 标题\n\n"
            "段落\n\n"
            "- 一项\n"
            "- 二项\n\n"
            "下一段",
        )

    def test_indents_lazy_list_continuation_lines(self):
        source = "- 父项\n说明文字仍属于父项\n  - 子项\n子项说明\n\n正文"

        self.assertEqual(
            normalize_note_markdown(source),
            "- 父项\n"
            "  说明文字仍属于父项\n"
            "  - 子项\n"
            "    子项说明\n\n"
            "正文",
        )

    def test_preserves_think_tags_inside_protected_blocks(self):
        source = (
            "## 代码\n\n"
            "```text\n"
            "<think>保留</think>\n"
            "\n"
            "````\n\n"
            "$$\n"
            "<think>保留</think>\n"
            "$$\n\n"
            "正文"
        )

        self.assertEqual(normalize_note_markdown(source), source)


if __name__ == "__main__":
    unittest.main()
