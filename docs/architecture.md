# Architecture

## Principes

- Backend = source de vérité (polling Riot, persistance, jobs, outbox)
- Discord = publisher/consumer léger (aucun polling Riot)
- Frontend = admin/monitoring
- Infra = exécution locale/prod (Docker)
- Media = assets Riot statiques

## Conventions backend

- Organisation feature-first
- Les routes FastAPI d’une feature sont dans `backend/app/features/<feature>/api.py`
- Pas de dossiers transverses `api/`, `services/`, `repositories/`, `schemas/`
