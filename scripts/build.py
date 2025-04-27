#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
build.py - Blender手冊RAG系統資料建立整合腳本

此腳本整合了完整的資料處理流程，依序執行：
1. 下載Blender官方手冊 (download.py)
2. 清理HTML成純文字 (clean.py)
3. 建立向量索引 (index.py)

作為一站式解決方案，這個腳本可以從頭開始建立整個RAG系統所需的資料。
"""

import os
import time
import sys
from pathlib import Path

# 匯入其他模組
sys.path.append(str(Path(__file__).resolve().parent))
import download
import clean
import index

def print_section_header(title):
    """印出區段標題"""
    line = "=" * 60
    print("\n" + line)
    print(f"  {title}")
    print(line + "\n")

def main():
    """主函數 - 執行完整的處理流程"""
    start_time = time.time()

    print_section_header("開始建立 Blender 手冊 RAG 系統資料")

    # 步驟 1: 下載 Blender 官方手冊
    print_section_header("步驟 1/3: 下載 Blender 官方手冊")
    if not download.main():
        print("錯誤: 下載手冊失敗，處理中止")
        return False

    # 步驟 2: 清理 HTML 成純文字
    print_section_header("步驟 2/3: 清理 HTML 成純文字")
    if not clean.main():
        print("錯誤: 清理 HTML 失敗，處理中止")
        return False

    # 步驟 3: 建立向量索引
    print_section_header("步驟 3/3: 建立向量索引")
    if not index.main():
        print("錯誤: 建立索引失敗，處理中止")
        return False

    # 計算總處理時間
    total_time = time.time() - start_time
    hours, remainder = divmod(total_time, 3600)
    minutes, seconds = divmod(remainder, 60)

    print_section_header("處理完成")
    print(f"總處理時間: {int(hours)}小時 {int(minutes)}分鐘 {int(seconds)}秒")
    print("Blender 手冊 RAG 系統資料建立完成！")
    print("您現在可以啟動服務並開始使用了。")

    return True

if __name__ == "__main__":
    main()
