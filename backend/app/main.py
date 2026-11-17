from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.core.config import settings
from app.database import engine
from app.api.routes.orders import router as orders_router
from app.api.routes.planning import router as planning_router

app = FastAPI(title=settings.APP_NAME, version=settings.APP_VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://localhost:5175",
        "http://127.0.0.1:5175",
        "http://127.0.0.1:5176",
        "http://localhost:5177",
        "http://127.0.0.1:5177",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_private_network=True,
)

app.include_router(orders_router)
app.include_router(planning_router)


@app.get("/")
def root():
    return {"application": settings.APP_NAME, "status": "running"}


@app.get("/api/v1/health")
def health():
    try:
        with engine.connect() as connection:
            database_name = connection.execute(text("SELECT current_database()")).scalar_one()
        return {
            "status": "healthy",
            "backend": "Python FastAPI",
            "database": "connected",
            "database_name": database_name,
        }
    except Exception:
        return {
            "status": "unhealthy",
            "backend": "Python FastAPI",
            "database": "disconnected",
        }

from app.api.routes.purchases import router as purchases_router
app.include_router(purchases_router)

from app.api.routes.production import router as production_router
app.include_router(production_router)
