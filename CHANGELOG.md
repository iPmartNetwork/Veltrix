# Changelog

All notable changes to **Veltrix** are documented in this file.  
Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [0.2.0] — 2026-05-19

### 🏗 Architecture

- **Router-based API** — Complete refactor from monolithic handler to a clean router with 60+ declarative endpoints (`router.py`, `routes.py`). Each handler is a standalone function with permission annotations.
- **Separated Worker** — Background monitoring extracted to `worker.py` with enhanced capabilities (auto-disable, scheduled reports, SSE events).
- **Module structure** — Backend expanded from 9 to 22 focused modules.

### 🔒 Security

- **AES-256 credential encryption** — x-ui passwords and API tokens encrypted at rest with AES-256-CBC + HMAC-SHA256 (`crypto.py`). Activated via `OUTPANEL_ENCRYPTION_KEY`.
- **API rate limiting** — Sliding-window limiter at 120 req/min per IP with burst protection (30/5s). Returns `X-RateLimit-*` headers (`ratelimit.py`).
- **Login lockout** — 5 failed attempts per username or 15 per IP within 15 minutes triggers lockout.
- **Ed25519 token verification** — Pure-Python Ed25519 implementation for verifying signed license tokens from the License Server (`token_verify.py`).

### 📡 Real-time

- **Server-Sent Events (SSE)** — Push real-time updates to connected dashboards via `GET /api/events` (`sse.py`). Events: `server.status`, `outbound.ping`, `alert.new`, `incident.update`, `monitor.cycle`.
- **Auto-reconnect** — Frontend reconnects SSE within 5 seconds on disconnect.
- **Heartbeat** — 25-second keepalive to prevent proxy timeouts.

### 🤖 Automation

- **Auto-disable outbounds** — Outbounds with N consecutive failures (default: 5) are automatically disabled with an incident record. Configurable via `OUTPANEL_AUTO_DISABLE_THRESHOLD`.
- **Scheduled weekly reports** — Automatic uptime report generated and sent to all notification channels every week (configurable day/hour).
- **Webhook events** — All key events dispatched to webhook channels for external integrations (Zapier, n8n, Make). Event types: `server.*`, `outbound.*`, `incident.*`, `backup.*`, `license.*`.

### 📊 Reporting

- **Uptime reports** — Server availability, latency stats, incident counts over configurable periods (`reports.py`).
- **Outbound performance reports** — Per-outbound availability, min/max/avg latency.
- **CSV export** — Download servers, outbounds, or incidents as CSV files with BOM for Excel compatibility.
- **Report storage** — Generated reports saved to database for historical access.

### 🎨 Dashboard

- **Dark Mode** — Complete dark theme with `[data-theme="dark"]` CSS. Toggle button in topbar. Respects `prefers-color-scheme` system preference.
- **Table pagination** — 15 items per page with page navigation, total count display.
- **Search & filter** — Real-time search and status dropdown filter on server and outbound tables.
- **Export buttons** — CSV download buttons on servers, outbounds, and incidents panels.
- **Report modal** — In-dashboard report viewer with summary cards and data tables.
- **Chart tooltips** — Hover tooltips on chart data points.
- **PWA support** — `manifest.json` + Service Worker for offline caching and mobile install.
- **Improved CSS** — New variables (`--radius`, `--transition`, `--shadow-hover`), dialog animations, auth screen animation, better scrollbars, focus-visible states.

### 🌐 Internationalization & Branding

- **Multi-language** — Persian (fa) and English (en) with runtime switching (`i18n.py`). API: `GET /api/i18n`.
- **Custom branding** — Product name, logo, colors, tagline configurable via env vars or API (`branding.py`). API: `GET/PUT /api/branding`.
- **Demo mode** — Realistic fake data generator for demonstrations (`demo.py`). Activated via `OUTPANEL_DEMO_MODE=1`.

### 🔧 Infrastructure

- **Database migrations** — Versioned schema migrations with automatic execution on startup (`migrations.py`). 6 initial migrations included.
- **Structured logging** — JSON request/response logging with timing, client IP, user agent (`logger.py`). Configurable output (stdout/file).
- **Docker Compose** — Production-ready `docker-compose.yml` with volumes, healthcheck, resource limits.
- **Improved installer** — Interactive menu, auto Python install, OS detection, security hardening, one-line install support.
- **Health Score** — Server health calculation (0–100) with weighted scoring: connectivity 30%, CPU 15%, RAM 15%, outbound availability 40%.

### 🔌 Server Management

- **API Token auth** — Servers can authenticate with x-ui panels via API Token (Bearer) instead of username/password. More secure, no admin password storage needed.
- **Auth mode selector** — Dashboard dialog shows dropdown to choose between credentials and API token.

### 📝 Documentation

- **INSTALL_GUIDE.md** — Complete installation, configuration, and troubleshooting guide.
- **CHANGELOG.md** — This file.
- **Professional README** — Separate English and Persian README files with badges, architecture diagram, and API reference.

---

## [0.1.0] — 2026-05-12

### Initial Release

- Multi-server x-ui management with inbound synchronization
- TCP ping monitoring for outbound connectivity
- CPU, RAM, disk monitoring from x-ui status API
- Alert system with CPU/RAM/ping thresholds
- Incident lifecycle (open → acknowledged → recovered)
- Browser notifications, Telegram, and Webhook channels
- Primary owner account with full access
- Manager accounts (up to 10) with section-level permissions
- PBKDF2-SHA256 password hashing with session management
- Database backup, download, delete, and restore workflows
- License activation client with IP binding
- Persian RTL dashboard (single-page vanilla JS)
- Docker container support
- Linux systemd deployment with install script
- Commercial license enforcement (plan-based server limits)

---

<p align="center">
  <sub>Veltrix — Intelligent Network Control by iPmartNetwork</sub>
</p>
