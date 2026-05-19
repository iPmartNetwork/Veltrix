# Veltrix Product Spec

## Brand

- Name: Veltrix
- Tagline: Intelligent Network Control
- Visual direction: dark operational dashboard, teal/cyan accent, restrained commercial UI
- Primary audience: people and teams who sell V2Ray/x-ui outbound access
- Sales model: license purchase through support
- Deployment model: self-hosted customer installation with SaaS license validation
- License scope: one license is valid for one server public IP

## Core Product

Veltrix manages multiple x-ui servers from one dashboard. It syncs V2Ray routes, monitors server resources, checks route connectivity, and raises alerts when latency or availability is unhealthy.

## License Plans

| Plan | Limit | Audience |
| --- | --- | --- |
| Pro | 20 servers | Small and mid-size outbound sellers |
| Enterprise | 60 servers and 60 outbounds by the current definition | Larger sellers and teams |

License durations:

- 6 months
- 1 year
- Lifetime

Every license is bound to a single public server IP. If the customer moves Veltrix to a new server, support must reissue or rebind the license.

## Required Product Modules

- Server inventory and x-ui credentials
- x-ui sync for inbounds/routes
- TCP ping/latency monitoring
- CPU/RAM/Disk monitoring from x-ui status API
- Alert center
- Browser notification, Telegram, and Webhook notifications
- License activation screen
- Instance ID generation
- License server integration
- Primary admin account with full access
- Up to 10 manager accounts with section-level permissions
- Audit log for server/license/admin actions
- Dashboard backup and restore with pre-restore safety backup

## Future SaaS Components

Veltrix needs two products that work together:

- Customer installation: installed on the buyer's Linux server.
- Veltrix License Server: hosted by us, validates license keys and returns signed license tokens.

The license server should manage customers, plans, durations, renewals, revocation, support notes, and activation limits.
