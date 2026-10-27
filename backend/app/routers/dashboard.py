from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import PlantObservation, User
from app.schemas import DashboardStats
from app.security import get_current_user

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def caring_badge(score: int) -> str:
    if score >= 85:
        return "Excellent"
    if score >= 60:
        return "High"
    if score >= 30:
        return "Medium"
    return "Low"


@router.get("/me", response_model=DashboardStats)
def my_dashboard(current: User = Depends(get_current_user), db: Session = Depends(get_db)):
    observations = db.scalars(select(PlantObservation).where(PlantObservation.user_id == current.id)).all()
    identified = [item for item in observations if item.status == "Identified"]
    now = datetime.now(timezone.utc)
    dates = [item.created_at.replace(tzinfo=timezone.utc) if item.created_at.tzinfo is None else item.created_at for item in observations if item.created_at]
    photos_week = sum(value >= now - timedelta(days=7) for value in dates)
    photos_month = sum(value >= now - timedelta(days=30) for value in dates)
    score = 0
    return DashboardStats(
        plants_identified=len(identified),
        unique_species=len({item.scientific_name for item in identified}),
        photos_this_week=photos_week,
        photos_this_month=photos_month,
        daily_streak=0,
        today_task_complete=False,
        caring_rate=score,
        caring_badge=caring_badge(score),
        people_online=0,
        phase="1",
        note="Plant counts are based on observations saved to your account.",
    )
