# Deployment And Security Checklist

## 1. Before pushing to GitHub

- Ensure `.env`, `backend/.env`, `discord/.env`, and `frontend/.env.local` are not committed.
- Keep `.env.compose.example` committed, but never commit real production secrets.
- Verify `git status` is clean before pushing.
- If the repository is public, rotate any Riot or Discord secret that may have been exposed locally before.

## 2. Minimum VM prerequisites

- Ubuntu 24.04 LTS or Debian 12 on the VM.
- A non-root user with `sudo`.
- Docker Engine and Docker Compose plugin installed.
- Firewall enabled.
- SSH key authentication enabled and password login disabled.
- Automatic security updates enabled.

## 3. Network model to target

- Expose only `80` and `443` publicly.
- Do not expose `5432` for Postgres publicly.
- Do not expose `6379` for Redis publicly.
- Prefer not exposing `8000` publicly if Nginx can reverse proxy it locally.
- Prefer not exposing `3000` publicly if Nginx can reverse proxy it locally.

Recommended public layout:

- `front.your-domain.tld` -> Nginx -> frontend container
- `api.your-domain.tld` -> Nginx -> backend container
- Discord bot: no inbound public port required
- Postgres and Redis: internal Docker network only

## 4. When you have your frontend and backend IPs/domains

Set these values in `.env.compose`:

```env
ENV=production
LOG_LEVEL=INFO

POSTGRES_DB=app
POSTGRES_USER=app
POSTGRES_PASSWORD=<strong-random-password>

CORS_ALLOWED_ORIGINS=https://front.your-domain.tld
NEXT_PUBLIC_BACKEND_BASE_URL=https://api.your-domain.tld

RIOT_API_KEY=<riot-api-key>

DISCORD_TOKEN=<discord-token>
DISCORD_APPLICATION_ID=<discord-application-id>
DISCORD_GUILD_ID=<discord-guild-id>
DISCORD_CONSUMER_ID=discord-bot-prod
DISCORD_MATCHES_CHANNEL_ID=<channel-id>
DISCORD_LEADERBOARD_CHANNEL_ID=<channel-id>
DISCORD_LIVE_CHANNEL_ID=<channel-id>
DISCORD_FINISHED_CHANNEL_ID=<channel-id>
```

Rules:

- Use domains with HTTPS, not raw IPs, as soon as possible.
- `CORS_ALLOWED_ORIGINS` must contain only the frontend public origin.
- `NEXT_PUBLIC_BACKEND_BASE_URL` must point to the backend public URL.
- Never reuse local or weak passwords in production.

## 5. Backend hardening

Current repo risk:

- The admin API currently exposes mutation endpoints without authentication.

Before public exposure, add one of these:

- A reverse proxy basic auth in front of the admin UI and API.
- An app-level admin token for write endpoints.
- A proper identity provider later if the project grows.

Minimum backend controls:

- Restrict backend ingress to Nginx only when possible.
- Keep FastAPI behind HTTPS termination.
- Limit CORS to the exact frontend domain.
- Disable public docs if you do not need them in production.
- Add request logging and container restart policies.
- Add backups before trusting production data.

Recommended first-step protection for this project:

- Keep the backend private behind Nginx.
- Allow only Nginx to reach the backend container.
- Protect `/api` admin routes with at least a shared secret or basic auth.

## 6. Frontend hardening

- Serve the frontend only through HTTPS.
- Point `NEXT_PUBLIC_BACKEND_BASE_URL` to the backend public HTTPS URL.
- Do not place secrets in frontend environment variables.
- Treat everything prefixed with `NEXT_PUBLIC_` as public information.
- Add a strict Content Security Policy later if you keep the app public.

## 7. Discord bot hardening

- The Discord bot does not need inbound public ports.
- Keep it on the same private Docker network as the backend.
- Store only outbound secrets: `DISCORD_TOKEN`, `DISCORD_APPLICATION_ID`, channel IDs.
- If a token is ever exposed, rotate it immediately in the Discord developer portal.
- Restrict Discord bot permissions to the minimum required scopes and channels.

## 8. Postgres hardening

- Do not publish port `5432` on the host in production.
- Keep the data on a named volume.
- Use a strong unique password.
- Enable routine dumps or snapshot backups.
- Test restore once before trusting backups.
- Limit access to the backend container only.

Minimum backup strategy:

- Daily `pg_dump` retained for several days.
- One off-VM copy if the data matters.

## 9. Redis hardening

- Do not publish port `6379` on the host in production.
- Keep Redis on the internal Docker network only.
- If later exposed across hosts, require authentication and TLS.
- If used only as an internal cache/queue helper, keep it private and simple.

## 10. Reverse proxy and TLS

Recommended setup:

- Nginx on the VM.
- Two virtual hosts:
  - `front.your-domain.tld` -> `127.0.0.1:3000`
  - `api.your-domain.tld` -> `127.0.0.1:8000`
- TLS certificates with Let's Encrypt.

Nginx security baseline:

- Redirect HTTP to HTTPS.
- Set `X-Forwarded-*` headers.
- Limit request body size if needed.
- Optionally enable rate limiting on API routes.
- Optionally put basic auth in front of admin endpoints immediately.

## 11. VM operating system hardening

- Create a dedicated deploy user.
- Disable root SSH login.
- Disable password SSH login.
- Use fail2ban or equivalent.
- Keep the OS patched automatically.
- Monitor disk usage for Docker volumes and logs.

## 12. Deployment flow

1. Push the repository to GitHub.
2. Clone it onto the VM.
3. Create `.env.compose` from `.env.compose.example`.
4. Fill real production values.
5. Adjust Docker Compose or override it so Postgres and Redis are not publicly published.
6. Start the stack with `docker compose --env-file .env.compose -f docker-compose.prod.yml up -d --build`.
7. Put Nginx in front with HTTPS.
8. Verify:
   - frontend loads
   - backend `/healthz` works through the public domain
   - admin actions work only for authorized users
   - Discord bot connects and publishes

For your OVH VM bootstrap and the IP-only first deployment path, see [docs/vm-init-ovh.md](vm-init-ovh.md).

## 13. Recommended next changes in this repo

Priority 1:

- Remove public host port mapping for Postgres and Redis in production.
- Add authentication in front of backend write/admin endpoints.
- Add an example production Nginx config.

Priority 2:

- Split dev and prod compose files.
- Add a deployment script for VM bootstrap.
- Add backup scripts for Postgres.

Priority 3:

- Add observability: structured logs, uptime checks, basic metrics.
- Add a secret-management approach more robust than raw `.env` files.
