import uuid
from datetime import datetime

from sqlalchemy import JSON, CheckConstraint, DateTime, Float, ForeignKey, Integer, LargeBinary, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "(email IS NOT NULL) OR (phone IS NOT NULL)",
            name="users_email_or_phone_required",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(20), unique=True, nullable=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(80), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="user")
    privacy: Mapped[str] = mapped_column(String(20), nullable=False, default="public")
    character: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class PlantObservation(Base):
    __tablename__ = "plant_observations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    image: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    image_type: Mapped[str] = mapped_column(String(32), nullable=False)
    dataset_label: Mapped[str | None] = mapped_column(String(80))
    common_name: Mapped[str] = mapped_column(String(120), nullable=False)
    scientific_name: Mapped[str] = mapped_column(String(160), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="Needs identification")
    location: Mapped[str] = mapped_column(String(240), nullable=False, default="Location not added")
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    accuracy: Mapped[float | None] = mapped_column(Float)
    plant_part: Mapped[str] = mapped_column(String(40), nullable=False, default="Other")
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class CharacterPreset:
    LEAF_SPIRIT = "leaf_spirit"
    GARDENER = "gardener"
    SCIENTIST = "scientist"
    FOREST_GUIDE = "forest_guide"
    CUSTOM = "custom"

    ALL = (LEAF_SPIRIT, GARDENER, SCIENTIST, FOREST_GUIDE, CUSTOM)


DEFAULT_CHARACTER = {
    "preset": CharacterPreset.LEAF_SPIRIT,
    "name": "Mitra",
    "primary_color": "#2F7D4A",
    "secondary_color": "#F4F1E6",
    "accessory": "leaf_crown",
    "greeting": "Namaste! Let's care for a plant today.",
}
