# -*- coding: utf-8 -*-
"""
自定义笔记风格管理

内置风格保留在代码里（simple/detailed/academic/creative），
用户自定义风格持久化到应用数据目录的 note_styles.json。
自定义风格的 prompt 是"风格指令"片段，会被注入到笔记生成的提示词模板中。
"""

import json
import os
import threading
import uuid
from pathlib import Path
from typing import Dict, List, Optional

from app.utils.logger import get_logger

logger = get_logger(__name__)

_lock = threading.Lock()

# 内置风格：id -> (名称, 图标, 风格指令英文版/最终提示词用)
BUILTIN_STYLES: List[Dict] = [
    {
        "id": "simple",
        "name": "简洁模式",
        "icon": "✨",
        "builtin": True,
        "prompt": (
            "Style: concise mode.\n"
            "- Focus on key points and remove redundant filler.\n"
            "- Use short paragraphs and bullets.\n"
            "- Keep core concepts, conclusions, and steps."
        ),
    },
    {
        "id": "detailed",
        "name": "详细模式",
        "icon": "📋",
        "builtin": True,
        "prompt": (
            "Style: detailed mode.\n"
            "- Keep examples, data, parameters, and concrete steps from the video.\n"
            "- Explain key concepts deeply enough that the note can replace rewatching.\n"
            "- Use clear headings and lists."
        ),
    },
    {
        "id": "academic",
        "name": "学术模式",
        "icon": "🎓",
        "builtin": True,
        "prompt": (
            "Style: academic mode.\n"
            "- Use formal, objective language.\n"
            "- Emphasize causality, argumentation, evidence, and terminology.\n"
            "- Organize content as background, core points, evidence, and conclusion."
        ),
    },
    {
        "id": "creative",
        "name": "创意模式",
        "icon": "🎨",
        "builtin": True,
        "prompt": (
            "Style: creative mode.\n"
            "- Make the note readable and vivid without losing facts.\n"
            "- Highlight key moments, insights, and takeaways.\n"
            "- Use expressive but still structured headings."
        ),
    },
    {
        "id": "hs_math",
        "name": "高中数学",
        "icon": "📐",
        "builtin": True,
        "prompt": (
            "Style: senior high school math timeline note.\n"
            "- 笔记以视频时间线为主轴：严格按板书页顺序逐页梳理，不按课本章节重新组织。\n"
            "- 每一页板书按「本页主题 → 板书原样（题目必须一字不漏完整保留，公式 LaTeX）→ 老师讲解与推导步骤 → 易错点」展开。\n"
            "- 例题必须完整：题干、条件、问法、解题步骤全保留，不跳步、不省略。\n"
            "- 老师口头强调的重点（必考、高考常考）单独标注。\n"
            "- 结尾「AI 总结」：方法清单、例题套路、易错点汇总、考点提示。"
        ),
    },
    {
        "id": "hs_physics",
        "name": "高中物理",
        "icon": "⚛️",
        "builtin": True,
        "prompt": (
            "Style: senior high school physics timeline note.\n"
            "- 笔记以视频时间线为主轴：按板书页顺序逐页梳理。\n"
            "- 每一页板书按「物理模型与情景 → 板书原样（公式注明适用条件与单位，LaTeX）→ 解题步骤模板 → 变式与易错点」展开。\n"
            "- 实验完整保留：目的、器材、步骤、数据表格、误差分析。\n"
            "- 受力分析、过程分析用编号列步骤。\n"
            "- 结尾「AI 总结」：公式速查表（公式|各量含义与单位|适用条件）、模型清单、易错点。"
        ),
    },
    {
        "id": "hs_chemistry",
        "name": "高中化学",
        "icon": "🧪",
        "builtin": True,
        "prompt": (
            "Style: senior high school chemistry timeline note.\n"
            "- 笔记以视频时间线为主轴：按板书页顺序逐页梳理。\n"
            "- 每一页板书按「物质/反应主题 → 板书原样（方程式配平、条件、↑↓符号、离子方程式）→ 实验现象与操作 → 易混点对比表」展开。\n"
            "- 方程式必须规范完整，实验安全注意事项单独标注。\n"
            "- 结尾「AI 总结」：方程式清单、易混概念对比、考点提示。"
        ),
    },
    {
        "id": "hs_biology",
        "name": "高中生物",
        "icon": "🧬",
        "builtin": True,
        "prompt": (
            "Style: senior high school biology timeline note.\n"
            "- 笔记以视频时间线为主轴：按板书页顺序逐页梳理。\n"
            "- 每一页板书按「核心概念（教材规范表述）→ 过程拆解（分步骤：场所、条件、产物）→ 文字流程图 → 易混点对比表」展开。\n"
            "- 板书里的图示（细胞结构、生理过程图）用文字精确描述各部分。\n"
            "- 结尾「AI 总结」：高频考点、答题关键词、易混点对照。"
        ),
    },

]


def _styles_file() -> Path:
    base = os.getenv("AINOTE_APP_DATA_DIR") or os.getenv("UPLOAD_DIR") or "."
    d = Path(base)
    d.mkdir(parents=True, exist_ok=True)
    return d / "note_styles.json"


def _load_custom() -> List[Dict]:
    f = _styles_file()
    if not f.exists():
        return []
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except Exception as e:
        logger.error(f"读取自定义笔记风格失败: {e}")
        return []


def _save_custom(styles: List[Dict]):
    f = _styles_file()
    f.write_text(json.dumps(styles, ensure_ascii=False, indent=2), encoding="utf-8")


def list_styles() -> List[Dict]:
    """全部风格：内置 + 自定义"""
    with _lock:
        custom = _load_custom()
    return BUILTIN_STYLES + [
        {
            "id": s.get("id"),
            "name": s.get("name"),
            "icon": s.get("icon", "📝"),
            "builtin": False,
            "prompt": s.get("prompt", ""),
        }
        for s in custom
    ]


def get_style_prompt(style_id: str) -> Optional[str]:
    """取风格指令；内置优先，其次自定义；找不到返回 None"""
    for s in BUILTIN_STYLES:
        if s["id"] == style_id:
            return s["prompt"]
    with _lock:
        for s in _load_custom():
            if s.get("id") == style_id:
                return s.get("prompt", "")
    return None


def create_style(name: str, prompt: str, icon: str = "📝") -> Dict:
    if not name or not name.strip():
        raise ValueError("风格名称不能为空")
    if not prompt or not prompt.strip():
        raise ValueError("提示词模板不能为空")
    style = {
        "id": f"custom_{uuid.uuid4().hex[:8]}",
        "name": name.strip()[:30],
        "icon": (icon or "📝")[:4],
        "prompt": prompt.strip(),
    }
    with _lock:
        styles = _load_custom()
        if any(s.get("name") == style["name"] for s in styles):
            raise ValueError(f"已存在同名风格: {style['name']}")
        styles.append(style)
        _save_custom(styles)
    logger.info(f"已创建自定义笔记风格: {style['name']} ({style['id']})")
    return style


def update_style(style_id: str, name: Optional[str] = None, prompt: Optional[str] = None, icon: Optional[str] = None) -> Dict:
    with _lock:
        styles = _load_custom()
        for s in styles:
            if s.get("id") == style_id:
                if name is not None and name.strip():
                    s["name"] = name.strip()[:30]
                if prompt is not None and prompt.strip():
                    s["prompt"] = prompt.strip()
                if icon:
                    s["icon"] = icon[:4]
                _save_custom(styles)
                return s
    raise ValueError(f"风格不存在或不可编辑: {style_id}")


def delete_style(style_id: str) -> bool:
    if any(s["id"] == style_id for s in BUILTIN_STYLES):
        raise ValueError("内置风格不能删除")
    with _lock:
        styles = _load_custom()
        remaining = [s for s in styles if s.get("id") != style_id]
        if len(remaining) == len(styles):
            raise ValueError(f"风格不存在: {style_id}")
        _save_custom(remaining)
    logger.info(f"已删除自定义笔记风格: {style_id}")
    return True
