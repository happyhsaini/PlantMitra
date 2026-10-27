from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, model_validator

Privacy = Literal["public", "friends_only", "private"]
Preset = Literal["leaf_spirit", "gardener", "scientist", "forest_guide", "custom"]
Accessory = Literal["leaf_crown", "hat", "glasses", "basket", "lantern", "none"]


class CharacterIn(BaseModel):
    model_config = {"extra": "ignore"}

    preset: Preset = "leaf_spirit"
    name: str = Field(default="Mitra", min_length=1, max_length=40)
    primary_color: str = Field(default="#2F7D4A", max_length=16)
    secondary_color: str = Field(default="#F4F1E6", max_length=16)
    accessory: Accessory = "leaf_crown"
    greeting: str = Field(default="Namaste! Let's care for a plant today.", max_length=160)


class SignupRequest(BaseModel):
    display_name: str = Field(min_length=2, max_length=80)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=20)
    password: str = Field(min_length=8, max_length=128)

    @model_validator(mode="after")
    def require_contact(self):
        if not self.email and not self.phone:
            raise ValueError("Provide an email or a phone number")
        if self.phone:
            digits = "".join(ch for ch in self.phone if ch.isdigit() or ch == "+")
            if len(digits) < 10:
                raise ValueError("Phone number looks too short")
            self.phone = digits
        return self


class LoginRequest(BaseModel):
    identifier: str = Field(min_length=3, max_length=255, description="Email or phone")
    password: str = Field(min_length=8, max_length=128)


class UserPublic(BaseModel):
    id: UUID
    email: str | None
    phone: str | None
    display_name: str
    role: str
    privacy: Privacy
    character: CharacterIn
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserPublic


class ProfileUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=2, max_length=80)
    privacy: Privacy | None = None
    character: CharacterIn | None = None


class DashboardStats(BaseModel):
    plants_identified: int = 0
    unique_species: int = 0
    photos_this_week: int = 0
    photos_this_month: int = 0
    daily_streak: int = 0
    today_task_complete: bool = False
    caring_rate: int = 0
    caring_badge: Literal["Low", "Medium", "High", "Excellent"] = "Low"
    people_online: int = 0
    phase: str = "1"
    note: str = "Identification, gallery, and live activity arrive in later phases."
