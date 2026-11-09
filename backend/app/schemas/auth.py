import re
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator


def validate_password_complexity(v: str) -> str:
    """
    Enforces strict password complexity requirements:
    - Minimum 8 characters, maximum 128 characters
    - At least one uppercase letter (A-Z)
    - At least one lowercase letter (a-z)
    - At least one numeric digit (0-9)
    - At least one special symbol (!@#$%^&*()_+-=[]{};':"|,.<>/?`~ etc.)
    """
    if len(v) < 8:
        raise ValueError("Password must be at least 8 characters long.")
    if len(v) > 128:
        raise ValueError("Password must not exceed 128 characters.")
    if not re.search(r"[A-Z]", v):
        raise ValueError("Password must contain at least one uppercase letter (A-Z).")
    if not re.search(r"[a-z]", v):
        raise ValueError("Password must contain at least one lowercase letter (a-z).")
    if not re.search(r"\d", v):
        raise ValueError("Password must contain at least one numeric digit (0-9).")
    if not re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>\/?`~]", v):
        raise ValueError(
            "Password must contain at least one special symbol (!@#$%^&*()_+-=[]{};':\"|,.<>/?`~)."
        )
    return v


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(
        min_length=8,
        max_length=128,
        description="Password must contain uppercase, lowercase, digit, and symbol",
    )
    full_name: str = Field(default="", max_length=255)
    workspace_name: str | None = Field(default=None, max_length=128)

    @field_validator("password")
    @classmethod
    def check_password_complexity(cls, v: str) -> str:
        return validate_password_complexity(v)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(
        min_length=1,
        max_length=128,
        description="Password max length limited to 128 characters to mitigate hashing DoS",
    )


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
        min_length=8,
        max_length=128,
        description="New password must contain uppercase, lowercase, digit, and symbol",
    )

    @field_validator("new_password")
    @classmethod
    def check_new_password_complexity(cls, v: str) -> str:
        return validate_password_complexity(v)


class VerifyEmailRequest(BaseModel):
    token: str = Field(min_length=16, description="Email verification token")


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(
        min_length=8,
        max_length=128,
        description="New password must contain uppercase, lowercase, digit, and symbol",
    )

    @field_validator("new_password")
    @classmethod
    def check_new_password_complexity(cls, v: str) -> str:
        return validate_password_complexity(v)


class MFASetupResponse(BaseModel):
    secret: str
    totp_uri: str
    issuer: str = "AI-MemoryVerse"


class MFAVerifyRequest(BaseModel):
    code: str = Field(min_length=6, max_length=6, description="6-digit TOTP verification code")

    @field_validator("code")
    @classmethod
    def check_code_digits(cls, v: str) -> str:
        if not v.isdigit():
            raise ValueError("MFA code must consist of 6 numeric digits.")
        return v


class MFADisableRequest(BaseModel):
    password: str = Field(min_length=1, max_length=128)
    code: str = Field(min_length=6, max_length=6, description="6-digit TOTP verification code")

    @field_validator("code")
    @classmethod
    def check_code_digits(cls, v: str) -> str:
        if not v.isdigit():
            raise ValueError("MFA code must consist of 6 numeric digits.")
        return v


class MFAAuthenticateRequest(BaseModel):
    mfa_token: str = Field(description="Temporary JWT token issued during primary login challenge")
    code: str = Field(min_length=6, max_length=6, description="6-digit TOTP verification code")

    @field_validator("code")
    @classmethod
    def check_code_digits(cls, v: str) -> str:
        if not v.isdigit():
            raise ValueError("MFA code must consist of 6 numeric digits.")
        return v


class MFARecoveryRequest(BaseModel):
    mfa_token: str = Field(description="Temporary JWT token issued during primary login challenge")
    recovery_code: str = Field(
        min_length=8, max_length=12, description="Single-use backup recovery code"
    )


class MFARegenerateBackupCodesRequest(BaseModel):
    password: str = Field(min_length=1, max_length=128)
    code: str = Field(min_length=6, max_length=6, description="6-digit TOTP verification code")


class MFABackupCodesResponse(BaseModel):
    backup_codes: list[str]
    count: int


class MFABackupCodesCountResponse(BaseModel):
    count: int


class UserSessionResponse(BaseModel):
    id: str
    ip_address: str
    user_agent: str
    device_info: str
    is_current: bool = False
    created_at: datetime
    expires_at: datetime
