from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    bio: str
    avatar_url: str
    ai_custom_instructions: str
    preferences: dict


class UserProfileUpdateRequest(BaseModel):
    bio: str | None = Field(default=None, max_length=500)
    avatar_url: str | None = Field(default=None, max_length=1000)
    ai_custom_instructions: str | None = Field(default=None, max_length=2000)
    preferences: dict | None = None


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: EmailStr
    full_name: str
    is_active: bool
    is_verified: bool
    is_superuser: bool
    is_mfa_enabled: bool = False
    created_at: datetime
    updated_at: datetime
    profile: UserProfileResponse | None = None


class UserUpdateRequest(BaseModel):
    full_name: str | None = Field(default=None, max_length=100)
    profile: UserProfileUpdateRequest | None = None
