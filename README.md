<p align="center">
  <a href="README-zh_CN.md">简体中文</a> •
  <a href="README-zh_TW.md">繁體中文</a> •
  <a href="README.md">English</a>
</p>

<p align="center">
  <img src="static/icon.svg" alt="OpenClaw Auto Manager" width="120"/>
</p>

<h1 align="center">OpenClaw Auto Manager</h1>

<p align="center">
  <strong>Multi-vendor API key manager for <a href="https://github.com/anthropics/openclaw">OpenClaw</a></strong>
</p>

<p align="center">
  <a href="#quick-start">Quick Start</a> •
  <a href="#features">Features</a> •
  <a href="#supported-providers">Providers</a> •
  <a href="#configuration">Config</a> •
  <a href="#license">License</a>
</p>

---

A visual multi-vendor API key manager designed for OpenClaw. Add, detect, and sync your AI provider API keys with one click. Supports 26+ mainstream providers with automatic health checking and OpenClaw configuration sync.

## Features

- **Multi-vendor Management** — Left panel for providers, right panel for API keys
- **26+ Built-in Providers** — OpenAI, Anthropic, DeepSeek, Groq, Google Gemini, xAI, Together AI, and more
- **Provider-specific Health Checks** — Each provider uses the correct API format for probing
- **OpenClaw Auto-Sync** — Healthy keys auto-sync to OpenClaw config, unhealthy keys auto-remove
- **Enable/Disable Keys** — Toggle keys to auto-sync or remove from OpenClaw config
- **Batch Import** — Paste text to auto-parse URL + API Key + provider
- **Light/Dark Theme** — One-click toggle, saves preference
- **Multi-language** — English / 简体中文 / 繁體中文
- **Gateway Status** — View and restart OpenClaw Gateway
- **Remote Gateway** — Connect to remote OpenClaw via SSH or Gateway API

## Quick Start

```bash
# Clone
git clone https://github.com/YOUR_USER/openclaw-auto-manager.git
cd openclaw-auto-manager

# Install dependencies
pip install -r requirements.txt

# Start
python3 app.py
# → Open http://127.0.0.1:8787

# Click "Sync from OpenClaw" to import existing config
```

**Requirements**: Python 3.9+, OpenClaw CLI installed and configured

**Compatible with**: OpenClaw 2026.3.0+ (recommended: 2026.6.11+)

### Docker

```bash
docker compose up -d
# → Open http://127.0.0.1:8787
```

## Usage

### Add a Provider

Click **+ Add Vendor** → Select provider from dropdown (auto-fills URL) → Enter name → Save

### Add an API Key

Select provider → Click **+ Add Key** → Enter name and key → Save

### Health Check

- Single check: Click **Check** on the key row
- Check all: Click **Check All Health** in toolbar
- Healthy key → auto-sync to OpenClaw
- Unhealthy key → removed from OpenClaw and disabled (kept in system)

### Batch Import

Supported format (one per line):

```
openai https://api.openai.com/v1 sk-proj-xxxx...
deepseek https://api.deepseek.com/v1 sk-xxxx...
https://api.groq.com/openai/v1 gsk_xxxx...
```

Auto-detects URL → matches provider → preview → one-click import

## Supported Providers

| Check Type | Providers |
|---|---|
| `openai_chat` | OpenAI, DeepSeek, OpenRouter, Groq, Together AI, xAI, Perplexity, Mistral, Cohere, Moonshot, Z.AI, MiniMax, Alibaba (Qwen), Volcengine, Fireworks, StepFun, DeepInfra, Cerebras, Novita, Venice, 01.AI, Ollama, Qianfan, Xiaomi |
| `anthropic` | Anthropic |
| `gemini` | Google Gemini |

Unknown providers default to `openai_chat` probe.

## Configuration

| Item | Path |
|---|---|
| Manager data | `~/.openclaw-auto-manager/data.json` |
| Health cache | `~/.openclaw-auto-manager/health_cache.json` |
| OpenClaw config | `~/.openclaw/openclaw.json` |
| Port | `8787` (env: `OPENCLAW_MANAGER_PORT`) |

## Security

> **API Keys are stored in `~/.openclaw-auto-manager/data.json`.**
> This file is NOT inside the project directory.
> Never commit it to version control.

## Tech Stack

- **Backend**: Python + Flask
- **Frontend**: Vanilla JS + CSS Variables theming
- **Storage**: JSON file (no database needed)
- **i18n**: Client-side locale switching

## Roadmap

- [ ] Key search/filter
- [ ] Batch operations (multi-select enable/disable/delete)
- [ ] Webhook alerts on key failure
- [ ] Key usage statistics
- [ ] Export/import config
- [ ] PWA support

## License

Apache 2.0
