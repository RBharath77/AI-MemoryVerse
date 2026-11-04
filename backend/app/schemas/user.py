from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class UserProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    bio: str
    avatar_url: str
    ai_custom_instructions: str
    preferences: dict


class UserProfileUpdateRequest(BaseModel):
    bio: str | None = None
    avatar_url: str | None = None
    ai_custom_instructions: str | None = None
    preferences: dict | None = None


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: EmailStr
    full_name: str
    is_active: bool
    is_verified: bool
    is_superuser: bool
    created_at: datetime
    updated_at: datetime
    profile: UserProfileResponse | None = None


class UserUpdateRequest(BaseModel):
    full_name: str | None = None
    profile: UserProfileUpdateRequest | None = None
