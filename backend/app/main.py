"""FastAPI application entry point.

Scaffolds health checks, CORS middleware, model lifespan preloading,
and mounts API routers for JD, resumes, and matching.
"""

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config import get_settings
from app.db import engine, init_db
from app.routers import jd, match, resumes
from app.services.embeddings import get_embedding_service
from app.services.skills import get_skills_service

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle hook for startup and shutdown procedures."""
    # 1. Initialize database tables
    init_db()

    # 2. Warm up / preload NLP models once at startup (SentenceTransformer + spaCy)
    emb_service = get_embedding_service()
    skills_service = get_skills_service()
    app.state.embedding_service = emb_service
    app.state.skills_service = skills_service
    app.state.models_loaded = True

    yield

    # Shutdown: dispose database engine connections
    engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="AI-Based Resume Matching & Ranking Engine Prototype",
    lifespan=lifespan,
)

# CORS middleware for React / Vite frontend
cors_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "*",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API Routers under configured prefix (default "/api")
app.include_router(jd.router, prefix=settings.api_prefix)
app.include_router(resumes.router, prefix=settings.api_prefix)
app.include_router(match.router, prefix=settings.api_prefix)


@app.get("/health", tags=["Health"], status_code=status.HTTP_200_OK)
@app.get(f"{settings.api_prefix}/health", tags=["Health"], status_code=status.HTTP_200_OK)
def health_check() -> dict[str, Any]:
    """Health check endpoint to verify backend status, DB connectivity, and models."""
    db_status = "ok"
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"

    return {
        "status": "healthy" if db_status == "ok" else "degraded",
        "app_name": settings.app_name,
        "version": settings.app_version,
        "database": db_status,
        "database_type": "sqlite" if "sqlite" in settings.database_url else "postgresql",
        "models_loaded": getattr(app.state, "models_loaded", False),
        "models": {
            "embedding": settings.embedding_model_name,
            "spacy": settings.spacy_model_name,
        },
        "weights": {
            "skills": settings.weight_skills,
            "semantic": settings.weight_semantic,
            "experience": settings.weight_experience,
            "education": settings.weight_education,
            "project": settings.weight_project,
        },
    }
