"""FastAPI 入口。启动时建表，开发期允许 Vite 跨域。"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .admin import router as admin_router
from .api import router
from .config import DEV_ORIGIN, DB_PATH
from .db import init_db


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="Onefold API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[DEV_ORIGIN, "http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(admin_router)


@app.get("/health")
def health():
    return {"ok": True, "db": str(DB_PATH)}
