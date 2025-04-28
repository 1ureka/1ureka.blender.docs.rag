# 什麼是 Blender-Docs-RAG-Assistant？

Blender 官方的繁體中文手冊，大部分仍都是英文，就算會英文，想出英文關鍵字查詢文件困難又耗時。
Blender-Docs-RAG-Assistant 讓你可以直接用繁體中文提問，
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

## 3. 拉取模型

第一次啟動時，Ollama 服務預設沒有任何模型，需要先拉取。

程式碼預設使用的模型是：

```
gemma3:4b-it-q8_0
```

如果不更換模型，請直接向 [Ollama 的 API](https://github.com/ollama/ollama/blob/main/docs/api.md#pull-a-model) 發送以下請求：

```bash
curl -X POST http://localhost:11434/api/pull \
  -H "Content-Type: application/json" \
  -d '{"model": "gemma3:4b-it-q8_0"}'
```

如果想更換其他模型：
- 請參考 Ollama 官方的[模型列表](https://ollama.com/search)
- 並修改 `scripts/model_ollama.py` 檔案中的 `OLLAMA_MODEL` 變數。

## 注意事項

- 首次使用必須先執行 `build`
- 若 Blender 手冊有更新，重新 `build`即可

---

# 使用方式

Blender-Docs-RAG-Assistant 提供了一個簡單易用的 API，能夠輕鬆地將 Blender 手冊查詢功能整合到前端專案中。

## API 端點

API 伺服器運行於 `http://localhost:7860`，提供以下端點：

| 端點      | 方法   | 說明                      |
|----------|-------|--------------------------|
| `/`      | GET   | 獲取 API 基本資訊與狀態      |
| `/status`| GET   | 檢查服務是否已準備就緒        |
| `/query` | GET   | 向 Blender 手冊提出查詢問題  |

## `/`

以下是使用 TypeScript 訪問根端點的示例代碼，返回 API 的基本信息：

```typescript
interface ApiEndpoint {
  path: string;
  method: string;
  description: string;
}

interface ApiInfo {
  service: string;
  version: string;
  status: string;
  endpoints: ApiEndpoint[];
}

/**
 * 獲取 Blender-RAG API 的基本信息
 * @returns API 基本信息
 */
async function getApiInfo(): Promise<ApiInfo> {
  const response = await fetch('http://localhost:7860/');
  if (!response.ok) {
    throw new Error(`HTTP error! Status: ${response.status}`);
  }
  return await response.json() as ApiInfo;
}

// 使用示例
getApiInfo()
  .then(info => {
    console.log(`服務名稱: ${info.service}`);
    console.log(`版本: ${info.version}`);
    console.log(`狀態: ${info.status}`);
    console.log('可用端點:');
    info.endpoints.forEach(endpoint => {
      console.log(`- ${endpoint.path} (${endpoint.method}): ${endpoint.description}`);
    });
  })
  .catch(error => console.error('獲取 API 信息時出錯:', error));
```

## `/status`

在進行查詢前，建議先檢查服務是否已準備就緒：

```typescript
interface StatusResponse {
  ready: boolean;
  timestamp: number;
  message: string;
}

/**
 * 檢查 Blender-RAG API 服務狀態
 * @returns 服務狀態信息
 */
async function checkApiStatus(): Promise<StatusResponse> {
  const response = await fetch('http://localhost:7860/status');
  if (!response.ok) {
    throw new Error(`HTTP error! Status: ${response.status}`);
  }
  return await response.json() as StatusResponse;
}

// 使用示例
checkApiStatus()
  .then(status => {
    if (status.ready) {
      console.log(`服務已就緒: ${status.message}`);
      console.log(`時間戳: ${new Date(status.timestamp * 1000).toLocaleString()}`);
      // 服務就緒，可以開始查詢
      startQuerying();
    } else {
      console.log(`服務尚未就緒: ${status.message}`);
      console.log('請稍後再試...');
      // 可以設置定時器稍後再次檢查
      setTimeout(checkApiStatus, 5000);
    }
  })
  .catch(error => console.error('檢查 API 狀態時出錯:', error));
```

## `/query`

API 提供的是 Server-Sent Events (SSE) 格式的流式回應，以下是使用 TypeScript 實現的查詢功能：

```typescript
interface QueryOptions {
  onData?: (text: string) => void; // 接收流式數據的回調
  onComplete?: () => void; // 數據流結束時的回調
  onError?: (error: Error) => void; // 發生錯誤時的回調
}

/**
 * 向 Blender RAG API 發送查詢並處理流式響應
 * @param question 要查詢的問題
 * @param options 查詢選項
 * @returns 包含關閉連接方法的對象
 */
function queryBlenderRAG(question: string, options: QueryOptions = {}) {
  // 預設選項
  const {
    onData = (text: string) => console.log(text),
    onError = (error: Error) => console.error('查詢錯誤:', error),
    onComplete = () => console.log('查詢完成'),
  } = options;

  // 編碼查詢參數
  const encodedQuestion = encodeURIComponent(question);
  const url = `http://localhost:7860/query?question=${encodedQuestion}`;

  // 累積的回應文本
  let fullResponse = '';

  // 創建 EventSource 連接
  const eventSource = new EventSource(url);

  // 處理收到的數據
  eventSource.onmessage = (event) => {
    const text = event.data;
    fullResponse += text;
    onData(text);
  };

  // 處理連接完成
  eventSource.onopen = () => {
    console.log('SSE 連接已建立');
  };

  // 處理錯誤
  eventSource.onerror = (error) => {
    eventSource.close();
    if (fullResponse) {
      // 如果已收到部分回應，視為完成
      onComplete();
    } else {
      // 否則視為錯誤
      onError(new Error('SSE 連接錯誤'));
    }
  };

  // 返回控制對象
  return {
    close: () => {
      eventSource.close();
      onComplete();
    },
    getFullResponse: () => fullResponse
  };
}
```

---

# docker-compose.yml 概要

```yaml
services:
  ollama:
    image: ollama/ollama
    ports:
      - "11434:11434"
    volumes:
      - ./data/ollama:/root/.ollama
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
    environment:
      - PYTHONPATH=/app
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
opencc                   # 萬一AI仍不小心返回簡體，轉換成繁體中文
```

---

# 完整樹狀圖

```bash
blender.docs.rag/
├── app/
│   └── api.py       # 提供查詢 API
├── data/
│   ├── html/        # 原始 HTML 資料
│   ├── texts/       # 清理後的純文字
│   ├── index/       # FAISS 向量資料庫
│   └── ollama/      # Ollama 模型資料
├── scripts/
│   ├── build.py             # 主要整合腳本，統一協調處理流程
│   ├── build_download.py    # 下載 Blender 官方手冊 ZIP 檔案
│   ├── build_clean.py       # 將 HTML 轉換成純文字格式
│   ├── build_vectorize.py   # 文本分段並建立向量索引
│   ├── build_validate.py    # 驗證向量索引功能正確性
│   ├── model_embedding.py   # 多語言向量嵌入模型管理
│   ├── model_faiss.py       # FAISS 向量索引管理與查詢
│   ├── model_ollama.py      # Ollama API 串接與處理
│   └── query.py             # 查詢處理與 Prompt 組合
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

註：
- [Blender 官方手冊](https://docs.blender.org/manual/en/latest/blender_manual_html.zip)
