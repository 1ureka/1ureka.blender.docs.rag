#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
clean.py - 將Blender官方手冊HTML轉換成純文字

此腳本讀取data/html資料夾中的HTML檔案，
先提取 <main> 標籤內容以去除導航欄等不必要內容，
然後使用markdownify清理HTML標籤，
並將純文字保存到data/texts資料夾。
"""

import os
import time
import shutil
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from markdownify import markdownify as md
from bs4 import BeautifulSoup

# 設定資料路徑
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
HTML_DIR = DATA_DIR / "html"
TEXT_DIR = DATA_DIR / "texts"

# markdownify 設定選項
MD_OPTIONS = {
    'strip': ['a'],
    'heading_style': 'ATX',
    'bullets': '-',
    'autolinks': False,
    'code_language': '',
    'beautiful_soup_parser': 'lxml'
}

def ensure_directories():
    """確保所需的資料夾存在"""
    print("確保資料夾結構存在...")
    DATA_DIR.mkdir(exist_ok=True)

    # 如果文字目錄已存在，先清空它
    if TEXT_DIR.exists():
        print("清空現有的文字資料夾...")
        shutil.rmtree(TEXT_DIR)

    TEXT_DIR.mkdir(exist_ok=True)

def extract_main_content(html_content):
    """從HTML中提取<main>標籤內容"""
    try:
        soup = BeautifulSoup(html_content, 'lxml')
        main_tag = soup.find('main')

        # 如果找到main標籤，返回其HTML內容
        if main_tag:
            return str(main_tag)
        # 如果沒有找到main標籤，嘗試查找article或section標籤
        else:
            article_tag = soup.find('article')
            if article_tag:
                return str(article_tag)

            section_tag = soup.find('section', {'id': 'content'})
            if section_tag:
                return str(section_tag)

            # 如果都找不到，返回整個body內容
            body_tag = soup.find('body')
            if body_tag:
                return str(body_tag)

            # 最後的後備方案是返回原始HTML
            return html_content
    except Exception as e:
        print(f"提取main內容時發生錯誤: {e}")
        return html_content  # 出錯時返回原始HTML

def html_to_text(html_file):
    """將單個HTML檔案轉換為純文字"""
    try:
        # 計算目標路徑
        rel_path = html_file.relative_to(HTML_DIR)
        target_path = TEXT_DIR / rel_path.with_suffix('.txt')

        # 確保目標資料夾存在
        target_path.parent.mkdir(exist_ok=True, parents=True)

        # 讀取HTML
        with open(html_file, 'r', encoding='utf-8') as f:
            html_content = f.read()

        # 先提取<main>內容
        main_content = extract_main_content(html_content)

        # 轉換為純文字
        text_content = md(main_content, **MD_OPTIONS)

        # 保存純文字
        with open(target_path, 'w', encoding='utf-8') as f:
            f.write(text_content)

        return True
    except Exception as e:
        print(f"處理檔案 {html_file} 時發生錯誤: {e}")
        return False

def find_html_files(directory):
    """遞迴尋找所有HTML檔案"""
    html_files = []
    for path in directory.rglob('*.html'):
        if path.is_file():
            html_files.append(path)
    return html_files

def process_files():
    """處理所有HTML檔案轉換為純文字"""
    print("正在尋找HTML檔案...")
    html_files = find_html_files(HTML_DIR)
    total_files = len(html_files)
    print(f"找到 {total_files} 個HTML檔案需要處理")

    # 處理進度追蹤變數
    processed = 0
    success = 0
    failed = 0
    start_time = time.time()
    last_log_time = start_time  # 記錄上次輸出日誌的時間

    # 使用多線程處理檔案
    with ThreadPoolExecutor(max_workers=os.cpu_count()) as executor:
        # 提交所有任務
        future_to_file = {executor.submit(html_to_text, html_file): html_file for html_file in html_files}

        # 處理完成的任務
        for future in as_completed(future_to_file):
            processed += 1
            if future.result():
                success += 1
            else:
                failed += 1

            # 計算進度和速度
            elapsed = time.time() - start_time
            files_per_sec = processed / elapsed if elapsed > 0 else 0
            remaining = (total_files - processed) / files_per_sec if files_per_sec > 0 else 0

            # 更新進度顯示
            percent = int(100 * processed / total_files)

            # 每10秒記錄新的一行進度，或者達到100%時
            current_time = time.time()
            if current_time - last_log_time >= 10 or processed >= total_files:
                print(f"處理進度: {percent}% [{processed}/{total_files}] 速度: {files_per_sec:.1f} 檔案/秒, 預估剩餘時間: {int(remaining)}秒")
                last_log_time = current_time

    # 處理完成
    print("處理完成")
    print(f"成功轉換: {success} 個檔案")
    print(f"處理失敗: {failed} 個檔案")
    print(f"總處理時間: {time.time() - start_time:.2f} 秒")

def main():
    """主函數"""
    print("=== 開始將Blender官方手冊HTML轉換為純文字 ===")

    # 確認來源HTML資料夾存在
    if not HTML_DIR.exists():
        print(f"錯誤: HTML來源資料夾不存在 ({HTML_DIR})")
        print("請先執行 download.py 下載手冊")
        return False

    # 確保目標資料夾結構
    ensure_directories()

    # 處理檔案
    process_files()

    print("=== 轉換完成 ===")
    return True

if __name__ == "__main__":
    main()
