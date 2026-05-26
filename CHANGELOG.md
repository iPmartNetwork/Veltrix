# Changelog

All notable changes to **Veltrix** are documented in this file.  
Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [0.3.0] — 2026-05-27

### 🔌 Multi-Panel Support

- **x-ui, 3x-ui, Marzban** — Three panel types supported via unified adapter (`panels.py`). Panel type selectable per-server in the dashboard.
- **Marzban OAuth2** — Full authentication flow with token-based API access.
- **Panel auto-detection** — Factory pattern creates the correct client based on `panel_type` field.

### 🤖 Telegram Bot (Two-Way)

- **Interactive commands** — `/status`, `/servers`, `/server <id>`, `/ping <id>`, `/alerts`, `/incidents`, `/health`, `/help`
- **Long-polling** — Background thread polls Telegram for updates.
- **Access control** — Restrict bot access to specific chat IDs via `OUTPANEL_TELEGRAM_ALLOWED_CHATS`.
- **Rich formatting** — HTML-formatted responses with status icons.

### 🔐 License Validation

- **Periodic validation** — Worker validates license with remote server every 24 hours (configurable).
- **Grace period** — 7-day grace if License Server is unreachable.
- **Expiry warning** — Dashboard shows warning 14 days before expiration.
- **Days remaining** — Clear display of remaining license days.
- **Signed token verification** — Validates cached Ed25519 tokens locally.

### ⚡ Advanced Alerts

- **IP Rotation detection** — Alert when a server's public IP changes unexpectedly.
- **Traffic limit alerts** — Warning at 80% and alert at 100% of configured traffic limit per outbound.
- **Configurable limits** — Per-outbound `traffic_limit` field + global `OUTPANEL_TRAFFIC_LIMIT_GB`.

### 🔧 Bulk Operations

- `POST /api/bulk/ping` — Ping multiple servers at once.
- `POST /api/bulk/sync` — Sync multiple servers.
- `POST /api/bulk/toggle-servers` — Enable/disable multiple servers.
- `POST /api/bulk/toggle-outbounds` — Enable/disable multiple outbounds.
- `POST /api/bulk/delete-servers` — Delete multiple servers.

### 🏷 Server Tags & Groups

- **Tag management** — Assign up to 10 tags per server for categorization.
- **Filter by tag** — `GET /api/tags/{tag}/servers` returns servers with a specific tag.
- **Tag list** — `GET /api/tags` returns all unique tags.

### 📛 Public Uptime Badge

- **Shields.io compatible** — `GET /api/badge/uptime` returns JSON in shields.io endpoint format.
- **Per-server badges** — `GET /api/badge/uptime/{server_id}` for individual server badges.
- **Color-coded** — Green (99%+), yellow-green (95%+), yellow (90%+), red (<80%).

### 📖 API Documentation

- **Auto-generated OpenAPI 3.0** — `GET /api/docs` returns full Swagger-compatible documentation.
- **65+ documented paths** — All endpoints with methods, parameters, permissions, and tags.
- **Security schemes** — Bearer token and cookie auth documented.

### 🧪 Testing & CI

- **Unit test suite** — 7 test modules covering auth, crypto, rate limiting, router, ping, i18n, and panels.
- **GitHub Actions CI** — Automated testing on Python 3.12/3.13, Docker build verification, syntax checks.
- **pytest configuration** — `pytest.ini` with verbose output.

### 🛡 Security Improvements

- **Per-endpoint rate limiting** — Login/setup endpoints: 10 req/15min. General API: 120 req/min.
- **Log rotation** — `RotatingFileHandler` with configurable max size (50MB) and backup count (5).

### 📊 Database

- **New migration** — `panel_type`, `last_detected_ip` on servers; `traffic_limit` on outbounds.

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
