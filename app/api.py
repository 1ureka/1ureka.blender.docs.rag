#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
api.py - Blender手冊RAG系統的API服務

此腳本提供基於FastAPI的HTTP API服務，允許用戶通過HTTP請求查詢Blender手冊，
並獲得基於RAG系統的中文回答。服務會在啟動時預載向量模型和索引，
以加快查詢速度。
"""

import os
import sys
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# 添加腳本目錄到模塊搜索路徑
SCRIPT_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.append(str(SCRIPT_DIR))

# 導入查詢模塊
from query import load_model, load_index_and_chunks, process_query, OLLAMA_MODEL

# 創建FastAPI應用
app = FastAPI(
    title="Blender手冊RAG API",
    description="使用自然語言查詢Blender官方手冊，獲取中文回答",
    version="1.0.0"
)

# 配置跨域資源共享(CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允許所有來源
    allow_credentials=True,
    allow_methods=["*"],  # 允許所有方法
    allow_headers=["*"],  # 允許所有頭部
)

# 定義請求模型
class QueryRequest(BaseModel):
    question: str
    model: Optional[str] = OLLAMA_MODEL

# 定義響應模型
class QueryResponse(BaseModel):
    success: bool
    answer: str
    elapsed_time: float
    model: str

# 全局變數，用於追蹤加載狀態
loading_status = {
    "is_loading": False,
    "loaded": False,
    "error": None
}

# 後台任務：預載模型和索引
def preload_resources():
    global loading_status
    try:
        loading_status["is_loading"] = True

        # 載入模型和索引
        if load_model() and load_index_and_chunks()[0]:
            loading_status["loaded"] = True
            loading_status["error"] = None
            print("資源預載完成，系統準備就緒")
        else:
            loading_status["error"] = "資源載入失敗，請檢查日誌"
            print("錯誤：資源預載失敗")
    except Exception as e:
        loading_status["error"] = f"預載資源時發生錯誤: {str(e)}"
        print(f"錯誤：{loading_status['error']}")
    finally:
        loading_status["is_loading"] = False

@app.on_event("startup")
async def startup_event():
    """應用啟動時，啟動後台任務預載資源"""
    background_tasks = BackgroundTasks()
    background_tasks.add_task(preload_resources)
    # 執行後台任務
    preload_resources()

@app.get("/")
async def root():
    """API根路徑，提供服務資訊"""
    return {
        "service": "Blender手冊RAG API",
        "version": "1.0.0",
        "status": "運行中",
        "endpoints": [
            {"path": "/", "method": "GET", "description": "API資訊"},
            {"path": "/status", "method": "GET", "description": "檢查服務狀態"},
            {"path": "/query", "method": "POST", "description": "查詢Blender手冊"}
        ]
    }

@app.get("/status")
async def status():
    """檢查API服務狀態"""
    return {
        "status": "ready" if loading_status["loaded"] else "loading" if loading_status["is_loading"] else "error",
        "error": loading_status["error"],
        "is_loading": loading_status["is_loading"],
        "loaded": loading_status["loaded"]
    }

@app.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    """處理用戶查詢請求"""
    # 檢查系統是否已準備就緒
    if not loading_status["loaded"]:
        if loading_status["is_loading"]:
            raise HTTPException(status_code=503, detail="系統正在載入資源，請稍後再試")
        else:
            raise HTTPException(status_code=500, detail=f"系統未能正確初始化: {loading_status['error']}")

    # 獲取請求參數
    question = request.question.strip()
    model = request.model

    # 驗證問題不為空
    if not question:
        raise HTTPException(status_code=400, detail="問題不能為空")

    # 處理查詢
    try:
        result = process_query(question, model)
        return {
            "success": result["success"],
            "answer": result["answer"],
            "elapsed_time": result["elapsed_time"],
            "model": model
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"處理查詢時發生錯誤: {str(e)}")

# 啟動服務的入口點（當直接執行此文件時）
if __name__ == "__main__":
    # 從環境變量或使用默認值獲取主機和端口
    host = os.environ.get("API_HOST", "0.0.0.0")
    port = int(os.environ.get("API_PORT", "7860"))

    # 啟動 Uvicorn 服務器
    print(f"啟動 Blender手冊RAG API 服務於 http://{host}:{port}")
    uvicorn.run("api:app", host=host, port=port, reload=False)
