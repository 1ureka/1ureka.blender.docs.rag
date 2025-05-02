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


def generate_keywords(question: str, model_name: str = model_ollama.OLLAMA_MODEL) -> str:
    """使用LLM從問題中生成關鍵字列表"""
    # 構建生成關鍵字的prompt
    prompt = textwrap.dedent(f"""\
        你是一位專業的關鍵字提取專家，負責從用戶的問題中提取與 Blender 3D 軟體相關的重要關鍵字與概念。

        請根據問題內容，分析其意圖，並提取 10～20 個關鍵字。這些關鍵字可以是：
        1. 使用到的功能或技術（如：節點、布林、粒子系統）
        2. 使用到的渲染引擎（如：Cycles、Eevee）
        3. 隱含的語意概念（例如：若問題提到「寫實」，請包含「Cycles」；若提到「快速渲染」，可包含「Eevee」）

        僅輸出關鍵字，以「英文半形逗號」分隔，且請務必不要換行或添加多餘說明，這樣我才能用 `keywords = [kw.strip() for kw in response.split(",")]`進行分析。

        範例：
        問題：如何在Blender中製作寫實的水材質？
        回答：water material,shader,shader nodes,realistic material,Cycles,refraction,transparency,fresnel,IOR,PBR,BSDF,reflection,caustics,subsurface scattering,render engine,node editor,glass shader,lighting,wet surface,material preview

        問題：我要快速預覽玻璃材質效果
        回答：glass material,Eevee,preview,shader,simple lighting,transparency,viewport shading,material preview,node editor,real-time rendering,refractive shader,BSDF,screen space reflections,alpha blend,render engine,glass BSDF,roughness,IOR,shader nodes,viewport performance

        問題：用表格展示python bpy常用工具
        回答：Python,bpy,API,Blender scripting,Blender addon,table display,UI panel,operator,property,layout,script editor,automation,developer tools,object manipulation,mesh editing,data access,custom tool,addon development,interface,code example

        問題：{question}
        關鍵字：

        格式務必與上述範例完全相同，否則將導致解析失敗。
    """)

    # 呼叫LLM生成關鍵字
    try:
        response = model_ollama.query_ollama(prompt, model_name)
        print(f"生成關鍵字的回應: {response}")
        return response
    except Exception as e:
        print(f"生成關鍵字時發生錯誤: {e}")
        return []


def retrieve_relevant_texts(query: str) -> List[Dict[str, Any]]:
    """使用查詢來檢索最相關的文本"""
    try:
        query_vector = model_embedding.encode_text([query])[0].astype("float32").reshape(1, -1)
        results = model_faiss.query_index(query_vector)
        print("檢索到的相關文本:")
        for i, result in enumerate(results):
            print(f"結果 {i + 1}: 來源: {result['file']}, 相似度: {result['similarity']}")
        return results
    except Exception as e:
        print(f"查詢索引時發生錯誤: {e}")
        return []


def build_prompt(query: str, texts: List[Dict[str, Any]]) -> str:
    """構建發送給LLM的prompt"""
    context_texts = []
    for text in texts:
        if text["similarity"] < 0.4:
            continue

        # 添加來源和內容到上下文
        context_text = textwrap.dedent(f"""\
            [文件 {text["file"]}]
            與該問題的相關性: {text["similarity"]:.2f}
            內容: {text["content"]}
        """)
        context_texts.append(context_text)

    # 組合完整的prompt
    context_texts_joined = "\n\n".join(context_texts)
    prompt = textwrap.dedent(f"""\
        你是 Blender 官方手冊的專業導覽員，負責協助繁體中文使用者查詢 **Blender 4.2** 版功能與操作說明。

        請注意以下規則：
        - 必須**全程使用正體中文**回答，**不可混用簡體字**。
        - 回答必須**僅根據提供的參考文件內容**，**不得引用未提供的外部資訊**。
        - 如果參考文件中**無法找到足夠資訊**，請明確說明「**無法回答**」，**禁止推測或自行編造內容**。
        - 如果問題與 Blender 無關，請禮貌地回應：「此問題超出 Blender 手冊的範圍，無法回答。」

        系統根據問題找到的參考文件：
        {context_texts_joined}

        特別指引：
        - 請綜合所有參考文件內容進行回答，**避免僅依賴單一文件**，除非只有一份資料可用。
        - 請根據現有文件內容，主動列出2～3個具體的後續提問範例（例如：「如何設定剛體物理效果？」「如何使用Subdivision Surface細分物件？」），
          這些範例必須與參考文件中提及的功能相關，不得超出文件範圍自行假設。
        - 若參考文件內容不足以提出2～3個具體提問，請酌情列出可行範例或略過此步驟。

        最後請保持回答的：
        - 條理清晰
        - 使用 Blender 專有名詞時，儘量保留原文並加上中文說明（例如：「Subdivision Surface（細分曲面）」）

        使用者的問題是：
        {query}

        請以專業且親切的態度，給出最適切且詳盡的回答。
    """)
    return prompt


def process_query(question: str, model_name: str = model_ollama.OLLAMA_MODEL):
    """處理用戶查詢並以流式方式返回回答"""
    try:
        # 檢索相關文本塊
        print(f"正在處理問題: '{question}'")
        keywords = generate_keywords(question, model_name)
        relevant_texts = retrieve_relevant_texts(keywords)

        if not relevant_texts:
            yield "很抱歉，無法找到相關資訊。請嘗試重新表達您的問題，或檢查索引是否正確建立。"
            return

        # 構建prompt，向Ollama請求流式回答
        prompt = build_prompt(question, relevant_texts)
        print(f"向Ollama ({model_name}) 發送流式請求...")
        yield from model_ollama.query_ollama_stream(prompt, model_name)

    except Exception as e:
        error_msg = f"處理查詢時發生錯誤: {e}"
        print(error_msg)
        yield error_msg
