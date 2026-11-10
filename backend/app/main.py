from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.core.config import Settings
from app.core.errors import DomainError
from app.core.limits import RateLimiter
from app.infrastructure.database import create_session_factory
from app.infrastructure.repositories import KnowledgeRepository
from app.infrastructure.seed import seed
from app.rag.engine import HybridKnowledgeRetriever, load_chunks, persist_chunks


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    session_factory, engine = create_session_factory(settings)
    with session_factory() as session:
        seed(session)
        chunks, _dropped = load_chunks(settings.knowledge_dir)
        KnowledgeRepository(session).replace_all(persist_chunks(chunks))
        session.commit()
    retriever = HybridKnowledgeRetriever(chunks=chunks)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        app.state.engine.dispose()

    app = FastAPI(
        title="Harbourline Bank Assistant POC",
        summary="Fictional local banking assistant. Not a real bank.",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.session_factory = session_factory
    app.state.engine = engine
    app.state.retriever = retriever
    app.state.limiter = RateLimiter()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(DomainError)
    async def handle_domain_error(_request, exc: DomainError):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})

    app.include_router(router, prefix="/api")
    return app


app = create_app()
