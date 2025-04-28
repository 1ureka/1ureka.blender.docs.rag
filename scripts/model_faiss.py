#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
model_faiss.py - FAISS索引加載與管理模組

此模組負責載入和初始化FAISS向量索引，
提供GPU加速支援，同時管理索引和文本塊數據的載入與查詢功能。
也提供建立向量索引的功能。
"""

import json
from pathlib import Path
from typing import Tuple, List, Dict, Any, Optional

import numpy as np
import faiss

# 設定資料路徑
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
INDEX_DIR = DATA_DIR / "index"
TEXT_DIR = DATA_DIR / "texts"

# 每次查詢返回的最相關結果數量
TOP_K = 12

# 快取全局變數
_index = None
_chunks = None
_gpu_resources = None


def get_gpu_resources():
    """獲取GPU資源，如果可用的話"""
    global _gpu_resources

    # 如果已經初始化過GPU資源，直接返回
    if _gpu_resources is not None:
        return _gpu_resources

    try:
        # 嘗試初始化GPU資源
        res = faiss.StandardGpuResources()
        print("成功初始化GPU資源")
        _gpu_resources = res
        return res
    except Exception as e:
        print(f"無法初始化GPU資源: {e}")
        return None


def load_model() -> Tuple[Optional[Any], Optional[List[Dict[str, Any]]]]:
    """載入FAISS索引和文本塊資料，支援GPU加速

    Returns:
        tuple: (index, chunks) - FAISS索引和文本塊資料，若載入失敗則返回(None, None)
    """
    global _index, _chunks

    # 如果已經載入，直接返回
    if _index is not None and _chunks is not None:
        return _index, _chunks

    print("正在載入FAISS索引和文本塊資料...")

    index_path = INDEX_DIR / "faiss.index"
    chunks_path = INDEX_DIR / "chunks.json"

    if not index_path.exists() or not chunks_path.exists():
        print(f"錯誤：找不到索引文件 ({index_path}) 或文本塊資料 ({chunks_path})")
        return None, None

    try:
        # 載入FAISS索引
        index = faiss.read_index(str(index_path))

        # 檢查是否有可用的GPU資源
        gpu_res = get_gpu_resources()
        if gpu_res is not None:
            print("檢測到GPU資源，使用GPU加速索引...")
            # 將索引複製到GPU
            index = faiss.index_cpu_to_gpu(gpu_res, 0, index)

        # 載入文本塊資料
        with open(chunks_path, "r", encoding="utf-8") as f:
            chunks = json.load(f)

        print(f"成功載入索引，包含 {index.ntotal} 個向量")
        print(f"成功載入文本塊資料，共 {len(chunks)} 個塊")

        # 快取載入的資源
        _index = index
        _chunks = chunks

        return index, chunks
    except Exception as e:
        print(f"載入索引或文本塊資料時發生錯誤: {e}")
        return None, None


def create_index(embeddings: np.ndarray) -> bool:
    """為文本塊創建向量索引

    Args:
        embeddings (np.ndarray): 文本塊的嵌入向量，形狀為(n_chunks, vector_dimension)

    Returns:
        bool: 索引創建是否成功
    """
    # 確保索引目錄存在
    INDEX_DIR.mkdir(exist_ok=True, parents=True)

    # 將嵌入轉換為numpy數組並標準化
    embeddings = np.array(embeddings).astype("float32")
    faiss.normalize_L2(embeddings)

    # 建立FAISS索引
    print("建立FAISS索引...")
    vector_dimension = embeddings.shape[1]
    index = faiss.IndexFlatIP(vector_dimension)

    # 檢查是否有可用的GPU資源
    gpu_res = get_gpu_resources()
    if gpu_res is not None:
        print("檢測到GPU資源，使用GPU加速索引...")
        index = faiss.index_cpu_to_gpu(gpu_res, 0, index)

    # 添加向量到索引
    index.add(embeddings)

    # 保存索引
    if isinstance(index, faiss.GpuIndexFlat):
        print("將索引從GPU移回CPU以保存...")
        index = faiss.index_gpu_to_cpu(index)

    print(f"保存索引到 {INDEX_DIR / 'faiss.index'}")
    faiss.write_index(index, str(INDEX_DIR / "faiss.index"))

    return True


def query_index(query_vector: np.ndarray, top_k: int = TOP_K) -> List[Dict[str, Any]]:
    """使用查詢向量檢索最相關的文本

    Args:
        query_vector (np.ndarray): 查詢的向量，形狀為(1, 向量維度)
        top_k (int): 返回最相關的結果數量，預設為TOP_K

    Returns:
        List[Dict[str, Any]]: 包含內容、來源和相似度的結果列表
    """
    index, chunks = load_model()
    if index is None or chunks is None:
        raise RuntimeError("索引載入失敗，無法執行搜尋")

    # 標準化查詢向量，在索引中搜尋
    faiss.normalize_L2(query_vector)
    distances, indices = index.search(query_vector, top_k)

    # 建立來源路徑到相似度的映射
    similarity_map = {}
    for i, idx in enumerate(indices[0]):
        if idx < 0 or idx >= len(chunks):
            continue

        source = chunks[idx]["source"]
        similarity = float(distances[0][i])
        txt_path = str(TEXT_DIR / source)

        # 只記錄檔案存在的來源
        if Path(txt_path).exists():
            similarity_map[txt_path] = similarity

    # 處理文本檔案並建立最終結果
    final_results = []
    for txt_path, similarity in similarity_map.items():
        try:
            with open(txt_path, "r", encoding="utf-8") as f:
                content = f.read()

            p = Path(txt_path)
            name = str(p.parent.name + "/" + p.name) if p.parent.name else p.name
            content = str(content)[:4500]  # 限制內容長度
            final_results.append({"file": name, "content": content, "similarity": similarity})

        except Exception as e:
            print(f"處理HTML檔案 {txt_path} 時出錯: {e}")

    return final_results
