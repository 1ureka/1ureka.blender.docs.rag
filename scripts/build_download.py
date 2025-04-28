#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
download.py - 下載Blender官方手冊

此腳本從Blender官方網站下載最新版本的手冊HTML壓縮檔，
並解壓到data/html資料夾中供後續處理。
"""

import os
import requests
import zipfile
import shutil
import time
from pathlib import Path

# 官方手冊下載URL
BLENDER_MANUAL_URL = "https://docs.blender.org/manual/en/latest/blender_manual_html.zip"

# 設定資料路徑
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
HTML_DIR = DATA_DIR / "html"
DOWNLOAD_PATH = DATA_DIR / "blender_manual_html.zip"

def ensure_directories():
    """確保所需的資料夾存在"""
    print("確保資料夾結構存在...")
    DATA_DIR.mkdir(exist_ok=True)

    # 如果HTML目錄已存在，先清空它
    if HTML_DIR.exists():
        print("清空現有的HTML資料夾...")
        shutil.rmtree(HTML_DIR)

    HTML_DIR.mkdir(exist_ok=True)

def download_manual():
    """下載Blender官方手冊"""
    print(f"開始從 {BLENDER_MANUAL_URL} 下載Blender手冊...")

    try:
        response = requests.get(BLENDER_MANUAL_URL, stream=True)
        response.raise_for_status()  # 檢查是否成功獲取

        # 獲取文件大小以顯示下載進度
        total_size = int(response.headers.get('content-length', 0))

        # 下載文件
        with open(DOWNLOAD_PATH, 'wb') as f:
            if total_size == 0:  # 無法獲取大小時的處理
                f.write(response.content)
                print("下載完成")
            else:
                downloaded = 0
                last_log_time = time.time()  # 記錄上次輸出日誌的時間

                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        percent = int(100 * downloaded / total_size)

                        # 每10秒記錄新的一行進度，或者達到100%時
                        current_time = time.time()
                        if current_time - last_log_time >= 10 or percent >= 100:
                            print(f"下載進度: {percent}% [{downloaded}/{total_size} bytes]")
                            last_log_time = current_time

                print("下載完成")

        return True
    except Exception as e:
        print(f"下載過程中發生錯誤: {e}")
        return False

def extract_manual():
    """解壓縮下載的手冊"""
    print(f"解壓縮 {DOWNLOAD_PATH} 到 {HTML_DIR}...")

    try:
        with zipfile.ZipFile(DOWNLOAD_PATH, 'r') as zip_ref:
            zip_ref.extractall(HTML_DIR)
        print("解壓縮完成")

        # 解壓後刪除ZIP檔
        os.remove(DOWNLOAD_PATH)
        print(f"已刪除下載的ZIP檔 {DOWNLOAD_PATH}")

        return True
    except Exception as e:
        print(f"解壓縮過程中發生錯誤: {e}")
        return False

def main():
    """主函數"""
    print("=== 開始下載Blender官方手冊 ===")

    # 確保所需目錄存在
    ensure_directories()

    # 下載手冊
    if download_manual():
        # 解壓縮手冊
        if extract_manual():
            print("=== Blender官方手冊下載並解壓完成 ===")
            return True

    print("=== 下載或解壓過程中發生錯誤，請檢查上述訊息 ===")
    return False

if __name__ == "__main__":
    main()
