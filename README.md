# LoL Ecosystem Monorepo

Monorepo pour un ecosysteme League of Legends :

- `backend/` : coeur metier, polling Riot, persistance, jobs, outbox d'evenements
- `discord/` : bot Discord / consumer publisher
- `frontend/` : admin / monitoring
- `infra/` : Docker, env, orchestration
- `media/` : assets Riot

## Demarrage

Ouvre 3 terminaux PowerShell a la racine du repo.

### Terminal 1 - Backend API

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
pip install -e ".[dev]"
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Le backend tourne sur `http://localhost:8000`.

### Terminal 2 - Chatbot / bot Discord

```powershell
cd discord
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
pip install -e ".[dev]"
python -m app.main
```

Assure-toi que le `.env` du bot Discord est configure avant de le lancer.

### Terminal 3 - Frontend

```powershell
cd frontend
npm install
npm run dev
```

Le frontend tourne sur `http://localhost:3000`.

## Deploiement Docker

Copie `/.env.compose.example` vers `/.env.compose`, remplis les secrets, puis adapte au minimum :

- `POSTGRES_PASSWORD`
- `RIOT_API_KEY`
- `DISCORD_TOKEN`
- `DISCORD_APPLICATION_ID`
- `DISCORD_GUILD_ID`
- `DISCORD_*_CHANNEL_ID`
- `NEXT_PUBLIC_BACKEND_BASE_URL` avec l'URL publique du backend
- `CORS_ALLOWED_ORIGINS` avec l'URL publique du frontend

Lance ensuite la stack complete :

```powershell
Copy-Item .env.compose.example .env.compose
docker compose --env-file .env.compose up -d --build
```

Services exposes :

- frontend : `http://localhost:3000`
- backend : `http://localhost:8000`
- postgres : `localhost:5432`
- redis : `localhost:6379`

## Deploiement et securite

Voir [docs/deployment-security-checklist.md](docs/deployment-security-checklist.md) pour la checklist GitHub + VM, la configuration des URLs publiques et les recommandations de securisation backend/frontend/Discord/Postgres/Redis.
Pour l'initialisation de la VM OVH et un premier deploiement sur IP seule, voir aussi [docs/vm-init-ovh.md](docs/vm-init-ovh.md).
Pour les sauvegardes Postgres, voir [docs/postgres-backups.md](docs/postgres-backups.md).
