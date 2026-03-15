import logging
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.api import api_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

app = FastAPI(
    title="Document Agent API",
    description="Upload documents and interact with them via a Claude-powered agent.",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def create_db_indexes():
    """Ensure all MongoDB indexes exist on startup."""
    from app.db.users import create_indexes as user_indexes
    from app.db.sessions import create_indexes as session_indexes
    from app.db.messages import create_indexes as message_indexes
    from app.db.feedback import create_indexes as feedback_indexes
    await user_indexes()
    await session_indexes()
    await message_indexes()
    await feedback_indexes()


app.include_router(api_router)
