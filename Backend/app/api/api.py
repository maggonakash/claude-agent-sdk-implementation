from fastapi import APIRouter

from app.api.endpoints import agent, health, sessions

api_router = APIRouter()

api_router.include_router(health.router)
api_router.include_router(sessions.router)
api_router.include_router(agent.router)
