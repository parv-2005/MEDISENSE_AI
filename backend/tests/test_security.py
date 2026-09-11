import time

import jwt
import pytest

from app.core import security


def test_password_hash_roundtrip():
    hashed = security.hash_password("correct horse battery staple")
    assert hashed != "correct horse battery staple"
    assert security.verify_password("correct horse battery staple", hashed)
    assert not security.verify_password("wrong", hashed)


def test_create_and_decode_access_token_carries_subject():
    token = security.create_access_token(subject="user-123")
    payload = security.decode_access_token(token)
    assert payload["sub"] == "user-123"
    assert payload["exp"] > time.time()


def test_expired_token_is_rejected():
    token = security.create_access_token(subject="user-123", expires_minutes=-1)
    with pytest.raises(security.TokenError):
        security.decode_access_token(token)


def test_tampered_token_is_rejected():
    token = security.create_access_token(subject="user-123")
    forged = jwt.encode({"sub": "attacker"}, "other-secret-that-is-long-enough-for-hs256", algorithm="HS256")
    assert forged != token
    with pytest.raises(security.TokenError):
        security.decode_access_token(forged)
