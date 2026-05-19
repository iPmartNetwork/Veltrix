# Veltrix Installation Guide

## Quick Start

### Linux (Recommended)

```bash
git clone https://github.com/iPmartNetwork/Veltrix.git
cd Veltrix
sudo bash scripts/install-linux.sh
```

The installer provides an interactive menu:
1. **Fresh install** — Full installation with systemd service
2. **Update** — Update existing installation preserving data
3. **Demo mode** — Install with sample data for demonstration
4. **Uninstall** — Remove service (data preserved)

### Docker

```bash
docker compose up -d
```

Or manually:

```bash
docker build -t veltrix:latest .
docker run -d --name veltrix \
  -p 8000:8000 \
  -v veltrix-data:/app/data \
  -v veltrix-backups:/app/backups \
  veltrix:latest
```

### Development

```bash
python -m outpanel.app --host 127.0.0.1 --port 8000
```

---

## First Setup

1. Open `http://YOUR_SERVER_IP:8000` in your browser
2. Create the primary admin account
3. Add your first x-ui server
4. Run synchronization to import outbounds

---

## Configuration

All configuration is done via environment variables. See `.env.example` for the full list.

### Key Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OUTPANEL_PORT` | HTTP port | 8000 |
| `OUTPANEL_DB` | SQLite database path | data/veltrix.db |
| `OUTPANEL_MONITOR_INTERVAL` | Monitoring interval (seconds) | 30 |
| `OUTPANEL_API_TOKEN` | API authentication token | (empty) |
| `OUTPANEL_ENCRYPTION_KEY` | AES key for credential encryption | (empty) |
| `OUTPANEL_LANGUAGE` | UI language: fa or en | fa |
| `OUTPANEL_AUTO_DISABLE_THRESHOLD` | Auto-disable after N failures | 5 |
| `OUTPANEL_REQUIRE_LICENSE` | Enforce license validation | 0 |

### Branding

| Variable | Description |
|----------|-------------|
| `OUTPANEL_BRAND_NAME` | Custom product name |
| `OUTPANEL_BRAND_TAGLINE` | Custom tagline |
| `OUTPANEL_BRAND_LOGO` | Custom logo URL |
| `OUTPANEL_BRAND_COLOR` | Primary brand color (hex) |
| `OUTPANEL_SUPPORT_URL` | Support page URL |
| `OUTPANEL_SUPPORT_EMAIL` | Support email |

---

## Adding Servers

### Method 1: Username & Password

Enter the x-ui panel URL, username, and password. Veltrix will authenticate using the standard login flow.

### Method 2: API Token

If your x-ui panel supports API tokens:
1. Go to x-ui panel settings
2. Generate an API access token
3. In Veltrix, select "API Token" as the authentication method
4. Paste the token

API Token is more secure as it doesn't require storing the admin password.

---

## Monitoring

Veltrix monitors your servers every 30 seconds (configurable):

- **TCP Ping** — Checks connectivity to each outbound
- **Resource Metrics** — CPU, RAM, disk from x-ui status API
- **Alerts** — Triggered when thresholds are exceeded
- **Incidents** — Created for persistent issues
- **Auto-disable** — Outbounds with repeated failures are automatically disabled

---

## Notifications

Supported channels:
- **Telegram** — Bot token + Chat ID
- **Webhook** — Any URL (compatible with Zapier, n8n, Make)

Events that trigger notifications:
- New incidents (critical/warning)
- Incident recovery
- Weekly scheduled reports

---

## Backup & Restore

- Backups are ZIP files containing the SQLite database + metadata
- Before every restore, a safety backup is automatically created
- Backups can be downloaded, restored, or deleted from the dashboard

---

## Security

- Passwords: PBKDF2-SHA256 (260,000 iterations)
- Sessions: HttpOnly cookies, 7-day expiry
- Rate limiting: 5 failed logins → 15-minute lockout
- Credentials: AES-256 encryption at rest (when key configured)
- Permissions: Role-based (owner + managers with section-level access)

---

## Updating

### Linux

```bash
cd /path/to/Veltrix
git pull
sudo bash scripts/install-linux.sh --update
```

### Docker

```bash
docker compose pull
docker compose up -d
```

Database migrations run automatically on startup.

---

## Troubleshooting

### Service won't start

```bash
journalctl -u veltrix -n 50
```

### Database locked

```bash
systemctl restart veltrix
```

### Reset admin password

```bash
cd /opt/veltrix
python3 -c "
from outpanel.db import connect, init_db
from outpanel.auth import hash_password
init_db()
with connect() as conn:
    conn.execute('UPDATE users SET password_hash = ? WHERE role = ?', (hash_password('newpassword'), 'owner'))
print('Password reset to: newpassword')
"
systemctl restart veltrix
```
