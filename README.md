# Blender-Manual-RAG-Assistant - 使用指南

---

## 🖥️ 本地依賴需求（Windows）

- 安裝 [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop/)（建議安裝最新版）
- 確認 Docker Desktop 設定啟用 WSL2
（Settings → Resources → WSL integration → 勾選「Enable integration with my default WSL distro」）

### 確認環境成功

請分別執行以下指令，並比對輸出結果：

```bash
docker --version
docker compose version
```
✅ 正常應顯示 Docker 版本與 Docker Compose 版本

```bash
docker info | findstr /i nvidia
```
✅ 正常應該能看到包含 `nvidia` 的字樣，例如：
`Runtimes: io.containerd.runc.v2 nvidia runc`
如果有看到 `nvidia` 出現，代表 GPU 支援設定成功。

---

## 🛠️ docker-compose.yml 概要

```yaml
version: "3.8"

services:
  ollama:
    image: ollama/ollama
    ports:
      - "11434:11434"
    deploy:
      resources:
        reservations:
          devices:
            - capabilities: [gpu]

  blender-rag-build:
    build: .
    profiles: ["build"]
    volumes:
      - .:/app
    command: python scripts/build.py
    deploy:
      resources:
        reservations:
          devices:
            - capabilities: [gpu]

  blender-rag-deploy:
    build: .
    ports:
      - "7860:7860"
    volumes:
      - .:/app
    command: uvicorn app.api:app --host 0.0.0.0 --port 7860
    depends_on:
      - ollama
    deploy:
      resources:
        reservations:
          devices:
            - capabilities: [gpu]
```

- 啟動 **ollama** 作為本地 LLM API 服務 (11434 端口)
- 使用 **blender-rag-build** 進行資料處理（必須指定 profile）
- 使用 **blender-rag-deploy** 啟動查詢服務

---

## 🛠️ Dockerfile 概要

```Dockerfile
FROM pytorch/pytorch:2.5.1-cuda12.1-cudnn9-runtime

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir --requirement requirements.txt

COPY . .
```

---

## 🛠️ requirements.txt 概要

```text
beautifulsoup4
lxml
requests
sentence-transformers
faiss-gpu-cu12
torch
transformers
uvicorn
fastapi
```

---

# 🚀 使用流程

## 1. Build：建立資料

```bash
docker compose --profile build up blender-rag-build
```

處理內容：
- 下載 Blender 官方手冊
- 清理 HTML 成純文字
- 分段 (chunk)
- 建立 FAISS 向量資料庫

## 2. Deploy：啟動服務

```bash
docker compose up
```

啟動內容：
- 啟動 Ollama 服務 (http://localhost:11434)
- 啟動 Blender-RAG 查詢 api server (http://localhost:7860)

## 👉 現在可以透過 HTTP API 直接 POST 查詢！

---

# 注意事項

- 首次使用必須先執行 `build`
- 若 Blender 手冊有更新，重新 `build`即可
- 如需切換模型，可在 Ollama 對應指令：
  ```bash
  docker exec -it ollama ollama run llama3
  ```

---

# 💼 完整樹狀圖

```bash
blender-rag-ai/
├── app/
│   └── api.py            # 提供查詢 API
├── data/
│   ├── raw_html/          # 原始 HTML 資料
│   ├── cleaned_texts/     # 清理後的純文字
│   └── faiss_index/       # FAISS 向量資料庫
├── scripts/
│   ├── crawl_blender_manual.py   # 下載 Blender 手冊
│   ├── clean_html_extract.py     # HTML 清理
│   ├── build_embedding_index.py  # 建向量資料庫
│   └── query_rag.py               # 查詢與組 Prompt
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```
