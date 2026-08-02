from fastapi import FastAPI
from sqlalchemy import text

from config import settings
from database import engine

app = FastAPI(title=settings.app_name)


@app.get("/api/v1/health")
def health():
    return {"status": "ok", "env": settings.env}


@app.get("/api/v1/health/db")
def health_db():
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ok", "database": "connected"}
