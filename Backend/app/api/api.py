from fastapi import APIRouter

from app.api.endpoints import agent, auth, feedback, health, messages, sessions

api_router = APIRouter()

api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(sessions.router)
api_router.include_router(messages.router)
api_router.include_router(feedback.router)
api_router.include_router(agent.router)
