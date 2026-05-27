<p align="center">
  <img src="img/Veltrix.svg" alt="Veltrix" width="280" height="280" />
</p>

<p align="center">
  <strong>Intelligent Network Control — Professional x-ui/V2Ray Server Management Dashboard</strong>
</p>

<p align="center">
  <a href="./CHANGELOG.md"><img src="https://img.shields.io/badge/version-0.4.0-00bfa6?style=for-the-badge" alt="Version" /></a>
  <a href="./LICENSE"><img src="https://img.shields.io/badge/license-Commercial-ef4444?style=for-the-badge" alt="License" /></a>
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/python-3.12+-3776ab?style=for-the-badge&logo=python&logoColor=white" alt="Python" /></a>
</p>

<p align="center">
  <a href="https://github.com/iPmartNetwork/Veltrix/stargazers"><img src="https://img.shields.io/github/stars/iPmartNetwork/Veltrix?style=for-the-badge&color=f59e0b" alt="Stars" /></a>
  <a href="https://github.com/iPmartNetwork/Veltrix/network/members"><img src="https://img.shields.io/github/forks/iPmartNetwork/Veltrix?style=for-the-badge&color=8b5cf6" alt="Forks" /></a>
  <a href="https://github.com/iPmartNetwork/Veltrix/issues"><img src="https://img.shields.io/github/issues/iPmartNetwork/Veltrix?style=for-the-badge&color=ef4444" alt="Issues" /></a>
  <a href="https://github.com/iPmartNetwork/Veltrix"><img src="https://img.shields.io/github/repo-size/iPmartNetwork/Veltrix?style=for-the-badge&color=06b6d4" alt="Repo Size" /></a>
</p>

<p align="center">
  <a href="https://github.com/iPmartNetwork/Veltrix/commits/master"><img src="https://img.shields.io/github/last-commit/iPmartNetwork/Veltrix?style=for-the-badge&color=6366f1" alt="Last Commit" /></a>
  <a href="https://github.com/iPmartNetwork/Veltrix/graphs/contributors"><img src="https://img.shields.io/github/contributors/iPmartNetwork/Veltrix?style=for-the-badge&color=ec4899" alt="Contributors" /></a>
</p>

<p align="center">
  <a href="#-quick-start">Quick Start</a> •
  <a href="#-features">Features</a> •
  <a href="#-architecture">Architecture</a> •
  <a href="#%EF%B8%8F-tech-stack">Tech Stack</a> •
  <a href="#-deployment">Deployment</a> •
  <a href="./README_FA.md">🇮🇷 فارسی</a> •
  <a href="./CHANGELOG.md">Changelog</a>
</p>

---

## 📋 Overview

**Veltrix** is a self-hosted operational dashboard for outbound sellers, network operators, and teams managing multiple x-ui/V2Ray servers. It consolidates server monitoring, outbound health checks, incident management, notifications, reporting, and commercial licensing into a single professional interface.

Designed as **commercial software** with a private License Server for activation and validation.

---

## ⚡ Quick Start

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/iPmartNetwork/Veltrix/master/scripts/install-linux.sh)
```

Or manually:

```bash
git clone https://github.com/iPmartNetwork/Veltrix.git
cd Veltrix
sudo bash scripts/install-linux.sh
```

Or with Docker:

```bash
docker compose up -d
```

---

## ✨ Features

### 🖥 Server Management

| Feature | Description |
|---------|-------------|
| Multi-panel | x-ui, 3x-ui, and Marzban support |
| Auth modes | Username/password or API Token |
| Sync | Automatic inbound synchronization |
| Health Score | 0–100 scoring with A–F grades |
| Tags | Categorize servers with custom tags |
| Bulk ops | Ping, sync, enable/disable multiple servers |

### 📡 Monitoring & Alerts

| Feature | Description |
|---------|-------------|
| TCP Ping | Per-outbound connectivity checks |
| Resources | CPU, RAM, disk, Xray status |
| Auto-disable | Outbounds disabled after N failures |
| IP Rotation | Alert when server IP changes |
| Traffic limits | Warning at 80%, alert at 100% |
| Real-time | SSE push updates to dashboard |

### 🔔 Incidents & Notifications

| Feature | Description |
|---------|-------------|
| Lifecycle | open → acknowledged → recovered |
| Telegram | Bot notifications + two-way commands |
| Webhook | Events for Zapier, n8n, Make |
| Browser | Push notifications for new alerts |
| Scheduled | Weekly uptime reports auto-sent |

### 📊 Reporting & Export

| Feature | Description |
|---------|-------------|
| Uptime reports | Server availability over 7/30/90 days |
| Performance | Per-outbound latency statistics |
| CSV export | Servers, outbounds, incidents |
| Uptime badge | Shields.io compatible public badge |
| API docs | Auto-generated OpenAPI 3.0 |

### 🔐 Security

| Feature | Description |
|---------|-------------|
| Passwords | PBKDF2-SHA256 (260K iterations) |
| Encryption | AES-256-CBC for stored credentials |
| Rate limiting | Per-endpoint (login: 10/15min, API: 120/min) |
| Sessions | HttpOnly cookies, 7-day expiry |
| RBAC | Owner + 10 managers with permissions |
| Audit | Full action logging |
| License | Ed25519 signed token verification |

### 🎨 Dashboard

| Feature | Description |
|---------|-------------|
| Dark Mode | Full dark theme with system detection |
| RTL | Persian interface with English support |
| PWA | Installable on mobile devices |
| Charts | CPU/RAM and ping history visualization |
| Pagination | Search, filter, and page through data |
| Branding | Custom logo, colors, product name |

---

## 🏗 Architecture

```
Veltrix/
├── outpanel/              26 Python modules (backend)
│   ├── app.py             HTTP server + router dispatch
│   ├── routes.py          77 API endpoint handlers
│   ├── worker.py          Background monitoring + automation
│   ├── sse.py             Real-time Server-Sent Events
│   ├── panels.py          Multi-panel adapter (x-ui/3x-ui/Marzban)
│   ├── telegram_bot.py    Two-way Telegram bot
│   ├── crypto.py          AES-256 credential encryption
│   ├── reports.py         Reporting + CSV export
│   └── ...                Auth, licensing, alerts, i18n, etc.
├── web/                   Frontend (vanilla JS SPA)
├── tests/                 Unit test suite (pytest)
├── .github/workflows/     CI/CD pipeline
├── scripts/               Auto-installer
├── docker-compose.yml     Production deployment
└── docs/                  Documentation
```

---

## ⚙️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12+ (stdlib only — zero dependencies) |
| Database | SQLite with WAL mode |
| Frontend | Vanilla JavaScript SPA |
| Styling | Custom CSS with Dark Mode |
| Container | Docker + Docker Compose |
| Deployment | systemd service on Linux |
| CI/CD | GitHub Actions |
| Testing | pytest |

---

## 🚀 Deployment

### One-Line Install (Linux)

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/iPmartNetwork/Veltrix/master/scripts/install-linux.sh)
```

The installer provides:
- 🔍 Auto OS detection (Ubuntu, Debian, CentOS, Fedora, Arch)
- 🐍 Auto Python 3.12 installation if missing
- 🔑 Auto-generated encryption key and API token
- 🛡 systemd service with security hardening
- 📋 Interactive menu (install, update, demo, uninstall)

### Docker

```bash
docker compose up -d
```

### Development

```bash
python -m outpanel.app --host 127.0.0.1 --port 8000
```

---

## 🤖 Telegram Bot

Configure in `.env`:
```env
OUTPANEL_TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
OUTPANEL_TELEGRAM_ALLOWED_CHATS=-1001234567890
```

Commands:
| Command | Description |
|---------|-------------|
| `/status` | Overview of all servers |
| `/servers` | List servers with status |
| `/server <id>` | Server detail + metrics |
| `/ping <id>` | Ping server outbounds |
| `/alerts` | Active alerts |
| `/incidents` | Open incidents |
| `/health` | Health scores |

---

## 📜 License

Veltrix is **proprietary commercial software**.

Use, installation, modification, distribution, resale, sublicensing, public hosting, or making this software available to third parties is not permitted without a valid commercial license issued by **iPmartNetwork**.

| Plan | Limit | Duration |
|------|-------|----------|
| Pro | 20 servers | 6mo / 1yr / Lifetime |
| Enterprise | 60 servers + 60 outbounds | 6mo / 1yr / Lifetime |

---

## 🤝 Support

For licensing, installation support, or commercial inquiries:

- **GitHub:** [iPmartNetwork](https://github.com/iPmartNetwork)
- **Issues:** [Report a bug](https://github.com/iPmartNetwork/Veltrix/issues)

---

<p align="center">
  <img src="img/Veltrix.png" alt="Veltrix" width="120" />
</p>

<p align="center">
  <sub>Built with precision by <strong>iPmartNetwork</strong></sub><br>
  <sub>© 2026 iPmartNetwork — All rights reserved.</sub>
</p>
