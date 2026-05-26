<p align="center">
  <img src="web/assets/veltrix-brand-board.jpg" alt="Veltrix — Intelligent Network Control" width="480"/>
</p>

<h1 align="center">Veltrix</h1>

<p align="center">
  <strong>Intelligent Network Control</strong><br>
  Professional dashboard for x-ui server management, V2Ray outbound monitoring, incident response, and commercial license control.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/version-0.3.0-00bfa6?style=flat-square" alt="Version"/>
  <img src="https://img.shields.io/badge/python-3.12+-3776ab?style=flat-square" alt="Python"/>
  <img src="https://img.shields.io/badge/license-Commercial-red?style=flat-square" alt="License"/>
  <img src="https://img.shields.io/badge/platform-Linux%20%7C%20Docker-333?style=flat-square" alt="Platform"/>
</p>

<p align="center">
  <a href="README_FA.md">🇮🇷 مستندات فارسی</a> •
  <a href="docs/INSTALL_GUIDE.md">Installation Guide</a> •
  <a href="CHANGELOG.md">Changelog</a> •
  <a href="docs/ARCHITECTURE.md">Architecture</a>
</p>

---

## Overview

**Veltrix** is a self-hosted web application for outbound sellers, network operators, and teams managing multiple x-ui/V2Ray servers. It consolidates server resource monitoring, outbound health checks, ping visibility, incident management, notifications, backups, access control, and commercial licensing into a single operational dashboard.

Veltrix is designed as **commercial software**. The private License Server and license issuing infrastructure are intentionally not included in this repository.

---

## Key Features

### Server Management
- Multi-server x-ui panel management with credential or API token authentication
- Automatic inbound synchronization (presented as V2Ray outbounds/routes)
- CPU, RAM, disk, uptime, and Xray status monitoring
- Server Health Score (0–100) with grade assignment (A–F)

### Monitoring & Alerts
- TCP ping checks for each outbound with configurable thresholds
- Status detection: `ok`, `high`, `timeout`, `error`, `disabled`
- Automatic outbound disable after repeated failures
- Real-time updates via Server-Sent Events (SSE)
- Background monitoring worker with configurable interval

### Incident Management
- Incident lifecycle: `open` → `acknowledged` → `recovered`
- Automatic incident creation from persistent failures
- Browser notifications, Telegram bot, and Webhook channels
- Webhook events for external integrations (Zapier, n8n, Make)

### Reporting & Export
- Uptime and availability reports (7/30/90 day periods)
- Outbound performance reports with latency statistics
- CSV export for servers, outbounds, and incidents
- Scheduled weekly reports sent to notification channels

### Security & Access Control
- Primary owner account with full access
- Up to 10 manager accounts with section-level permissions
- PBKDF2-SHA256 password hashing (260,000 iterations)
- AES-256 encryption for stored credentials
- API rate limiting (120 req/min per IP + burst protection)
- Login rate limiting with IP-based lockout
- HttpOnly session cookies with 7-day expiry
- Audit logging for all sensitive actions

### Dashboard
- Professional Persian RTL interface with Dark Mode
- Real-time status updates without page reload
- Interactive charts for CPU/RAM and ping history
- Table pagination, search, and status filters
- PWA support (installable on mobile devices)
- Custom branding (logo, colors, product name)
- Multi-language support (Persian + English)

### Commercial Licensing
- License activation with remote License Server
- IP binding (one license per server public IP)
- Plan-based server limits (Pro: 20, Enterprise: 60)
- Ed25519 signed token verification
- Offline grace period with cached tokens

---

## Architecture

```
Veltrix/
├── outpanel/              Python backend (22 modules)
│   ├── app.py             HTTP server with router-based dispatch
│   ├── router.py          URL routing with path params & permissions
│   ├── routes.py          60+ API endpoint handlers
│   ├── auth.py            Authentication, RBAC, sessions, audit
│   ├── monitor.py         Server sync, ping, health score
│   ├── worker.py          Enhanced background worker
│   ├── sse.py             Server-Sent Events broker
│   ├── webhooks.py        Webhook event dispatcher
│   ├── reports.py         Operational reporting & CSV export
│   ├── crypto.py          AES-256 credential encryption
│   ├── ratelimit.py       Sliding-window rate limiter
│   ├── logger.py          Structured JSON request logging
│   ├── migrations.py      Database migration system
│   ├── i18n.py            Internationalization (fa/en)
│   ├── branding.py        Custom branding support
│   ├── licensing.py       License client & activation
│   ├── token_verify.py    Ed25519 signature verification
│   ├── notifier.py        Telegram & Webhook notifications
│   ├── backup.py          Database backup & restore
│   ├── demo.py            Demo data generator
│   ├── xui.py             x-ui panel API client
│   ├── ping.py            TCP ping implementation
│   └── db.py              SQLite connection & schema
├── web/                   Frontend dashboard
│   ├── index.html         Single-page application
│   ├── assets/            CSS, JS, images
│   ├── manifest.json      PWA manifest
│   └── sw.js              Service Worker
├── docs/                  Documentation
├── scripts/               Installation scripts
├── systemd/               Service unit file
├── Dockerfile             Container build
├── docker-compose.yml     Production compose
└── CHANGELOG.md           Release history
```

---

## Requirements

- Python 3.12 or newer
- Linux for production (systemd deployment)
- Docker (optional, for containerized runtime)
- x-ui panel access for each managed server

Veltrix runs entirely on the Python standard library — no external packages required.

---

## Quick Start

### One-Line Install (Linux)

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/iPmartNetwork/Veltrix/main/scripts/install-linux.sh)
```

### Linux Production (Manual)

```bash
git clone https://github.com/iPmartNetwork/Veltrix.git
cd Veltrix
sudo bash scripts/install-linux.sh
```

The installer provides:
- Interactive menu with 5 options (install, update, demo, status, uninstall)
- Automatic Python 3.12 installation if not present
- OS detection (Ubuntu, Debian, CentOS, Fedora, AlmaLinux, Arch)
- Auto-generated encryption key and API token
- systemd service with security hardening
- Non-interactive mode: `--install`, `--update`, `--demo`, `--uninstall`

### Local Development

```bash
python -m outpanel.app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000` and create the admin account.

### Docker

```bash
docker compose up -d
```

---

## Configuration

All configuration is via environment variables. See [`.env.example`](.env.example) for the complete reference.

| Variable | Description | Default |
|----------|-------------|---------|
| `OUTPANEL_PORT` | HTTP server port | 8000 |
| `OUTPANEL_DB` | SQLite database path | data/veltrix.db |
| `OUTPANEL_MONITOR_INTERVAL` | Monitoring interval (seconds) | 30 |
| `OUTPANEL_API_TOKEN` | API authentication token | — |
| `OUTPANEL_ENCRYPTION_KEY` | AES key for credential encryption | — |
| `OUTPANEL_LANGUAGE` | Interface language (fa/en) | fa |
| `OUTPANEL_AUTO_DISABLE_THRESHOLD` | Auto-disable after N failures | 5 |
| `OUTPANEL_REQUIRE_LICENSE` | Enforce license validation | 0 |

---

## API

Veltrix exposes a RESTful JSON API with 60+ endpoints:

| Category | Endpoints |
|----------|-----------|
| Auth | `/api/auth/status`, `/api/auth/login`, `/api/auth/setup`, `/api/auth/logout`, `/api/auth/password` |
| Servers | `/api/servers`, `/api/servers/{id}`, `/api/servers/{id}/sync`, `/api/servers/{id}/health` |
| Outbounds | `/api/outbounds`, `/api/outbounds/{id}/ping`, `/api/outbounds/{id}/checks` |
| Alerts | `/api/alerts`, `/api/alerts/{id}/dismiss` |
| Incidents | `/api/incidents`, `/api/incidents/{id}/ack`, `/api/incidents/{id}/recover` |
| Notifications | `/api/notification-channels`, `/api/notification-channels/{id}/test` |
| Reports | `/api/reports/uptime`, `/api/reports/outbounds`, `/api/export/*` |
| Real-time | `/api/events` (SSE stream) |
| Settings | `/api/settings`, `/api/branding`, `/api/i18n` |

---

## Licensing Model

Veltrix is proprietary commercial software. Use, installation, modification, distribution, resale, sublicensing, public hosting, or making this software available to third parties is not permitted without a valid commercial license issued by iPmartNetwork.

| Plan | Limit | Audience |
|------|-------|----------|
| Pro | Up to 20 servers | Small and medium outbound sellers |
| Enterprise | Up to 60 servers, 60 outbounds | High-traffic teams and operators |

License durations: 6 months, 1 year, Lifetime.

---

## Security

- Passwords stored with PBKDF2-SHA256 (260,000 iterations)
- x-ui credentials encrypted with AES-256-CBC + HMAC-SHA256
- Sessions in HttpOnly cookies with SameSite protection
- Failed login rate limiting (5 attempts → 15-minute lockout)
- API rate limiting (120 requests/minute per IP)
- x-ui passwords never returned in API responses
- Ed25519 signed license tokens (unforgeable without private key)

---

## Development

```bash
# Compile check
python -m compileall -q outpanel

# Run locally
python -m outpanel.app --host 127.0.0.1 --port 8000

# With demo data
OUTPANEL_DEMO_MODE=1 python -m outpanel.app
```

---

## Support

For licensing, installation support, or commercial inquiries, contact the iPmartNetwork team.

---

<p align="center">
  <sub>Built with precision by iPmartNetwork</sub>
</p>
