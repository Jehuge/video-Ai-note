#!/usr/bin/env python3
"""检查数据库结构"""
import sqlite3
import os

DB_PATH = "video_note.db"

if os.path.exists(DB_PATH):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 检查表结构
    cursor.execute("PRAGMA table_info(video_tasks)")
    columns = cursor.fetchall()
    
    print("数据库表结构:")
    print("-" * 50)
    for col in columns:
        print(f"  {col[1]} ({col[2]})")
    
    # 检查是否有 screenshot 字段
    column_names = [col[1] for col in columns]
    if "screenshot" in column_names:
        print("\n✓ screenshot 字段已存在")
    else:
        print("\n✗ screenshot 字段不存在，需要添加")
        print("执行迁移: python -c 'from app.db.migrate import migrate_add_screenshot_column; migrate_add_screenshot_column()'")
    
    conn.close()
else:
    print(f"数据库文件 {DB_PATH} 不存在")

