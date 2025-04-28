#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
vectorize.py - 為Blender官方手冊建立向量索引

此腳本讀取data/texts資料夾中的純文字檔案，
將文件分段(chunk)以便於檢索，
然後使用多語言模型建立向量索引，
最終生成FAISS向量資料庫於data/index資料夾。
支援中文查詢英文內容功能。
"""

import os
import shutil
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict

# 導入專用模型加載模塊
from scripts import model_embedding
from scripts import model_faiss

# 設定資料路徑
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
TEXT_DIR = DATA_DIR / "texts"
INDEX_DIR = DATA_DIR / "index"

# 設定分段和索引參數
CHUNK_SIZE = 500  # 每個分段的字符數
CHUNK_OVERLAP = 50  # 分段間的重疊字符數
MAX_CHUNKS_PER_FILE = 1000  # 每個檔案最多處理的分段數，防止極大檔案


def ensure_directories():
    """確保所需的資料夾存在"""
    print("確保資料夾結構存在...")
    DATA_DIR.mkdir(exist_ok=True)

    # 如果索引目錄已存在，先清空它
    if INDEX_DIR.exists():
        print("清空現有的索引資料夾...")
        shutil.rmtree(INDEX_DIR)

    INDEX_DIR.mkdir(exist_ok=True)


def load_text_file(file_path: Path) -> str:
    """載入純文字檔案內容"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        print(f"讀取檔案 {file_path} 時發生錯誤: {e}")
        return ""


def chunk_text(text: str, file_path: str) -> List[Dict[str, str]]:
    """將文本分割成較小的塊"""
    chunks = []

    # 跳過空文本
    if not text.strip():
        return chunks

    # 確保檔案路徑為文字格式
    file_path = str(file_path)

    # 將文本按段落分割
    paragraphs = text.split("\n\n")
    current_chunk = ""

    for paragraph in paragraphs:
        # 如果段落太長，直接做為一個塊
        if len(paragraph) > CHUNK_SIZE:
            # 如果當前塊不為空，先添加當前塊
            if current_chunk:
                chunks.append({"content": current_chunk.strip(), "source": file_path})
                current_chunk = ""

            # 處理長段落
            for i in range(0, len(paragraph), CHUNK_SIZE - CHUNK_OVERLAP):
                chunk = paragraph[i : i + CHUNK_SIZE]
                if chunk:
                    chunks.append({"content": chunk.strip(), "source": file_path})

                if len(chunks) >= MAX_CHUNKS_PER_FILE:
                    print(f"警告: 檔案 {file_path} 分段數達到上限 {MAX_CHUNKS_PER_FILE}")
                    return chunks

        # 如果加上新段落後長度超過限制，保存當前塊並創建新塊
        elif len(current_chunk) + len(paragraph) + 2 > CHUNK_SIZE:  # +2 for '\n\n'
            if current_chunk:
                chunks.append({"content": current_chunk.strip(), "source": file_path})
            current_chunk = paragraph

        # 否則，將段落添加到當前塊
        else:
            if current_chunk:
                current_chunk += "\n\n" + paragraph
            else:
                current_chunk = paragraph

    # 添加最後一個塊
    if current_chunk:
        chunks.append({"content": current_chunk.strip(), "source": file_path})

    return chunks


def find_text_files(directory: Path) -> List[Path]:
    """遞迴尋找所有文字檔案"""
    return list(directory.rglob("*.txt"))


def process_file(text_file: Path) -> List[Dict[str, str]]:
    """處理單個檔案的分段"""
    content = load_text_file(text_file)
    if not content:
        return []

    # 計算相對路徑作為來源標識
    rel_path = text_file.relative_to(TEXT_DIR)
    chunks = chunk_text(content, str(rel_path))
    return chunks


def vectorize_text_chunks(chunks: List[Dict[str, str]]):
    """為文本塊創建向量索引"""
    print(f"開始為 {len(chunks)} 個文本塊建立向量索引...")

    # 確保索引目錄存在
    ensure_directories()

    # 向量化文本塊
    try:
        texts = [chunk["content"] for chunk in chunks]
        embeddings = model_embedding.encode_text(texts)
        print(f"成功向量化 {len(embeddings)} 個文本塊")
    except Exception as e:
        print(f"建立向量索引時發生錯誤: {e}")
        return False

    # 創建索引
    model_faiss.create_index(embeddings)

    # 保存文本塊數據
    print(f"保存文本塊數據到 {INDEX_DIR / 'chunks.json'}")
    with open(INDEX_DIR / "chunks.json", "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)

    print(f"索引創建完成，共包含 {len(chunks)} 個文本塊的向量")
    return True


def main():
    """主函數"""
    print("=== 開始為Blender官方手冊建立向量索引 ===")

    # 確認來源文本資料夾存在
    if not TEXT_DIR.exists():
        print(f"錯誤: 文本來源資料夾不存在 ({TEXT_DIR})")
        print("請先執行 clean.py 清理HTML")
        return False

    # 找到所有文本檔案
    print("正在尋找文字檔案...")
    text_files = find_text_files(TEXT_DIR)
    total_files = len(text_files)
    print(f"找到 {total_files} 個文字檔案需要處理")

    # 初始化統計變數
    success = 0
    failed = 0
    all_chunks = []

    # 使用多線程處理檔案
    with ThreadPoolExecutor(max_workers=os.cpu_count()) as executor:
        # 提交所有任務
        future_to_file = {executor.submit(process_file, text_file): text_file for text_file in text_files}

        # 處理完成的任務
        for future in as_completed(future_to_file):
            try:
                file_chunks = future.result()
                if file_chunks:
                    all_chunks.extend(file_chunks)
                    success += 1
                else:
                    failed += 1
            except Exception as e:
                print(f"\n處理檔案時發生錯誤: {e}")
                failed += 1

    print("分段處理完成")
    print(f"成功處理: {success} 個檔案")
    print(f"處理失敗: {failed} 個檔案")
    print(f"總分段數: {len(all_chunks)}")

    # 建立向量索引
    result = vectorize_text_chunks(all_chunks)

    if result:
        print("=== 向量索引建立完成 ===")
    else:
        print("=== 向量索引建立失敗 ===")

    return result


if __name__ == "__main__":
    main()
