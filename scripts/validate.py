#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
validate.py - 驗證Blender手冊RAG系統的向量索引

此腳本用於測試已建立的向量索引是否正常工作，執行一系列測試查詢，
驗證多語言檢索能力，特別是用中文查詢英文內容的能力。
同時檢查索引的完整性和效能。
"""

import json
import time
from pathlib import Path

# 導入向量化和索引所需的庫
import numpy as np
from sentence_transformers import SentenceTransformer
import faiss

# 設定資料路徑
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
INDEX_DIR = DATA_DIR / "index"

# 設定驗證參數
TOP_K = 10  # 每次查詢返回的最相關結果數量
MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"  # 與 index.py 中相同的模型

# 測試查詢列表 (中英文混合)
TEST_QUERIES = [
    "如何在Blender中使用鏡像修改器？",
    "如何匯出模型成GLTF格式？",
    "How to use modifiers in Blender?",
    "材質節點的基本使用方法？",
    "如何進行UV展開？",
    "Rigging and bone setup",
]

def load_index_and_chunks():
    """載入FAISS索引和文本塊資料"""
    print("正在載入FAISS索引和文本塊資料...")

    index_path = INDEX_DIR / "faiss.index"
    chunks_path = INDEX_DIR / "chunks.json"

    if not index_path.exists() or not chunks_path.exists():
        print(f"錯誤：找不到索引文件 ({index_path}) 或文本塊資料 ({chunks_path})")
        print("請先執行 index.py 建立向量索引")
        return None, None

    try:
        # 載入FAISS索引
        index = faiss.read_index(str(index_path))

        # 檢查是否有可用的GPU資源
        try:
            res = faiss.StandardGpuResources()  # 初始化GPU資源
            print("檢測到GPU資源，使用GPU加速索引...")
            # 將索引複製到GPU
            index = faiss.index_cpu_to_gpu(res, 0, index)
        except Exception as e:
            print(f"無法使用GPU加速: {e}")
            print("使用CPU繼續處理...")

        # 載入文本塊資料
        with open(chunks_path, 'r', encoding='utf-8') as f:
            chunks = json.load(f)

        print(f"成功載入索引，包含 {index.ntotal} 個向量")
        print(f"成功載入文本塊資料，共 {len(chunks)} 個塊")

        return index, chunks
    except Exception as e:
        print(f"載入索引或文本塊資料時發生錯誤: {e}")
        return None, None

def query_index(query, index, chunks, model, top_k=TOP_K):
    """使用查詢來檢索最相關的文本塊"""
    try:
        # 對查詢進行向量化
        start_time = time.time()
        query_vector = model.encode([query])[0].astype('float32').reshape(1, -1)
        faiss.normalize_L2(query_vector)

        # 在索引中搜索最相關的向量
        distances, indices = index.search(query_vector, top_k)

        # 獲取對應的文本塊
        results = []
        for i, idx in enumerate(indices[0]):
            if 0 <= idx < len(chunks):
                result = {
                    "content": chunks[idx]["content"],
                    "source": chunks[idx]["source"],
                    "similarity": float(distances[0][i])  # 轉換為Python浮點數以便JSON序列化
                }
                results.append(result)

        query_time = time.time() - start_time
        return results, query_time
    except Exception as e:
        print(f"查詢索引時發生錯誤: {e}")
        return [], 0

def validate_index():
    """執行一系列測試查詢以驗證索引"""
    print("=== 開始驗證向量索引 ===")

    # 載入索引和文本塊
    index, chunks = load_index_and_chunks()
    if not index or not chunks:
        return False

    # 載入多語言模型
    try:
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"載入多語言向量模型 {MODEL_NAME}...")
        model = SentenceTransformer(MODEL_NAME, device=device)
        print(f"模型載入成功，使用裝置：{device}")
    except Exception as e:
        print(f"載入模型時發生錯誤: {e}")
        return False

    # 執行測試查詢
    print(f"\n執行 {len(TEST_QUERIES)} 個測試查詢...")
    all_successful = True
    total_time = 0

    for i, query in enumerate(TEST_QUERIES):
        print(f"\n測試查詢 {i+1}/{len(TEST_QUERIES)}: '{query}'")

        results, query_time = query_index(query, index, chunks, model)
        total_time += query_time

        if not results:
            print(f"  ❌ 失敗：沒有找到相關結果")
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
