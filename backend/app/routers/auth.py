from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import DEFAULT_CHARACTER, User
from app.schemas import LoginRequest, SignupRequest, TokenResponse, UserPublic
from app.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


def _normalize_identifier(value: str) -> str:
    return value.strip().lower()


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def signup(body: SignupRequest, db: Session = Depends(get_db)):
    email = body.email.lower() if body.email else None
    phone = body.phone

    filters = []
    if email:
        filters.append(User.email == email)
    if phone:
        filters.append(User.phone == phone)
    existing = db.scalar(select(User).where(or_(*filters))) if filters else None
    if existing:
        raise HTTPException(status_code=409, detail="An account with this email or phone already exists")

    user = User(
        email=email,
        phone=phone,
        password_hash=hash_password(body.password),
        display_name=body.display_name.strip(),
        role="user",
        privacy="public",
        character=DEFAULT_CHARACTER.copy(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return TokenResponse(access_token=create_access_token(user.id), user=UserPublic.model_validate(user))


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    identifier = _normalize_identifier(body.identifier)
    user = db.scalar(
        select(User).where(or_(User.email == identifier, User.phone == body.identifier.strip()))
    )
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email/phone or password")
    return TokenResponse(access_token=create_access_token(user.id), user=UserPublic.model_validate(user))
