"""Shared MongoDB client and collection references."""
import certifi
from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings

client = AsyncIOMotorClient(settings.MONGODB_URI, tlsCAFile=certifi.where())
db = client[settings.MONGODB_DB_NAME]

users_collection = db["users"]
sessions_collection = db["sessions"]
messages_collection = db["messages"]
feedback_collection = db["feedback"]
