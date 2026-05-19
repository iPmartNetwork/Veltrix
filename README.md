<p align="center">
  <img src="web/assets/veltrix-brand-board.jpg" alt="Veltrix - Intelligent Network Control" width="420"/>
</p>

<h1 align="center">Veltrix</h1>

<p align="center">
  <strong>Intelligent Network Control</strong>
</p>

<p align="center">
  A professional dashboard for x-ui server management, V2Ray outbound monitoring, incident alerts, and commercial license control.
</p>

---

## Overview

**Veltrix** is a self-hosted web application for outbound sellers, network operators, and teams managing multiple x-ui/V2Ray servers. It brings server resource monitoring, outbound health checks, ping visibility, incidents, notifications, backups, access control, and commercial licensing into one operational dashboard.

Veltrix is designed as commercial software. The private License Server and license issuing infrastructure are intentionally not included in this repository.

## Key Features

- Multi-server x-ui management
- x-ui inbound synchronization, presented as V2Ray outbounds/routes
- CPU, RAM, disk, uptime, and Xray status monitoring where supported
- TCP ping checks for each outbound
- Status detection for `ok`, `high`, `timeout`, `error`, and `disabled`
- Server detail view with Health Score, resource chart, focused ping chart, and recent risks
- Incident lifecycle with `open`, `acknowledged`, and `recovered` states
- Browser notifications, Telegram, and Webhook channels
- Primary owner account with full access
- Up to 10 manager accounts with configurable permissions
- Account password change and failed-login rate limiting
- Database backup, download, delete, and restore workflows
- Linux systemd deployment support
- Dockerfile for containerized runtime
- Commercial license client integration with a private License Server

## Commercial Licensing Model

Veltrix is proprietary commercial software. Use, installation, modification, distribution, resale, sublicensing, public hosting, or making this software available to third parties is not permitted without a valid commercial license issued by iPmartNetwork.

Each license is bound to one authorized public server IP where Veltrix is installed.

| Plan | Limit | Recommended For |
| --- | --- | --- |
| Pro | Up to 20 servers | Small and medium outbound sellers |
| Enterprise | Up to 60 servers and 60 outbounds | High-traffic teams and operators |

License durations:

- 6 months
- 1 year
- Lifetime

## Project Structure

```text
Veltrix/
  outpanel/          Backend, API, auth, licensing client, monitoring, backup
  web/               Persian RTL dashboard and static assets
  docs/              Product, architecture, roadmap and licensing notes
  scripts/           Development and Linux installer scripts
  systemd/           Production systemd service
  apps/              Future app boundaries for API, web and worker
  packages/          Future shared package boundary
  Dockerfile         Container runtime definition
  .env.example       Production environment template
  README.md          Project documentation
  CHANGELOG.md       Release notes
```

## Requirements

- Python 3.12 or newer
- Linux for production systemd installation
- Docker for containerized execution, optional
- x-ui panel access for each managed server

Veltrix currently relies mostly on the Python standard library.

## Local Development

From the project root:

```bash
python -m outpanel.app --host 127.0.0.1 --port 8000
```

Dashboard:

```text
http://127.0.0.1:8000
```

On first run, Veltrix shows the primary owner setup screen.

## Docker Runtime

```bash
docker build -t veltrix:latest .

docker run --rm -p 8000:8000 \
  -v veltrix-data:/app/data \
  -v veltrix-backups:/app/backups \
  --env OUTPANEL_REQUIRE_LICENSE=0 \
  veltrix:latest
```

## Linux Installation

```bash
git clone https://github.com/iPmartNetwork/Veltrix.git
cd Veltrix
sudo bash scripts/install-linux.sh
```

The installer:

- Copies the project to `/opt/veltrix`
- Creates the `veltrix` system user
- Creates `/etc/veltrix.env`
- Enables and starts `veltrix.service`

Check service status:

```bash
systemctl status veltrix.service
```

## Important Environment Variables

| Variable | Description |
| --- | --- |
| `OUTPANEL_HOST` | Web server bind address |
| `OUTPANEL_PORT` | Web server port |
| `OUTPANEL_DB` | SQLite database path |
| `OUTPANEL_BACKUP_DIR` | Backup storage path |
| `OUTPANEL_MONITOR_INTERVAL` | Monitoring interval in seconds |
| `OUTPANEL_API_TOKEN` | API token for secure automation |
| `OUTPANEL_REQUIRE_LICENSE` | Enforce commercial licensing |
| `OUTPANEL_LICENSE_SERVER_URL` | Private License Server URL |
| `OUTPANEL_SERVER_PUBLIC_IP` | Public server IP for license binding |

## x-ui Connection

Each server requires:

- Server name
- Public IP or domain
- x-ui panel URL
- x-ui username and password
- CPU, RAM, and ping warning thresholds
- Connection timeout

Veltrix uses TCP connect checks for ping monitoring because ICMP ping often requires elevated system permissions.

## Security

- User passwords are stored with PBKDF2-SHA256.
- Sessions are stored in HttpOnly cookies.
- Changing a password removes other sessions for the same user.
- Failed login attempts are rate-limited.
- x-ui passwords are not returned in server API responses.
- The primary owner always has full access.
- Managers only receive the permissions assigned by the owner.

## Do Not Commit

The following files and directories are runtime/private data and must not be committed:

- `data/*.db`
- `data/*.db-*`
- `data/license-cache.json`
- `data/instance.id`
- `logs/`
- `backups/`
- `.env`
- Private License Server files

## Development Checks

```bash
python -m compileall -q outpanel
node --check web/assets/app.js
```

## Development Status

Veltrix `0.1.0` includes the core product baseline. Recommended next steps:

- Complete Docker Compose setup
- Improve the production installer and upgrade path
- Add database migrations
- Encrypt sensitive credentials at rest
- Add operational reporting
- Finalize private License Server integration

## License

Veltrix is proprietary commercial software.

Use, installation, modification, distribution, sublicensing, resale, public hosting, or making this software available to third parties is not permitted without a valid commercial license issued by iPmartNetwork.

See `LICENSE.md` or the commercial EULA for details.

## Support

For licensing, installation support, or commercial inquiries, contact the iPmartNetwork team.

