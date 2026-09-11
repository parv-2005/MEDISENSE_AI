"""MediSense AI - FastAPI application factory."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import create_client, init_indexes
from app.routers import auth, reports


def create_app(connect_db: bool = True) -> FastAPI:
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if connect_db:
            client = create_client()
            try:
                await client.admin.command("ping")
            except Exception as exc:  # pragma: no cover - needs a real server
                raise RuntimeError(
                    f"Cannot reach MongoDB at '{settings.mongodb_uri}'. Start a local mongod or set MONGODB_URI "
                    f"in backend/.env to an Atlas connection string. ({exc.__class__.__name__})"
                ) from exc
            app.state.mongo_client = client
            app.state.db = client[settings.mongodb_db]
            await init_indexes(app.state.db)
        settings.upload_dir.mkdir(parents=True, exist_ok=True)
        settings.chroma_dir.mkdir(parents=True, exist_ok=True)
        yield
        if connect_db:
            app.state.mongo_client.close()

    app = FastAPI(
        title="MediSense AI API",
        version="1.0.0",
        description="Medical report upload, OCR extraction, Gemini analysis and RAG follow-up questions.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings.frontend_origin.split(",") if o.strip()],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(auth.router)
    app.include_router(reports.router)

    @app.get("/api/health", tags=["meta"])
    async def health():
        return {"status": "ok", "model": settings.gemini_model}

    return app


app = create_app()
