<p align="center">
  <img src="static/icon.svg" alt="OpenClaw Auto Manager" width="120"/>
</p>

<h1 align="center">OpenClaw Auto Manager</h1>

<p align="center">
  <strong>OpenClaw 多供應商 API Key 視覺化管理工具</strong>
</p>

<p align="center">
  <a href="#快速開始">快速開始</a> •
  <a href="#功能特性">功能</a> •
  <a href="#支援的供應商">供應商</a> •
  <a href="#設定說明">設定</a> •
  <a href="#開源協議">協議</a>
</p>

---

多供應商 API Key 視覺化管理工具，專為 [OpenClaw](https://github.com/anthropics/openclaw) 設計。一鍵新增、偵測、同步你的 AI 供應商 API Key，支援 26+ 主流供應商，自動健康偵測與 OpenClaw 設定同步。

## 功能特性

- **多供應商管理** — 左欄供應商列表，右欄 Key 表格，一目瞭然
- **26+ 內建供應商** — OpenAI、Anthropic、DeepSeek、Groq、Google Gemini、xAI、Together AI 等
- **供應商專屬健康偵測** — 每種供應商用正確的 API 格式探測
- **OpenClaw 自動同步** — 健康 Key 自動寫入設定，不健康 Key 自動移除
- **啟用/停用** — 切換 Key 時自動同步或移除 OpenClaw 設定
- **批次匯入** — 貼上文字自動解析 URL + API Key + 供應商
- **淺色/暗色主題** — 一鍵切換，儲存偏好
- **多語言** — English / 簡體中文 / 繁體中文
- **閘道狀態** — 檢視和重新啟動 OpenClaw Gateway
- **遠端閘道** — 透過 SSH 或 Gateway API 連線遠端 OpenClaw

## 快速開始

```bash
# 複製
git clone https://github.com/kingkate2009-droid/openclaw-auto-manager.git
cd openclaw-auto-manager

# 安裝相依套件
pip install -r requirements.txt

# 啟動
python3 app.py
# → 瀏覽器開啟 http://127.0.0.1:8787

# 點選 "Sync from OpenClaw" 同步現有設定
```

**要求**: Python 3.9+，OpenClaw CLI 已安裝並設定

### Docker

```bash
docker compose up -d
# → 瀏覽器開啟 http://127.0.0.1:8787
```

## 使用方法

### 新增供應商

點選 **+ Add Vendor** → 從下拉選單選擇供應商（自動填入 URL）→ 輸入名稱 → 儲存

### 新增 API Key

選中供應商 → 點選 **+ Add Key** → 輸入名稱和 Key → 儲存

### 健康偵測

- 單一偵測：點選 Key 列中的 **Check**
- 全部偵測：頂部工具列 **Check All Health**
- 健康 Key → 自動同步到 OpenClaw
- 不健康 Key → 從 OpenClaw 移除並停用（保留在系統內）

### 批次匯入

支援格式（每行一個）：

```
openai https://api.openai.com/v1 sk-proj-xxxx...
deepseek https://api.deepseek.com/v1 sk-xxxx...
https://api.groq.com/openai/v1 gsk_xxxx...
```

自動辨識 URL → 匹配供應商 → 預覽 → 一鍵匯入

## 支援的供應商

| 偵測類型 | 供應商 |
|---|---|
| `openai_chat` | OpenAI、DeepSeek、OpenRouter、Groq、Together AI、xAI、Perplexity、Mistral、Cohere、Moonshot、Z.AI、MiniMax、阿里雲 (Qwen)、火山引擎、Fireworks、StepFun、DeepInfra、Cerebras、Novita、Venice、01.AI、Ollama、千帆、Xiaomi |
| `anthropic` | Anthropic |
| `gemini` | Google Gemini |

未知供應商預設使用 `openai_chat` 探測。

## 設定說明

| 項目 | 路徑 |
|---|---|
| 管理器資料 | `~/.openclaw-auto-manager/data.json` |
| 健康快取 | `~/.openclaw-auto-manager/health_cache.json` |
| OpenClaw 設定 | `~/.openclaw/openclaw.json` |
| 連接埠 | `8787`（環境變數：`OPENCLAW_MANAGER_PORT`） |

## 安全說明

> **API Key 儲存在 `~/.openclaw-auto-manager/data.json` 中。**
> 此檔案不在專案目錄內。
> 請勿將其提交到版本控制。

## 技術棧

- **後端**: Python + Flask
- **前端**: 原生 JS + CSS Variables 主題
- **儲存**: JSON 檔案（無需資料庫）
- **國際化**: 客戶端語言切換

## 開發路線

- [ ] Key 模糊搜尋
- [ ] 批次操作（多選啟用/停用/刪除）
- [ ] Webhook 告警
- [ ] Key 使用統計
- [ ] 匯出/匯入設定
- [ ] PWA 支援

## 開源協議

Apache 2.0
