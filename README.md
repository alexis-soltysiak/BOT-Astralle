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

## Commande /lisnard

`/lisnard` fait reagir un pastiche de David Lisnard au dernier message du salon.
La commande lit les 25 derniers messages. Elle en extrait aussi le contenu des
liens (embeds Twitter/X, articles, videos), les pieces jointes, et le fil des
reponses Discord pour qu'un message comme "ca revient au meme ?" reste
comprehensible. Le modele peut chercher sur le web si le sujet le demande. La reponse est postee comme un message normal dans le salon.

La personnalite vit dans `discord/app/features/lisnard/persona.md` : c'est ce
fichier qu'il faut editer pour ajuster le ton, les positions ou la longueur des
reponses. Aucun redeploiement de code n'est necessaire au-dela d'un rebuild.

La commande est enregistree en **global**, pas sur `DISCORD_GUILD_ID` : elle
marche donc sur tous les serveurs ou le bot est invite, contrairement aux
commandes LoL qui dependent d'un serveur precis. Discord peut mettre jusqu'a
une heure a propager une commande globale nouvellement creee.

Le bot a besoin sur chaque salon de View Channel, Read Message History et Send
Messages. S'il lui en manque une, la commande repond en ephemere en disant
laquelle plutot que d'echouer en silence.

Prerequis important : la commande a besoin du **Message Content Intent**, active
dans le Discord Developer Portal (Applications > ton app > Bot > Privileged
Gateway Intents). Sans lui, `discord.py` refuse de se connecter au demarrage et
le bot entier ne tourne plus. Si tu ne peux pas l'activer, mets
`LISNARD_ENABLED=false` : le bot redemarre alors sans demander cet intent.

Variables associees :

- `LISNARD_ENABLED` : coupe la commande et l'intent privilegie
- `LISNARD_MODEL` : modele OpenAI utilise (defaut `gpt-5.6`)
- `LISNARD_HISTORY_LIMIT` : nombre de messages lus (defaut 25)
- `LISNARD_WEB_SEARCH_ENABLED` : autorise la recherche web
- `LISNARD_MAX_OUTPUT_TOKENS` : plafond qui couvre aussi les tokens de raisonnement
- `LISNARD_REASONING_EFFORT` : `minimal`, `low`, `medium` ou `high`

La cle utilisee est `LLM_API_KEY`, partagee avec l'analyse de match.

## Deploiement et securite

Voir [docs/deployment-security-checklist.md](docs/deployment-security-checklist.md) pour la checklist GitHub + VM, la configuration des URLs publiques et les recommandations de securisation backend/frontend/Discord/Postgres/Redis.
Pour l'initialisation de la VM OVH et un premier deploiement sur IP seule, voir aussi [docs/vm-init-ovh.md](docs/vm-init-ovh.md).
Pour les sauvegardes Postgres, voir [docs/postgres-backups.md](docs/postgres-backups.md).
Le frontend admin peut maintenant utiliser une session HTTP-only via `/auth/`, et le bot Discord utilise un token service distinct.
