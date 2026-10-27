from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas import ProfileUpdate, UserPublic
from app.security import get_current_user

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserPublic)
def me(current: User = Depends(get_current_user)):
    return current


@router.patch("/me", response_model=UserPublic)
def update_me(
    body: ProfileUpdate,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    if body.display_name is not None:
        current.display_name = body.display_name.strip()
    if body.privacy is not None:
        current.privacy = body.privacy
    if body.character is not None:
        current.character = body.character.model_dump()
    db.add(current)
    db.commit()
    db.refresh(current)
    return current
