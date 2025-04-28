#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
model_ollama.py - Ollama API 串接模組

此腳本提供與 Ollama API 的通信功能，支援流式輸出和錯誤處理。
"""

import json
import requests
from typing import Iterator

# 設定 Ollama 相關參數
OLLAMA_API_URL = "http://ollama:11434/api/generate"
OLLAMA_MODEL = "gemma3:4b-it-q8_0"  # 默認使用的模型名稱
OLLAMA_CONTEXT_LENGTH = 8192 * 2  # Ollama模型的上下文長度限制


def query_ollama_stream(prompt: str, model: str = OLLAMA_MODEL) -> Iterator[str]:
    """
    向Ollama API發送流式請求並逐步返回回答
    """
    try:
        payload = {"model": model, "prompt": prompt, "stream": True, "options": {"num_ctx": OLLAMA_CONTEXT_LENGTH}}
        response = requests.post(OLLAMA_API_URL, json=payload, stream=True)

        if response.status_code != 200:
            error_msg = f"Ollama API請求失敗: HTTP {response.status_code} - {response.text}"
            print(error_msg)
            yield f"處理您的問題時發生錯誤: {error_msg}"
            return

        for line in response.iter_lines():
            if not line:
                continue

            try:
                data = json.loads(line.decode("utf-8"))
            except json.JSONDecodeError as e:
                print(f"解析JSON回應時發生錯誤: {e}")
                continue

            chunk = data.get("response")
            if chunk:
                yield chunk

            if data.get("done"):
                break

    except Exception as e:
        error_msg = f"Ollama API流式請求過程中發生錯誤: {str(e)}"
        print(error_msg)
        yield f"處理您的問題時發生錯誤: {error_msg}"
