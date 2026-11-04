from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128, description="Password minimum 8 chars")
    full_name: str = Field(default="", max_length=255)
    workspace_name: str | None = Field(default=None, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_token: str | None = None


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=16, description="Password reset verification token")
    new_password: str = Field(
        min_length=8, max_length=128, description="New password minimum 8 chars"
    )


class VerifyEmailRequest(BaseModel):
    token: str = Field(min_length=16, description="Email verification token")
