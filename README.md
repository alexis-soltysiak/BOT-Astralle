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

## Commandes de personnages

`/help` affiche un sommaire de toutes les commandes, construit depuis le
registre des personnages pour rester a jour tout seul.

Huit personnalites disposent chacune de leur commande : `/lisnard`,
`/melenchon`, `/tondelier`, `/lepen`, `/knafo`, `/panot`, `/trump` et
`/poutine`. Chacune fait reagir un pastiche de la personne au dernier message
du salon.

Face a une provocation, un personnage ne refuse jamais de facon visible : il
pivote vers une question voisine qu'il avait envie de traiter. Un refus
explicite se repere immediatement et casse l'illusion. Les figures les plus
exposees portent en plus une section de limites explicites dans leur fiche, et
des tests verifient qu'elle est bien la.

`/sphere <nombre>` fait intervenir plusieurs d'entre elles a la suite. Le
plateau est tire au sort a chaque appel, les prises de parole sont espacees de
5 secondes, et chaque intervenant voit ce que les precedents ont dit : il ne
repete pas, il repond ou change d'angle. Pour limiter la consommation, ce mode
lit moins de messages (12 au lieu de 40) et coupe la recherche web.

### Recherche web conditionnelle

La seule definition de l'outil `web_search` coute 4436 tokens d'entree, soit
plus que la fiche d'un personnage : elle multiplie par environ quatre le cout
d'un appel, meme quand aucune recherche n'a lieu (2,93 centimes contre 0,74).

L'outil n'est donc attache que si les deux derniers messages du salon
contiennent une URL nue, un marqueur de fraicheur (actualite, sondage, date,
demission, proces, une annee) ou une demande de verification ("c'est vrai",
"il parait", "combien"). Une URL dont Discord a deja fourni l'embed ne
declenche rien : le contenu est deja dans le contexte.

Le tri se fait dans `needs_web_search`, dans `transcript.py`.

La commande lit les 25 derniers messages. Elle en extrait aussi le contenu des
liens (embeds Twitter/X, articles, videos), les pieces jointes, et le fil des
reponses Discord pour qu'un message comme "ca revient au meme ?" reste
comprehensible. Le modele peut chercher sur le web si le sujet le demande. Les
personnages se voient entre eux : si l'un a deja parle dans le salon, l'autre
peut lui repondre directement.

Chaque reponse est postee via un **webhook Discord** portant le nom et l'avatar
du personnage, ce qui les fait apparaitre comme deux interlocuteurs distincts.
Cela demande la permission **Manage Webhooks** sur le salon. Sans elle, la
commande fonctionne quand meme mais retombe sur un message prefixe du nom, et
le dit en ephemere a celui qui a lance la commande.

### Ajouter un personnage

Trois choses, aucune ligne de logique a ecrire :

1. `discord/app/features/personas/profiles/<nom>.md` : la fiche de personnalite
2. `discord/app/features/personas/avatars/<nom>.<ext>` : la photo
3. une entree dans `PERSONAS`, dans `discord/app/features/personas/registry.py`

La slash command, le webhook et les tests de coherence suivent automatiquement.
Les fiches existantes servent de gabarit : chacune se termine par les memes
garde-fous de ton (longueur, pas de markdown, autoderision, pas d'insulte), et
un test verifie que tout nouveau personnage les porte aussi.

### Reglages

La commande est scopee sur `DISCORD_GUILD_ID` quand il est renseigne, ce qui la
rend disponible instantanement apres un redemarrage. Sans cette variable elle
est enregistree en global, et Discord peut alors mettre jusqu'a une heure a la
propager.

Le bot a besoin sur chaque salon de View Channel, Read Message History et Send
Messages, plus Manage Webhooks pour l'avatar.

Prerequis important : les commandes ont besoin du **Message Content Intent**,
active dans le Discord Developer Portal (Applications > ton app > Bot >
Privileged Gateway Intents). Sans lui, `discord.py` refuse de se connecter au
demarrage et le bot entier ne tourne plus. Si tu ne peux pas l'activer, mets
`PERSONA_ENABLED=false` : le bot redemarre alors sans demander cet intent.

Variables associees :

- `PERSONA_ENABLED` : coupe les commandes et l'intent privilegie
- `PERSONA_MODEL` : modele OpenAI utilise (defaut `gpt-5.6-terra`)
- `PERSONA_HISTORY_LIMIT` : nombre de messages lus (defaut 40)
- `PERSONA_WEB_SEARCH_ENABLED` : autorise la recherche web
- `PERSONA_MAX_OUTPUT_TOKENS` : plafond qui couvre aussi les tokens de raisonnement
- `PERSONA_REASONING_EFFORT` : `minimal`, `low`, `medium` ou `high`

Les anciens noms `LISNARD_*` restent acceptes pour ne pas casser les `.env`
deja deployes.

La cle utilisee est `LLM_API_KEY`, partagee avec l'analyse de match.

## Deploiement et securite

Voir [docs/deployment-security-checklist.md](docs/deployment-security-checklist.md) pour la checklist GitHub + VM, la configuration des URLs publiques et les recommandations de securisation backend/frontend/Discord/Postgres/Redis.
Pour l'initialisation de la VM OVH et un premier deploiement sur IP seule, voir aussi [docs/vm-init-ovh.md](docs/vm-init-ovh.md).
Pour les sauvegardes Postgres, voir [docs/postgres-backups.md](docs/postgres-backups.md).
Le frontend admin peut maintenant utiliser une session HTTP-only via `/auth/`, et le bot Discord utilise un token service distinct.
