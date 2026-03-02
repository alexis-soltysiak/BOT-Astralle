from __future__ import annotations

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, HTTPException

from app.core.config import get_settings
from app.core.database import close_db, get_sessionmaker, init_db, ping_db
from app.core.logging import configure_logging
from app.features.jobs.api import router as jobs_router
from app.features.jobs.repository import JobsRepository
from app.features.jobs.service import JobsService
from app.features.tracked_players.api import router as tracked_players_router
from app.infra.scheduler import AppScheduler
from app.features.leaderboards.api import router as leaderboards_router
from app.features.live_games.api import router as live_games_router
from app.features.matches.api import router as matches_router
from app.features.publications.api import router as publications_router
from fastapi.middleware.cors import CORSMiddleware
from app.features.discord_bindings.api import router as discord_bindings_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    await init_db()

    scheduler: AppScheduler | None = None
    if settings.scheduler_enabled:
        jobs_service = JobsService(JobsRepository())
        async with get_sessionmaker()() as session:
            await jobs_service.sync_definitions(session)
        scheduler = AppScheduler(get_sessionmaker(), jobs_service)
        scheduler.start()
        app.state.scheduler = scheduler

    yield

    if scheduler is not None:
        scheduler.stop()

    await close_db()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(title="lol-backend", version="0.4.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    log = structlog.get_logger("backend")
    log.info("app_created", env=settings.env)

    app.include_router(tracked_players_router, prefix="/api")
    app.include_router(jobs_router, prefix="/api")
    app.include_router(leaderboards_router, prefix="/api")
    app.include_router(live_games_router, prefix="/api")
    app.include_router(matches_router, prefix="/api")
    app.include_router(publications_router, prefix="/api")
    app.include_router(discord_bindings_router, prefix="/api")


    @app.get("/")
    async def root() -> dict[str, str]:
        return {"service": "backend", "status": "ok"}

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz")
    async def readyz() -> dict:
        ok = await ping_db()
        if not ok:
            raise HTTPException(status_code=503, detail="db_unreachable")
        return {"status": "ok", "checks": {"db": "ok"}}

    return app


app = create_app()


def main() -> None:
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.backend_host,
        port=settings.backend_port,
        reload=True,
    )


if __name__ == "__main__":
    main()
