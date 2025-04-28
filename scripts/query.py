#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
query.py - 查詢與組 Prompt 模組

此腳本提供查詢Blender手冊RAG系統的功能。
使用向量索引檢索相關文本塊，組合成適合LLM的Prompt，
實現中文查詢英文內容，並以中文返回回答的功能。
"""

from pathlib import Path
from typing import List, Dict, Any
import textwrap

# 導入專用模型加載模塊
from scripts import model_embedding
from scripts import model_faiss
from scripts import model_ollama

# 設定資料路徑
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
INDEX_DIR = DATA_DIR / "index"


def retrieve_relevant_chunks(query: str) -> List[Dict[str, Any]]:
    """使用查詢來檢索最相關的文本塊"""
    try:
        query_vector = model_embedding.encode_text([query])[0].astype("float32").reshape(1, -1)
        results = model_faiss.query_index(query_vector)
        return results
    except Exception as e:
        print(f"查詢索引時發生錯誤: {e}")
        return []


def build_prompt(query: str, chunks: List[Dict[str, Any]]) -> str:
    """構建發送給LLM的prompt"""
    context_texts = []
    for i, chunk in enumerate(chunks):
        source = chunk["source"]
        content = chunk["content"]
        similarity = chunk["similarity"]

        if similarity < 0.2:
            continue

        # 添加來源和內容到上下文
        context_text = f"[文件 {i + 1}] 來源: {source}\n內容:\n{content}\n"
        context_texts.append(context_text)

    # 組合完整的prompt
    prompt = textwrap.dedent(f"""\
        您是 Blender 軟體的專業助手，請基於以下參考文件的內容，用繁體中文回答我的問題。
        如果參考文件中沒有足夠資訊，請坦誠表明無法回答，不要編造資訊。
        請專注於回答與 Blender 相關的問題，若問題與 Blender 無關，請婉拒回答。

        參考文件:
        {"".join(context_texts)}

        我的問題是: {query}

        請提供詳細且實用的回答，使用繁體中文，並適當引用參考文件的內容。
    """)
    return prompt


def process_query(question: str, model_name: str = model_ollama.OLLAMA_MODEL):
    """處理用戶查詢並以流式方式返回回答"""
    try:
        # 檢索相關文本塊
        print(f"正在處理問題: '{question}'")
        relevant_chunks = retrieve_relevant_chunks(question)

        if not relevant_chunks:
            yield "很抱歉，無法找到相關資訊。請嘗試重新表達您的問題，或檢查索引是否正確建立。"
            return

        # 構建prompt，向Ollama請求流式回答
        prompt = build_prompt(question, relevant_chunks)
        print(f"向Ollama ({model_name}) 發送流式請求...")
        yield from model_ollama.query_ollama_stream(prompt, model_name)

    except Exception as e:
        error_msg = f"處理查詢時發生錯誤: {e}"
        print(error_msg)
        yield error_msg
