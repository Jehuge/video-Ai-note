"""Shared Markdown output rules and conservative note cleanup helpers.

The model prompt describes the target shape, while this module removes harmless
formatting noise after generation. It deliberately does not rewrite Markdown
inside fenced code blocks or display-math blocks.
"""

from __future__ import annotations

import re


MARKDOWN_FORMAT_RULES = """Markdown 排版规范（必须遵守）：
1. 只输出 Markdown 正文，不输出解释、前言、结语或代码围栏包裹的整篇文档。
2. 标题只使用 `##` 和 `###` 两级，格式必须是 `## 标题` 或 `### 小节`；`##` 用于主要章节，`###` 用于小节，不要为了每个句子创建标题。
3. 标题、段落、列表、引用、表格、图片和公式块之间最多保留一个空行；禁止连续三个及以上空行。
4. 标题与相邻正文之间必须保留一个空行；普通段落控制在 1-4 行。不要把一句话拆成很多只有几个字的段落，也不要为了强调人为插入空行。
5. 只有确有 LaTeX 公式时才使用 `$...$`/`$$...$$` 交给 KaTeX；普通 Markdown、纯文本表达式、编号或货币符号不要强行包成公式。短公式和单个变量优先使用行内 `$...$`；只有较长公式、关键结论或多步推导使用 `$$...$$`。
6. 连续推导尽量合并为一个 `$$\\begin{aligned} ... \\\\ ... \\\\end{aligned}$$` 块，每行一步；不要连续输出多个只有一行的显示公式。
7. `$$...$$` 内只能放 LaTeX 公式，不能放中文、标题、列表符号、图片或 Markdown 标记。
8. 无序列表统一使用 `- `，有序步骤统一使用 `1. `；同一列表项之间不得插入空行。嵌套列表每深入一级只缩进两个空格，列表项的续行也要保持一致缩进，不要用 Tab 或四空格混排。
9. 只有在确实需要横向比较或展示字段时使用表格；表格列数尽量不超过 5 列，单元格内不要放大段落。
10. 代码必须使用 fenced code block，并标明语言；普通说明不要使用代码块。
11. 图片和时间标记只放在相关小节附近，不要连续重复；保留系统要求的 `*Screenshot-[mm:ss]` 格式。
12. 结尾必须有一个 `## AI 总结` 章节，使用简短列表归纳重点、方法、易错点或行动项。
13. 不输出 `<think>...</think>`、调试信息、模型元话术或“以下是笔记”等套话。
"""


_FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
_HEADING_RE = re.compile(r"^[ \t]{0,3}(#{1,6})(?:[ \t]+(.*?)[ \t]*|[ \t]*)$")
_LIST_RE = re.compile(
    r"^(?P<indent>[ \t]*)(?P<marker>(?:[-+*]|\d+[.)]))"
    r"(?:[ \t]+(?P<content>.*))?$"
)
_THIN_BREAK_RE = re.compile(r"^[ \t]{0,3}(?P<char>[-*_])(?:[ \t]*(?P=char)){2,}[ \t]*$")
_BLOCKQUOTE_RE = re.compile(r"^[ \t]{0,3}(?P<markers>>+(?:[ \t]*>+)*)(?:[ \t]+)?(?P<content>.*)$")
_THINK_OPEN_RE = re.compile(r"<think\b[^>]*>", re.IGNORECASE)
_THINK_CLOSE_RE = re.compile(r"</think\s*>", re.IGNORECASE)


def _strip_think_line(line: str, in_think: bool) -> tuple[str, bool]:
    """Remove model-internal ``<think>`` sections outside protected blocks."""

    pieces: list[str] = []
    cursor = 0
    while cursor < len(line):
        if in_think:
            close = _THINK_CLOSE_RE.search(line, cursor)
            if close is None:
                return "".join(pieces), True
            cursor = close.end()
            in_think = False
            continue

        opening = _THINK_OPEN_RE.search(line, cursor)
        if opening is None:
            pieces.append(line[cursor:])
            break
        pieces.append(line[cursor : opening.start()])
        cursor = opening.end()
        in_think = True

    return "".join(pieces), in_think


def _normalize_heading(line: str, match: re.Match[str]) -> str:
    """Use the two heading levels supported by the note renderer."""

    level = len(match.group(1))
    normalized_level = 2 if level <= 2 else 3
    title = (match.group(2) or "").strip()
    # A trailing ATX marker is decoration, not part of the title. Removing it
    # also prevents inconsistent heading widths in the print stylesheet.
    title = re.sub(r"[ \t]+#+[ \t]*$", "", title)
    return f"{'#' * normalized_level} {title}" if title else "#" * normalized_level


def _indent_width(indent: str) -> int:
    """Expand tabs before comparing list indentation widths."""

    return len(indent.replace("\t", "    "))


def _normalize_list_item(line: str, match: re.Match[str], indent_stack: list[int]) -> str:
    """Canonicalize markers and map each observed indentation increase to one level."""

    width = _indent_width(match.group("indent"))
    if not indent_stack:
        indent_stack.append(width)
    elif width < indent_stack[0]:
        # A smaller indentation starts a new top-level list in the same run.
        indent_stack[:] = [width]
    else:
        while len(indent_stack) > 1 and width < indent_stack[-1]:
            indent_stack.pop()
        if width > indent_stack[-1]:
            indent_stack.append(width)
    depth = len(indent_stack) - 1
    marker = match.group("marker")
    if marker in {"*", "+"}:
        marker = "-"
    elif marker[-1:] == ")":
        marker = marker[:-1] + "."
    content = (match.group("content") or "").strip()
    prefix = "  " * depth
    return f"{prefix}{marker} {content}" if content else f"{prefix}{marker}"


def _normalize_blockquote(line: str, match: re.Match[str]) -> str:
    markers = " ".join(">" for _ in range(match.group("markers").count(">")))
    content = match.group("content").strip()
    return f"{markers} {content}".rstrip()


def _line_kind(line: str) -> str:
    """Classify a non-empty, non-protected Markdown line for block spacing."""

    stripped = line.strip()
    if _HEADING_RE.match(line):
        return "heading"
    if _LIST_RE.match(line) and not _THIN_BREAK_RE.match(line):
        return "list"
    if _BLOCKQUOTE_RE.match(line):
        return "blockquote"
    if stripped.startswith("|") or stripped.endswith("|"):
        return "table"
    if _THIN_BREAK_RE.match(line) or stripped.startswith("!["):
        return "block"
    return "paragraph"


def _needs_blank(previous: str | None, current: str, blank_pending: bool) -> bool:
    """Return whether a single blank line belongs between two block lines."""

    if previous is None:
        return False
    if previous in {"list", "list_continuation"} and current in {"list", "list_continuation"}:
        return False
    if previous == "blockquote" and current == "blockquote":
        return False
    if previous == "table" and current == "table":
        return False
    if previous == "block" and current == "block":
        return False
    if previous == "paragraph" and current == "paragraph":
        return blank_pending
    # Headings, lists, quotes, tables, images, formulas, and code are separate
    # blocks even when the model forgot to insert an empty line.
    return True


def normalize_note_markdown(markdown: str) -> str:
    """Normalize note structure while preserving fenced code and display math.

    LLM output commonly contains ``#``/``####`` headings, mixed list markers,
    tab indentation, and missing blank lines around blocks. Those small syntax
    differences render inconsistently in browsers and PDF print pages, so they
    are canonicalized here. Content inside fenced code and ``$$`` blocks is
    intentionally copied byte-for-byte (apart from line-ending conversion).
    """

    if not markdown:
        return ""

    text = markdown.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    output: list[str] = []
    in_fence = False
    fence_char = ""
    in_math = False
    in_think = False
    blank_pending = False
    previous_kind: str | None = None
    list_indent_stack: list[int] = []
    last_list_depth = 0

    for raw_line in lines:
        # Protected blocks are handled before think-tag stripping so literal
        # tags in source code or LaTeX remain untouched.
        if in_fence:
            output.append(raw_line)
            fence_match = _FENCE_RE.match(raw_line)
            if fence_match and fence_match.group(1)[0] == fence_char:
                in_fence = False
                previous_kind = "protected_end"
            continue

        if in_math:
            output.append(raw_line)
            if raw_line.count("$$") % 2 == 1:
                in_math = False
                previous_kind = "protected_end"
            continue

        line, in_think = _strip_think_line(raw_line, in_think)
        if not line.strip():
            if output and not in_think:
                blank_pending = True
            continue

        line = line.rstrip()
        stripped = line.strip()

        fence_match = _FENCE_RE.match(line)
        if fence_match:
            normalized = stripped
            if _needs_blank(previous_kind, "protected_start", blank_pending):
                output.append("")
            output.append(normalized)
            blank_pending = False
            previous_kind = "protected_start"
            in_fence = True
            fence_char = fence_match.group(1)[0]
            list_indent_stack.clear()
            continue

        delimiter_count = line.count("$$")
        if delimiter_count % 2 == 1:
            if _needs_blank(previous_kind, "protected_start", blank_pending):
                output.append("")
            output.append(stripped)
            blank_pending = False
            previous_kind = "protected_start"
            in_math = True
            list_indent_stack.clear()
            continue

        heading_match = _HEADING_RE.match(line)
        list_match = _LIST_RE.match(line)
        if heading_match:
            normalized = _normalize_heading(line, heading_match)
            kind = "heading"
            list_indent_stack.clear()
        elif list_match and not _THIN_BREAK_RE.match(line):
            if previous_kind not in {"list", "list_continuation"}:
                list_indent_stack.clear()
            normalized = _normalize_list_item(line, list_match, list_indent_stack)
            kind = "list"
            last_list_depth = len(list_indent_stack) - 1
        else:
            blockquote_match = _BLOCKQUOTE_RE.match(line)
            is_list_continuation = (
                previous_kind in {"list", "list_continuation"}
                and not blank_pending
                and not blockquote_match
                and not _HEADING_RE.match(line)
                and not stripped.startswith("|")
                and not stripped.endswith("|")
                and not _THIN_BREAK_RE.match(line)
                and not stripped.startswith("![")
            )
            if is_list_continuation:
                normalized = f"{'  ' * (last_list_depth + 1)}{stripped}"
                kind = "list_continuation"
            elif blockquote_match:
                normalized = _normalize_blockquote(line, blockquote_match)
                kind = "blockquote"
            else:
                # Leading indentation on ordinary prose creates an accidental
                # code block in CommonMark, so prose is always left aligned.
                normalized = stripped
                kind = _line_kind(normalized)
            if kind != "list_continuation":
                list_indent_stack.clear()

        if _needs_blank(previous_kind, kind, blank_pending):
            output.append("")
        output.append(normalized)
        blank_pending = False
        previous_kind = kind

    while output and not output[0].strip():
        output.pop(0)
    while output and not output[-1].strip():
        output.pop()

    return "\n".join(output)
