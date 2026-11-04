from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.common import APIResponse
from app.schemas.user import UserResponse, UserUpdateRequest
from app.services.auth_service import AuthService

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=APIResponse[UserResponse])
async def get_current_user_profile(
    current_user: User = Depends(get_current_active_user),
):
    return APIResponse(
        success=True,
        data=UserResponse.model_validate(current_user),
    )


@router.patch("/me", response_model=APIResponse[UserResponse])
async def update_current_user_profile(
    data: UserUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    if data.full_name is not None:
        current_user.full_name = data.full_name

    if data.profile and current_user.profile:
        if data.profile.bio is not None:
            current_user.profile.bio = data.profile.bio
        if data.profile.avatar_url is not None:
            current_user.profile.avatar_url = data.profile.avatar_url
        if data.profile.ai_custom_instructions is not None:
            current_user.profile.ai_custom_instructions = data.profile.ai_custom_instructions
        if data.profile.preferences is not None:
            current_user.profile.preferences = data.profile.preferences

    await db.commit()
    await db.refresh(current_user)

    return APIResponse(
        success=True,
        data=UserResponse.model_validate(current_user),
    )


@router.delete("/me", response_model=APIResponse[dict])
async def delete_current_user_account(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """GDPR-compliant permanent account deletion with cascade cleanup."""
    await AuthService.delete_user_account(db, current_user.id)
    return APIResponse(
        success=True,
        data={
            "message": (
                "User account and all associated personal data have been permanently deleted."
            )
        },
    )
