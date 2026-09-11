"""Shared FastAPI dependencies (current user resolution)."""
from bson import ObjectId
from bson.errors import InvalidId
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.security import TokenError, decode_access_token
from app.database import USERS, get_db

bearer = HTTPBearer(auto_error=False)


def to_object_id(value: str) -> ObjectId:
    try:
        return ObjectId(value)
    except (InvalidId, TypeError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")


async def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if creds is None or creds.scheme.lower() != "bearer":
        raise unauthorized
    try:
        payload = decode_access_token(creds.credentials)
        user_id = ObjectId(payload["sub"])
    except (TokenError, KeyError, InvalidId, TypeError):
        raise unauthorized
    user = await db[USERS].find_one({"_id": user_id})
    if not user:
        raise unauthorized
    return user
