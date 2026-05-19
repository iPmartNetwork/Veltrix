# Changelog

All notable changes to Veltrix are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.2.0] - 2026-05-19

### Added

- **Router-based API architecture** — Refactored monolithic `handle_api` into a clean router with separate route handlers (`router.py`, `routes.py`). Each endpoint is now a standalone function with declarative permission requirements.
- **API rate limiting** — Sliding-window rate limiter (`ratelimit.py`) with per-IP tracking, burst protection, and `X-RateLimit-*` response headers. Default: 120 requests/minute, 30 burst/5s.
- **Structured request logging** — JSON-formatted request/response logging (`logger.py`) with configurable output (stdout, file). Includes timing, client IP, user agent, and error tracking.
- **Ed25519 signed token verification** — Pure-Python Ed25519 implementation (`token_verify.py`) for verifying license tokens signed by the License Server. Supports public key loading from file or environment variable.
- **Health Score calculation** — Server health scoring (0-100) with grade assignment (A-F) based on connectivity (30%), CPU (15%), RAM (15%), and outbound availability (40%). Available via `GET /api/servers/{id}/health`.
- **Complete auth module** — Implemented all missing functions: `create_manager`, `update_manager`, `delete_manager`, `list_users`, `list_audit_logs`, session management, password hashing/verification, rate limiting for login attempts.
- **Complete monitor module** — Implemented all missing functions: `parse_server_metrics`, `upsert_inbounds`, `store_metrics_and_alerts`, `record_outbound_check`, `raise_alert`, `resolve_alerts`.
- **Docker Compose** — Production-ready `docker-compose.yml` with volume mounts, health checks, restart policy, and environment configuration.
- **CHANGELOG.md** — This file, tracking all project changes.
- **requirements.txt** — Dependency manifest (currently stdlib-only with optional enhancements listed).

### Changed

- `app.py` — Simplified to use the router for dispatch. Added rate limit headers, structured logging, and cleaner error handling.
- `monitor.py` — Added metrics cleanup (keeps last 1000 per server), outbound check cleanup (keeps last 500 per outbound).
- `auth.py` — Added IP-based rate limiting for login attempts (3x multiplier over username-based).

### Fixed

- Missing function implementations that caused `ImportError` on startup.
- Server password now excluded from API responses in all endpoints.

### Security

- Rate limiting prevents brute-force attacks on both login and general API endpoints.
- Ed25519 token verification prevents license forgery without the private key.
- Login lockout after 5 failed attempts per username or 15 per IP within 15 minutes.

---

## [0.1.0] - 2026-05-12

### Added

- Initial product baseline.
- Multi-server x-ui management with inbound synchronization.
- TCP ping monitoring for outbound connectivity.
- CPU, RAM, disk monitoring from x-ui status API.
- Alert system with CPU/RAM/ping thresholds.
- Incident lifecycle (open → acknowledged → recovered).
- Browser notifications, Telegram, and Webhook channels.
- Primary owner account with full access.
- Manager accounts (up to 10) with section-level permissions.
- PBKDF2-SHA256 password hashing with session management.
- Database backup, download, delete, and restore workflows.
- License activation client with IP binding.
- Persian RTL dashboard (single-page vanilla JS).
- Docker container support.
- Linux systemd deployment with install script.
- Commercial license enforcement (plan-based server limits).
