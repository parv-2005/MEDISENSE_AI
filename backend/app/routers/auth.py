"""Stage 1 - Authentication: register / login / me."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError

from app.core.deps import get_current_user
from app.core.security import create_access_token, hash_password, verify_password
from app.database import USERS, get_db
from app.models.schemas import TokenOut, UserCreate, UserLogin, UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _user_out(doc: dict) -> UserOut:
    return UserOut(id=str(doc["_id"]), name=doc["name"], email=doc["email"], created_at=doc["created_at"])


def _token_response(doc: dict) -> TokenOut:
    return TokenOut(access_token=create_access_token(subject=str(doc["_id"])), user=_user_out(doc))


@router.post("/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
async def register(payload: UserCreate, db: AsyncIOMotorDatabase = Depends(get_db)):
    email = payload.email.lower()
    if await db[USERS].find_one({"email": email}):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    doc = {
        "name": payload.name.strip(),
        "email": email,
        "password_hash": hash_password(payload.password),
        "created_at": datetime.now(timezone.utc),
    }
    try:
        result = await db[USERS].insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    doc["_id"] = result.inserted_id
    return _token_response(doc)


@router.post("/login", response_model=TokenOut)
async def login(payload: UserLogin, db: AsyncIOMotorDatabase = Depends(get_db)):
    user = await db[USERS].find_one({"email": payload.email.lower()})
    if not user or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    return _token_response(user)


@router.get("/me", response_model=UserOut)
async def me(user: dict = Depends(get_current_user)):
    return _user_out(user)
