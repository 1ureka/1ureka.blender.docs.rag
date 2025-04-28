#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
validate.py - 驗證Blender手冊RAG系統的向量索引

此腳本用於測試已建立的向量索引是否正常工作，執行一系列測試查詢，
驗證多語言檢索能力，特別是用中文查詢英文內容的能力。
同時檢查索引的完整性和效能。
"""

import time
from pathlib import Path

# 導入專用模型加載模塊
from . import model_embedding
from . import model_faiss

# 設定資料路徑
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
INDEX_DIR = DATA_DIR / "index"

# 測試查詢列表 (中英文混合)
TEST_QUERIES = [
    "如何在Blender中使用鏡像修改器？",
    "如何匯出模型成GLTF格式？",
    "How to use modifiers in Blender?",
    "材質節點的基本使用方法？",
    "如何進行UV展開？",
    "Rigging and bone setup",
]


def retrieve_relevant_chunks(query: str):
    """對查詢進行向量化，並查詢索引"""
    try:
        start_time = time.time()
        query_vector = model_embedding.encode_text([query])[0].astype("float32").reshape(1, -1)
        results = model_faiss.query_index(query_vector)

        query_time = time.time() - start_time
        return results, query_time
    except Exception as e:
        print(f"查詢索引時發生錯誤: {e}")
        return [], 0


def validate_index():
    """執行一系列測試查詢以驗證索引"""
    print("=== 開始驗證向量索引 ===")

    # 載入嵌入模型
    embedding_model = model_embedding.load_model()
    if not embedding_model:
        print("無法載入嵌入模型")
        return False

    # 載入索引和文本塊
    index, chunks = model_faiss.load_model()
    if not index or not chunks:
        print("無法載入FAISS索引或文本塊資料")
        return False

    # 執行測試查詢
    print(f"\n執行 {len(TEST_QUERIES)} 個測試查詢...")
    all_successful = True
    total_time = 0

    for i, query in enumerate(TEST_QUERIES):
        print(f"\n測試查詢 {i + 1}/{len(TEST_QUERIES)}: '{query}'")

        results, query_time = retrieve_relevant_chunks(query)
        total_time += query_time

        if not results:
            print("  ❌ 失敗：沒有找到相關結果")
            all_successful = False
            continue

        print(f"  ✓ 成功：找到 {len(results)} 個結果，查詢時間: {query_time:.3f}秒")

        # 顯示第一個結果的簡短預覽
        if results:
            content = results[0]["content"]
            preview = content[:150] + "..." if len(content) > 150 else content
            source = results[0]["source"]
            similarity = results[0]["similarity"]

            print(f"  最相關結果 (相似度: {similarity:.4f}):")
            print(f"  來源: {source}")
            print(f"  內容預覽: {preview}")

    # 計算平均查詢時間
    avg_time = total_time / len(TEST_QUERIES) if TEST_QUERIES else 0

    print("\n=== 驗證結果摘要 ===")
    print(f"總測試查詢: {len(TEST_QUERIES)}")
    print(f"平均查詢時間: {avg_time:.3f}秒")

    if all_successful:
        print("✓ 所有測試查詢均成功返回結果")
        print("✓ 向量索引驗證通過！")
    else:
        print("❌ 部分測試查詢未能返回結果")
        print("❌ 向量索引驗證未完全通過，請檢查日誌")

    return all_successful


def main():
    """主函數"""
    success = validate_index()
    return success


if __name__ == "__main__":
    main()
