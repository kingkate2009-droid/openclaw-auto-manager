<p align="center">
  <img src="static/icon.svg" alt="OpenClaw Auto Manager" width="120"/>
</p>

<h1 align="center">OpenClaw Auto Manager</h1>

<p align="center">
  <strong>OpenClaw 多供应商 API Key 可视化管理工具</strong>
</p>

<p align="center">
  <a href="#快速开始">快速开始</a> •
  <a href="#功能特性">功能</a> •
  <a href="#支持的供应商">供应商</a> •
  <a href="#配置说明">配置</a> •
  <a href="#开源协议">协议</a>
</p>

---

多供应商 API Key 可视化管理工具，专为 [OpenClaw](https://github.com/anthropics/openclaw) 设计。一键添加、检测、同步你的 AI 供应商 API Key，支持 26+ 主流供应商，自动健康检测与 OpenClaw 配置同步。

## 功能特性

- **多供应商管理** — 左栏供应商列表，右栏 Key 表格，一目了然
- **26+ 内置供应商** — OpenAI、Anthropic、DeepSeek、Groq、Google Gemini、xAI、Together AI 等
- **供应商专属健康检测** — 每种供应商用正确的 API 格式探测
- **OpenClaw 自动同步** — 健康 Key 自动写入配置，不健康 Key 自动移除
- **启用/禁用** — 开关 Key 时自动同步或移除 OpenClaw 配置
- **批量导入** — 粘贴文本自动解析 URL + API Key + 供应商
- **浅色/暗色主题** — 一键切换，保存偏好
- **多语言** — English / 简体中文 / 繁體中文
- **网关状态** — 查看和重启 OpenClaw Gateway
- **远程网关** — 通过 SSH 或 Gateway API 连接远程 OpenClaw

## 快速开始

```bash
# 克隆
git clone https://github.com/kingkate2009-droid/openclaw-auto-manager.git
cd openclaw-auto-manager

# 安装依赖
pip install -r requirements.txt

# 启动
python3 app.py
# → 浏览器打开 http://127.0.0.1:8787

# 点击 "Sync from OpenClaw" 同步现有配置
```

**要求**: Python 3.9+，OpenClaw CLI 已安装并配置

### Docker

```bash
docker compose up -d
# → 浏览器打开 http://127.0.0.1:8787
```

## 使用方法

### 添加供应商

点击 **+ Add Vendor** → 从下拉菜单选择供应商（自动填入 URL）→ 输入名称 → 保存

### 添加 API Key

选中供应商 → 点击 **+ Add Key** → 输入名称和 Key → 保存

### 健康检测

- 单个检测：点击 Key 行中的 **Check**
- 全部检测：顶部工具栏 **Check All Health**
- 健康 Key → 自动同步到 OpenClaw
- 不健康 Key → 从 OpenClaw 移除并禁用（保留在系统内）

### 批量导入

支持格式（每行一个）：

```
openai https://api.openai.com/v1 sk-proj-xxxx...
deepseek https://api.deepseek.com/v1 sk-xxxx...
https://api.groq.com/openai/v1 gsk_xxxx...
```

自动识别 URL → 匹配供应商 → 预览 → 一键导入

## 支持的供应商

| 检测类型 | 供应商 |
|---|---|
| `openai_chat` | OpenAI、DeepSeek、OpenRouter、Groq、Together AI、xAI、Perplexity、Mistral、Cohere、Moonshot、Z.AI、MiniMax、阿里云 (Qwen)、火山引擎、Fireworks、StepFun、DeepInfra、Cerebras、Novita、Venice、01.AI、Ollama、千帆、Xiaomi |
| `anthropic` | Anthropic |
| `gemini` | Google Gemini |

未知供应商默认使用 `openai_chat` 探测。

## 配置说明

| 项目 | 路径 |
|---|---|
| 管理器数据 | `~/.openclaw-auto-manager/data.json` |
| 健康缓存 | `~/.openclaw-auto-manager/health_cache.json` |
| OpenClaw 配置 | `~/.openclaw/openclaw.json` |
| 端口 | `8787`（环境变量：`OPENCLAW_MANAGER_PORT`） |

## 安全说明

> **API Key 存储在 `~/.openclaw-auto-manager/data.json` 中。**
> 此文件不在项目目录内。
> 请勿将其提交到版本控制。

## 技术栈

- **后端**: Python + Flask
- **前端**: 原生 JS + CSS Variables 主题
- **存储**: JSON 文件（无需数据库）
- **国际化**: 客户端语言切换

## 开发路线

- [ ] Key 模糊搜索
- [ ] 批量操作（多选启用/禁用/删除）
- [ ] Webhook 告警
- [ ] Key 使用统计
- [ ] 导出/导入配置
- [ ] PWA 支持

## 开源协议

Apache 2.0
