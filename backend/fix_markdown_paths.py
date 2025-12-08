#!/usr/bin/env python3
"""
修复 markdown 文件中的图片路径
将 /static/screenshots/ 替换为 /api/note_results/screenshots/
"""
import re
from pathlib import Path

NOTE_OUTPUT_DIR = Path("note_results")
IMAGE_BASE_URL = "/api/note_results/screenshots"

def fix_markdown_paths():
    """修复所有 markdown 文件中的图片路径"""
    markdown_files = list(NOTE_OUTPUT_DIR.glob("*_markdown.md"))
    
    for md_file in markdown_files:
        print(f"处理文件: {md_file.name}")
        content = md_file.read_text(encoding='utf-8')
        
        # 修复图片路径
        old_content = content
        content = re.sub(
            r'!\[\]\(/static/screenshots/([^)]+)\)',
            lambda m: f"![]({IMAGE_BASE_URL.rstrip('/')}/{m.group(1)})",
            content
        )
        
        if content != old_content:
            md_file.write_text(content, encoding='utf-8')
            print(f"  ✓ 已修复路径")
        else:
            print(f"  - 无需修复")

if __name__ == "__main__":
    fix_markdown_paths()
    print("完成！")



