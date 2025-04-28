#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
model_embedding.py - 向量嵌入模型加載模組

此模組負責載入和初始化文本向量化的模型，
提供GPU加速支援，在系統啟動時預先載入模型以加速後續操作。
"""

from typing import Optional
from sentence_transformers import SentenceTransformer

# 使用多語言模型，支援中英文
MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"  # 支援中英文的多語言模型

# 全局變數用於快取已載入的模型
_model = None


def load_model() -> Optional[SentenceTransformer]:
    """
    載入多語言向量模型，支援GPU加速
    """
    global _model

    # 如果模型已載入，直接返回
    if _model is not None:
        return _model

    try:
        import torch

        # 檢查GPU是否可用
        device = "cuda" if torch.cuda.is_available() else "cpu"
        model = SentenceTransformer(MODEL_NAME, device=device)
        print(f"向量模型載入成功，使用裝置：{device}")

        # 快取模型
        _model = model
        return model
    except Exception as e:
        print(f"載入向量模型時發生錯誤: {e}")
        return None


def encode_text(texts):
    """將文本編碼為向量

    Args:
        texts: 要編碼的文本或文本列表
        show_progress: 是否顯示進度條

    Returns:
        編碼後的向量
    """
    model = load_model()
    if model is None:
        raise RuntimeError("模型載入失敗，無法編碼文本")

    return model.encode(texts, show_progress_bar=False)
