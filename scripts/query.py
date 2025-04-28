#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
query.py - 查詢與組 Prompt 模組

此腳本提供查詢Blender手冊RAG系統的功能。
使用向量索引檢索相關文本塊，組合成適合LLM(Ollama)的Prompt，
實現中文查詢英文內容，並以中文返回回答的功能。
"""

import json
import time
import requests
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

# 導入向量化和索引所需的庫
import numpy as np
from sentence_transformers import SentenceTransformer
import faiss

# 設定資料路徑
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
INDEX_DIR = DATA_DIR / "index"

# 設定查詢參數
TOP_K = 10  # 每次查詢返回的最相關結果數量
MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"  # 與 index.py 中相同的模型
OLLAMA_API_URL = "http://ollama:11434/api/generate"  # Ollama API URL (Docker服務名稱)
OLLAMA_MODEL = "llama3"  # 默認使用的模型名稱
OLLAMA_CONTEXT_LENGTH = 8192  # Ollama模型的上下文長度限制

# 緩存全局變數
_model = None
_index = None
_chunks = None

def load_model() -> Optional[SentenceTransformer]:
    """載入多語言向量模型，支援GPU加速"""
    global _model

    if _model is not None:
        return _model

    try:
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"
        model = SentenceTransformer(MODEL_NAME, device=device)
        print(f"向量模型載入成功，使用裝置：{device}")
        _model = model
        return model
    except Exception as e:
        print(f"載入模型時發生錯誤: {e}")
        return None

def load_index_and_chunks() -> Tuple[Any, List[Dict[str, Any]]]:
    """載入FAISS索引和文本塊資料"""
    global _index, _chunks

    # 如果已經載入，直接返回
    if _index is not None and _chunks is not None:
        return _index, _chunks

    print("正在載入FAISS索引和文本塊資料...")

    index_path = INDEX_DIR / "faiss.index"
    chunks_path = INDEX_DIR / "chunks.json"

    if not index_path.exists() or not chunks_path.exists():
        print(f"錯誤：找不到索引文件 ({index_path}) 或文本塊資料 ({chunks_path})")
        return None, []

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

        _index = index
        _chunks = chunks

        return index, chunks
    except Exception as e:
        print(f"載入索引或文本塊資料時發生錯誤: {e}")
        return None, []

def retrieve_relevant_chunks(query: str, top_k: int = TOP_K) -> List[Dict[str, Any]]:
    """使用查詢來檢索最相關的文本塊"""
    # 載入必要的資源
    model = load_model()
    index, chunks = load_index_and_chunks()

    if not model or not index or not chunks:
        return []

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
        print(f"查詢完成，找到 {len(results)} 筆結果，耗時 {query_time:.3f} 秒")

        return results
    except Exception as e:
        print(f"查詢索引時發生錯誤: {e}")
        return []

def build_prompt(query: str, chunks: List[Dict[str, Any]]) -> str:
    """構建發送給LLM的prompt"""
    # 選擇相似度最高的chunks
    selected_chunks = chunks[:5]  # 取前5個最相關的結果

    # 組合上下文內容
    context_texts = []
    for i, chunk in enumerate(selected_chunks):
        source = chunk["source"]
        content = chunk["content"]
        similarity = chunk["similarity"]

        # 添加來源和內容到上下文
        context_text = f"[文件 {i+1}] 來源: {source}\n內容:\n{content}\n"
        context_texts.append(context_text)

    # 組合完整的prompt
    prompt = f"""您是 Blender 軟體的專業助手，請基於以下參考文件的內容，用繁體中文回答我的問題。
如果參考文件中沒有足夠資訊，請坦誠表明無法回答，不要編造資訊。
請專注於回答與 Blender 相關的問題，若問題與 Blender 無關，請婉拒回答。

參考文件:
{"".join(context_texts)}

我的問題是: {query}

請提供詳細且實用的回答，使用繁體中文，並適當引用參考文件的內容。"""

    return prompt

def query_ollama(prompt: str, model: str = OLLAMA_MODEL) -> str:
    """向Ollama API發送請求獲取回答"""
    try:
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": { "num_ctx": OLLAMA_CONTEXT_LENGTH }
        }

        response = requests.post(OLLAMA_API_URL, json=payload)

        if response.status_code == 200:
            return response.json().get("response", "")
        else:
            error_msg = f"Ollama API請求失敗: HTTP {response.status_code} - {response.text}"
            print(error_msg)
            return f"處理您的問題時發生錯誤: {error_msg}"
    except Exception as e:
        error_msg = f"Ollama API請求過程中發生錯誤: {str(e)}"
        print(error_msg)
        return f"處理您的問題時發生錯誤: {error_msg}"

def process_query(question: str, model_name: str = OLLAMA_MODEL) -> Dict[str, Any]:
    """處理用戶查詢並返回回答"""
    try:
        start_time = time.time()

        # 檢索相關文本塊
        print(f"正在處理問題: '{question}'")
        relevant_chunks = retrieve_relevant_chunks(question)

        if not relevant_chunks:
            return {
                "success": False,
                "answer": "很抱歉，無法找到相關資訊。請嘗試重新表述您的問題，或檢查索引是否正確建立。",
                "elapsed_time": time.time() - start_time
            }

        # 構建prompt
        prompt = build_prompt(question, relevant_chunks)

        # 向Ollama請求回答
        print(f"向Ollama ({model_name}) 發送請求...")
        answer = query_ollama(prompt, model_name)

        elapsed_time = time.time() - start_time
        print(f"處理完成，總耗時: {elapsed_time:.3f} 秒")

        return {
            "success": True,
            "answer": answer,
            "retrieved_chunks": len(relevant_chunks),
            "elapsed_time": elapsed_time
        }
    except Exception as e:
        print(f"處理查詢時發生錯誤: {e}")
        return {
            "success": False,
            "answer": f"處理您的問題時發生錯誤: {str(e)}",
            "elapsed_time": time.time() - start_time
        }

def main():
    """命令行測試用主函數"""
    # 載入必要資源
    if not load_model() or not load_index_and_chunks()[0]:
        print("初始化失敗，無法進行查詢")
        return False

    print("=== Blender 手冊查詢系統 ===")
    print("輸入您的問題，或輸入'quit'退出")

    while True:
        question = input("\n您的問題: ")
        if question.lower() in ('quit', 'exit', 'q'):
            break

        result = process_query(question)
        print("\n回答:")
        print(result["answer"])
        print(f"\n用時: {result['elapsed_time']:.3f} 秒")

    return True

if __name__ == "__main__":
    main()
