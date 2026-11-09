"""FastAPI application: the pvorg API plus the built single-page app."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from api import cleanup_api, filters, library, mapping, media, system, viewer
from pipeline import Pipeline
from state import AppState

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"

# Routes from before the redesign, kept so bookmarks still work.
LEGACY_ROUTES = {"/config": "/filters", "/deleter": "/library", "/mapper": "/mapping/galleries",
                 "/tag-mapper": "/mapping/tags"}


def create_app(*, start_pipeline: bool = True, preprocess: bool = True) -> FastAPI:
    state = AppState()
    pipeline = Pipeline(state, preprocess=preprocess)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        if start_pipeline:
            pipeline.start()
        yield

    app = FastAPI(title="PP Video Organizer", lifespan=lifespan)
    app.state.pvorg = state
    app.state.pipeline = pipeline

    port = os.environ.get("PVORG_PORT", "8000")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[f"http://127.0.0.1:{port}", f"http://localhost:{port}",
                       "http://127.0.0.1:5173", "http://localhost:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(system.create_router(state, pipeline))
    app.include_router(viewer.create_router(state))
    app.include_router(filters.create_router(state))
    app.include_router(library.create_router(state))
    app.include_router(mapping.create_router(state))
    app.include_router(cleanup_api.create_router(state))
    app.include_router(media.create_router(state))

    for old, new in LEGACY_ROUTES.items():
        app.add_api_route(old, lambda new=new: RedirectResponse(new, status_code=308), include_in_schema=False)

    if FRONTEND_DIST.is_dir():
        app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str) -> FileResponse:
            """Serve built files, and index.html for client routes so deep links survive a refresh."""
            if path.startswith("api/"):
                raise HTTPException(status_code=404)
            candidate = (FRONTEND_DIST / path).resolve()
            if path and candidate.is_file() and FRONTEND_DIST in candidate.parents:
                return FileResponse(candidate)
            return FileResponse(FRONTEND_DIST / "index.html", headers={"Cache-Control": "no-cache"})

    return app


app = create_app()


def run() -> None:
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=int(os.environ.get("PVORG_PORT", "8000")))
