#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
api.py - Blender手冊RAG系統的API服務

此腳本提供基於FastAPI的HTTP API服務，允許用戶通過HTTP請求查詢Blender手冊，
並獲得基於RAG系統的中文回答。服務會在啟動時預載向量模型和索引，
啟動完成前，會禁止回應，並且透過/status可知道目前是否準備完成。
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import time

from scripts import model_embedding
from scripts import model_faiss
from scripts import query

# 初始化 FastAPI 應用
app = FastAPI(
    title="Blender手冊RAG API", description="透過RAG技術為Blender繁體中文使用者提供快速查詢服務", version="1.0.0"
)

# 添加CORS支援，使API可以被前端頁面調用
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允許所有來源
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 定義查詢請求的數據模型
class QueryRequest(BaseModel):
    question: str
    model: str = "gemma3:4b-it-q8_0"  # 默認使用 gemma3:4b-it-q8_0 模型


# 服務狀態標誌
SERVICE_READY = False


# 在應用啟動時預加載模型和索引
@app.on_event("startup")
async def startup_event():
    global SERVICE_READY
    try:
        print("正在加載向量嵌入模型...")
        model_embedding.load_model()

        print("正在加載FAISS索引...")
        model_faiss.load_model()

        print("API服務準備就緒!")
        SERVICE_READY = True
    except Exception as e:
        print(f"啟動服務時發生錯誤: {e}")
        # 不設置 SERVICE_READY = True，服務將保持未就緒狀態


@app.get("/")
async def root():
    """API根路徑，提供服務資訊"""
    return {
        "service": "Blender手冊RAG API",
        "version": "1.0.0",
        "status": "運行中" if SERVICE_READY else "正在初始化",
        "endpoints": [
            {"path": "/", "method": "GET", "description": "API資訊"},
            {"path": "/status", "method": "GET", "description": "檢查服務狀態"},
            {"path": "/query", "method": "POST", "description": "查詢Blender手冊"},
        ],
    }


@app.get("/status")
async def check_status():
    """檢查服務狀態"""
    return {
        "ready": SERVICE_READY,
        "timestamp": time.time(),
        "message": "服務已就緒，可以接受查詢" if SERVICE_READY else "服務正在初始化，請稍後再試",
    }


@app.post("/query")
async def handle_query(request: QueryRequest):
    """處理Blender手冊查詢請求"""
    # 檢查服務是否就緒
    if not SERVICE_READY:
        raise HTTPException(status_code=503, detail="服務正在初始化中，請稍後再試")

    # 檢查查詢文本是否為空
    if not request.question or request.question.strip() == "":
        raise HTTPException(status_code=400, detail="查詢內容不能為空")

    # 處理查詢
    try:

        def stream_response():
            # 使用正確的模型名稱
            for text_chunk in query.process_query(request.question, request.model):
                # 將每個文本塊轉換為SSE格式的事件
                yield f"data: {text_chunk}\n\n"

        # 返回流式響應
        return StreamingResponse(stream_response(), media_type="text/event-stream")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"處理查詢時發生錯誤: {str(e)}")


# 為所有請求添加處理中間件
@app.middleware("http")
async def check_readiness(request: Request, call_next):
    """確保服務就緒後才處理查詢請求"""
    # 允許直接訪問狀態和根端點，即使服務未就緒
    if request.url.path in ["/status", "/"]:
        return await call_next(request)

    # 對於其他端點，如果服務未就緒則返回503錯誤
    if not SERVICE_READY and request.url.path != "/status":
        return JSONResponse(status_code=503, content={"detail": "服務正在初始化中，請稍後再試"})

    # 處理請求
    try:
        return await call_next(request)
    except Exception as e:
        return JSONResponse(status_code=500, content={"detail": f"處理請求時發生錯誤: {str(e)}"})


# 直接運行此文件時執行的代碼
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=7860)
