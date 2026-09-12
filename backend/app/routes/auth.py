"""User authentication routes: Sign Up, Sign In, Profile (Me), and Logout.

Provides enterprise credential verification, password hashing with PBKDF2-HMAC-SHA256,
and session management.
"""

import logging
import re
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app import secrets as secret_store
from app.db import get_db, is_enabled
from app.db import repo
from app.db.models import Account

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Authentication"])


def require_db() -> None:
    if not is_enabled():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database persistence is required for user authentication.",
        )


def extract_token(
    authorization: Optional[str] = Header(None),
    x_account_key: Optional[str] = Header(None),
) -> Optional[str]:
    """Extract token from Authorization: Bearer <token> or X-Account-Key header."""
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    if x_account_key:
        return x_account_key.strip()
    return None


def get_current_user(
    authorization: Optional[str] = Header(None),
    x_account_key: Optional[str] = Header(None),
    session: Session = Depends(get_db),
) -> Account:
    require_db()
    token = extract_token(authorization, x_account_key)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    account = repo.account_for_key(session, token)
    if not account:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return account


class SignUpRequest(BaseModel):
    email: str
    password: str = Field(min_length=6, description="Password must be at least 6 characters")
    display_name: Optional[str] = None


class SignInRequest(BaseModel):
    email: str
    password: str


class AuthUser(BaseModel):
    id: int
    email: Optional[str]
    display_name: Optional[str]
    created_at: Optional[str]


class AuthResponse(BaseModel):
    token: str
    user: AuthUser
    message: str


@router.post("/signup", response_model=AuthResponse)
def signup(body: SignUpRequest, session: Session = Depends(get_db)):
    """Register a new user account with email and password."""
    require_db()
    email_clean = body.email.strip().lower()
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email_clean):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid email address format.")

    existing = repo.account_for_email(session, email_clean)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email address already exists. Please sign in instead.",
        )

    pwd_hash = secret_store.hash_password(body.password)
    display_name = (body.display_name or "").strip() or email_clean.split("@")[0].capitalize()

    account, token = repo.register_user(
        session=session,
        email=email_clean,
        password_hash=pwd_hash,
        display_name=display_name,
    )

    return AuthResponse(
        token=token,
        user=AuthUser(
            id=account.id,
            email=account.email,
            display_name=account.display_name,
            created_at=account.created_at.isoformat() if account.created_at else None,
        ),
        message="Account created successfully.",
    )


@router.post("/signin", response_model=AuthResponse)
def signin(body: SignInRequest, session: Session = Depends(get_db)):
    """Sign in with email and password."""
    require_db()
    email_clean = body.email.strip().lower()
    account = repo.account_for_email(session, email_clean)
    if not account:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password. Please check your credentials.",
        )

    if not account.password_hash or not secret_store.verify_password(body.password, account.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password. Please check your credentials.",
        )

    token = repo.issue_new_key(session, account)

    return AuthResponse(
        token=token,
        user=AuthUser(
            id=account.id,
            email=account.email,
            display_name=account.display_name,
            created_at=account.created_at.isoformat() if account.created_at else None,
        ),
        message="Signed in successfully.",
    )


@router.get("/me")
def me(account: Account = Depends(get_current_user)):
    """Get currently authenticated user details."""
    return {
        "authenticated": True,
        "user": {
            "id": account.id,
            "email": account.email,
            "display_name": account.display_name,
            "created_at": account.created_at.isoformat() if account.created_at else None,
        },
    }


@router.post("/logout")
def logout(account: Account = Depends(get_current_user), session: Session = Depends(get_db)):
    """Log out and invalidate current session token."""
    # Rotate token so existing key is revoked
    repo.issue_new_key(session, account)
    return {"success": True, "message": "Successfully logged out."}
