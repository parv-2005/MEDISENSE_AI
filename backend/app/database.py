"""MongoDB connection management (Motor, async)."""
from fastapi import Request
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.config import get_settings

USERS = "users"
REPORTS = "reports"
ANALYSES = "analyses"
QA_HISTORY = "qa_history"


def create_client() -> AsyncIOMotorClient:
    return AsyncIOMotorClient(get_settings().mongodb_uri, serverSelectionTimeoutMS=5000)


async def init_indexes(db: AsyncIOMotorDatabase) -> None:
    await db[USERS].create_index("email", unique=True)
    await db[REPORTS].create_index([("user_id", 1), ("created_at", -1)])
    await db[ANALYSES].create_index([("report_id", 1)], unique=True)
    await db[QA_HISTORY].create_index([("report_id", 1), ("created_at", 1)])


def get_db(request: Request) -> AsyncIOMotorDatabase:
    """FastAPI dependency. Overridden in tests with an in-memory database."""
    db = getattr(request.app.state, "db", None)
    if db is None:
        raise RuntimeError("Database is not connected.")
    return db
