"""PET Enzyme Explorer API.

    .venv/bin/uvicorn backend.main:app --port 8000      # from the repository root

Serves the cached outputs of `python -m pet_explorer.pipeline` and runs live
sequence matching with pet_explorer.sequence_matching.
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from .api import conditions, datasets, network, organisms, overview, sequence
from .services import layout, matching, store


@asynccontextmanager
async def lifespan(app):
    # load every table once so the first request is fast and missing files fail loudly
    for loader in (store.proteins, store.pairs, store.temperature_summary, store.temperature_assays,
                   store.organisms, layout.packed_layout, matching.matcher):
        loader()
    yield


app = FastAPI(title="PET Enzyme Explorer API", version="1.0", lifespan=lifespan)
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("PET_EXPLORER_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(","),
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"status": "ok", "proteins": len(store.proteins()),
            "organism_table": len(store.organisms()) > 0, "matcher_ready": matching.matcher() is not None}


for module in (overview, sequence, network, conditions, organisms, datasets):
    app.include_router(module.router, prefix="/api")
