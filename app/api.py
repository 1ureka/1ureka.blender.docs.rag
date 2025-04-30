#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
api.py - Blender手冊RAG系統的API服務

此腳本提供基於FastAPI的HTTP API服務，允許用戶通過HTTP請求查詢Blender手冊。
"""

from typing import Literal
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import opencc
import asyncio
import logging

from scripts import model_embedding
from scripts import model_faiss
from scripts import query

# 全局變數
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
converter = opencc.OpenCC("s2t.json")  # 簡轉繁
tag: Literal["idle", "loading", "error", "ok"] = "idle"  # 服務狀態標誌


def load_models_sync():
    """預載入模型和索引(同步)"""
    global tag
    try:
        tag = "loading"
        logger.info("正在載入向量嵌入模型與FAISS索引...")
        model_embedding.load_model()
        model_faiss.load_model()

        logger.info("正在載入Ollama模型中...")
        next(query.process_query("你好"))

        logger.info("模型準備就緒!")
        tag = "ok"
    except Exception as e:
        logger.info(f"載入模型時發生錯誤: {e}")
        tag = "error"


async def load_models():
    """預載入模型和索引(異步)"""
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, load_models_sync)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """在應用啟動時預載入模型和索引"""
    asyncio.create_task(load_models())
    logger.info("API服務啟動中...")
    yield


app = FastAPI(
    title="Blender手冊RAG API",
    description="透過RAG技術為Blender繁體中文使用者提供快速查詢服務",
    version="1.0.0",
    lifespan=lifespan,
)

# 添加CORS支援，使API可以被前端頁面調用
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允許所有來源
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """API根路徑，提供服務資訊"""
    return {
        "service": "Blender手冊RAG API",
        "version": "1.0.0",
        "status": tag,
        "endpoints": [
            {"path": "/", "method": "GET", "description": "API服務狀態與資訊"},
            {"path": "/query", "method": "GET", "description": "查詢Blender手冊"},
        ],
    }


@app.get("/query")
async def handle_query(question: str = Query(..., description="提問問題")):
    """處理Blender手冊查詢請求"""
    # 檢查服務是否就緒
    if tag != "ok":
        raise HTTPException(status_code=503, detail="服務正在啟動中，請稍後再試")

    # 檢查查詢文本是否為空
    if not question or question.strip() == "":
        raise HTTPException(status_code=400, detail="查詢內容不能為空")

    # 處理查詢
    try:
        # 將每個文本塊轉換為SSE格式的事件
        def stream_response():
            for text_chunk in query.process_query(question):
                safe_chunk = converter.convert(text_chunk).replace("\n", "\\n")
                yield f"data: {safe_chunk}\n\n"

        # 返回流式響應
        return StreamingResponse(stream_response(), media_type="text/event-stream")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"處理查詢時發生錯誤: {str(e)}")
