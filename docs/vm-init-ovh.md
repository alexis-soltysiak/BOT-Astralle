# OVH VM Init Guide

Target VM:

- Hostname: `vps-b3698c91.vps.ovh.net`
- IPv4: `149.202.57.147`
- IPv6: `2001:41d0:305:2100::504f`
- User: `ubuntu`

## 1. First login

From your machine:

```powershell
ssh ubuntu@149.202.57.147
```

If you only have the generated password, connect once, then switch to SSH keys as soon as possible.

## 2. Immediate OS hardening

Run on the VM:

```bash
sudo apt update && sudo apt upgrade -y
sudo timedatectl set-timezone Europe/Paris
sudo adduser deploy
sudo usermod -aG sudo deploy
```

If you already have your SSH public key locally:

```bash
sudo mkdir -p /home/deploy/.ssh
sudo nano /home/deploy/.ssh/authorized_keys
sudo chown -R deploy:deploy /home/deploy/.ssh
sudo chmod 700 /home/deploy/.ssh
sudo chmod 600 /home/deploy/.ssh/authorized_keys
```

Then harden SSH:

```bash
sudo cp /etc/ssh/sshd_config /etc/ssh/sshd_config.bak
sudo nano /etc/ssh/sshd_config
```

Set or confirm:

```text
PermitRootLogin no
PasswordAuthentication no
PubkeyAuthentication yes
```

Reload SSH only after validating a second session works:

```bash
sudo systemctl reload ssh
```

## 3. Firewall and brute-force protection

```bash
sudo apt install -y ufw fail2ban apache2-utils ca-certificates curl gnupg
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
sudo systemctl enable --now fail2ban
```

## 4. Docker installation

```bash
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo $VERSION_CODENAME) stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker deploy
sudo systemctl enable --now docker
```

Reconnect after group changes:

```bash
exit
ssh deploy@149.202.57.147
docker version
docker compose version
```

## 5. Clone and prepare the app

```bash
mkdir -p ~/apps
cd ~/apps
git clone <your-github-repo-url> astralle
cd astralle
cp .env.compose.example .env.compose
```

Edit `.env.compose`:

```env
ENV=production
LOG_LEVEL=INFO

POSTGRES_DB=app
POSTGRES_USER=app
POSTGRES_PASSWORD=change-this-to-a-long-random-password

CORS_ALLOWED_ORIGINS=http://149.202.57.147
NEXT_PUBLIC_BACKEND_BASE_URL=http://149.202.57.147

RIOT_API_KEY=your-riot-key

DISCORD_TOKEN=your-discord-token
DISCORD_APPLICATION_ID=your-discord-application-id
DISCORD_GUILD_ID=your-discord-guild-id
DISCORD_CONSUMER_ID=discord-bot-prod
DISCORD_MATCHES_CHANNEL_ID=your-channel-id
DISCORD_LEADERBOARD_CHANNEL_ID=your-channel-id
DISCORD_LIVE_CHANNEL_ID=your-channel-id
DISCORD_FINISHED_CHANNEL_ID=your-channel-id
```

With the current IP-only setup:

- `NEXT_PUBLIC_BACKEND_BASE_URL` should stay `http://149.202.57.147`
- `CORS_ALLOWED_ORIGINS` should stay `http://149.202.57.147`

## 6. Start the containers in production mode

Use both compose files:

```bash
docker compose --env-file .env.compose -f docker-compose.prod.yml up -d --build
```

Verify:

```bash
docker compose ps
curl http://127.0.0.1:8000/healthz
curl http://127.0.0.1:3000
```

## 7. Put Nginx in front

Install Nginx:

```bash
sudo apt install -y nginx
sudo systemctl enable --now nginx
```

Create a basic-auth user:

```bash
sudo htpasswd -c /etc/nginx/.htpasswd-astralle admin
```

Install the IP-based config:

```bash
sudo cp infra/nginx/ip-single-host.conf.example /etc/nginx/sites-available/astralle
sudo ln -s /etc/nginx/sites-available/astralle /etc/nginx/sites-enabled/astralle
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
```

Result:

- `http://149.202.57.147/` -> frontend behind basic auth
- `http://149.202.57.147/api/...` -> backend behind basic auth
- `http://149.202.57.147/healthz` -> backend health endpoint without auth

## 8. When you later have domains

Example:

- `front.your-domain.tld`
- `api.your-domain.tld`

Then:

1. Update DNS to point both records to `149.202.57.147`
2. Update `.env.compose`
3. Rebuild the frontend with the new backend URL
4. Switch Nginx to `infra/nginx/domain-split.conf.example`
5. Request Let's Encrypt certificates

Values to update in `.env.compose`:

```env
CORS_ALLOWED_ORIGINS=https://front.your-domain.tld
NEXT_PUBLIC_BACKEND_BASE_URL=https://api.your-domain.tld
```

Then rebuild:

```bash
docker compose --env-file .env.compose -f docker-compose.prod.yml up -d --build
```

## 9. What should never be public

- Postgres on `5432`
- Redis on `6379`
- Discord bot ports
- Raw backend `8000`
- Raw frontend `3000`

The production compose file in this repo already keeps `5432` and `6379` off the public network and binds `8000` and `3000` to `127.0.0.1` only.
