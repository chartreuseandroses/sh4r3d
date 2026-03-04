from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.routes import api as api_router

app = FastAPI(title="sh4r3d")

app.add_middleware(SessionMiddleware, secret_key=settings.secret_key)

app.include_router(api_router.router, prefix="/api")
