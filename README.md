# 什麼是 Blender-Manual-RAG-Assistant？

Blender 官方的繁體中文手冊，大部分仍都是英文，就算會英文，想出英文關鍵字查詢文件困難又耗時。
Blender-Manual-RAG-Assistant 讓你可以直接用繁體中文提問，
快速從完整官方文件中找到答案，並以中文清楚回覆。

---

# 本地依賴需求（Windows）

- 安裝 [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop/)（建議安裝最新版）
- 確認 Docker Desktop 設定啟用 WSL2
（Settings → Resources → WSL integration → 勾選「Enable integration with my default WSL distro」）

## 確認環境成功

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

# docker-compose.yml 概要

```yaml
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
    tty: true
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

# Dockerfile 概要

```Dockerfile
FROM pytorch/pytorch:2.5.1-cuda12.1-cudnn9-runtime

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir --requirement requirements.txt

RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')"

COPY . .
```

---

# requirements.txt 概要

```text
markdownify              # 將 HTML 轉換成純文字格式（Markdown）
lxml                     # 解析與處理 HTML/XML
requests                 # 下載 Blender 官方手冊 ZIP 檔案
hf_xet                   # 加速 Hugging Face 模型下載（可選）
sentence-transformers    # 中文/多語言向量化（Embedding）
faiss-gpu-cu12           # GPU 加速的向量搜尋資料庫 FAISS
torch
transformers
uvicorn                  # 輕量級 ASGI 伺服器
fastapi                  # 高效能 API 框架
```

---

# 使用流程

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
- 啟動 Blender-RAG 查詢 API server (http://localhost:7860)

Blender-RAG 查詢 API server 工作流程：
1. 接收使用者的中文問題
2. 進行向量化（Embedding）
3. 從 Blender 手冊中檢索最相關段落
4. 組合成 Prompt，發送給本地的 Ollama 模型
5. 取得模型回覆後，將中文回答回傳給使用者

## 👉 現在可以透過 HTTP API 直接 POST 查詢！
比如使用 curl 指令：

```bash
curl -X POST "http://localhost:7860/query" -H "Content-Type: application/json" -d '{"question":"如何在 Blender 中使用鏡像？"}'
```

## 注意事項

- 首次使用必須先執行 `build`
- 若 Blender 手冊有更新，重新 `build`即可
- 如需切換模型，可在 Ollama 對應指令：
  ```bash
  docker exec -it ollama ollama run llama3
  ```

---

# 完整樹狀圖

```bash
blender-rag-ai/
├── app/
│   └── api.py       # 提供查詢 API
├── data/
│   ├── html/        # 原始 HTML 資料
│   ├── texts/       # 清理後的純文字
│   └── index/       # FAISS 向量資料庫
├── scripts/
│   ├── download.py  # 下載 Blender 官方手冊
│   ├── clean.py     # HTML 清理成純文字
│   ├── index.py     # 建立向量索引
│   ├── validate.py  # 驗證向量索引
│   ├── build.py     # 整合處理流程
│   └── query.py     # 查詢與組 Prompt
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

註：
- [Blender 官方手冊](https://docs.blender.org/manual/en/latest/blender_manual_html.zip)
