from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import require_admin
from app.core.database import get_db
from app.core.security import hash_password
from app.models.asset import Asset
from app.models.user import User
from app.models.video_job import VideoJob
from app.schemas.auth import (
    AdminUserCreate,
    AdminUserCreated,
    AdminUserUpdate,
    ResetPasswordRequest,
    ResetPasswordResponse,
    UserListResponse,
    UserResponse,
)


router = APIRouter(prefix="/admin/users", tags=["admin-users"])


async def get_target(db: AsyncSession, user_id: str) -> User:
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="账号不存在")
    return user


@router.get("", response_model=UserListResponse)
async def list_users(
    _: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    query: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> UserListResponse:
    conditions = []
    if query:
        pattern = f"%{query.strip()}%"
        conditions.append(
            or_(User.username.ilike(pattern), User.display_name.ilike(pattern))
        )
    statement = select(User)
    count_statement = select(func.count(User.id))
    if conditions:
        statement = statement.where(*conditions)
        count_statement = count_statement.where(*conditions)
    total = int(await db.scalar(count_statement) or 0)
    users = (
        await db.scalars(
            statement.order_by(User.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    return UserListResponse(items=list(users), total=total, page=page, page_size=page_size)


@router.post("", response_model=AdminUserCreated, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: AdminUserCreate,
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AdminUserCreated:
    exists = await db.scalar(select(User.id).where(User.username == payload.username))
    if exists:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="用户名已存在")
    user = User(
        username=payload.username,
        display_name=payload.display_name,
        password_hash=hash_password(payload.initial_password),
        role=payload.role,
        is_active=payload.is_active,
        must_change_password=True,
        remark=payload.remark,
        created_by=admin.id,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return AdminUserCreated(user=UserResponse.model_validate(user), initial_password=payload.initial_password)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    _: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    return await get_target(db, user_id)


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    payload: AdminUserUpdate,
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    user = await get_target(db, user_id)
    changes = payload.model_dump(exclude_unset=True)
    if user.id == admin.id and changes.get("role") == "user":
        raise HTTPException(status_code=400, detail="不能降低当前登录管理员的角色")
    for key, value in changes.items():
        setattr(user, key, value)
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/{user_id}/reset-password", response_model=ResetPasswordResponse)
async def reset_password(
    user_id: str,
    payload: ResetPasswordRequest,
    _: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ResetPasswordResponse:
    user = await get_target(db, user_id)
    user.password_hash = hash_password(payload.new_password)
    user.must_change_password = True
    user.session_version += 1
    await db.commit()
    return ResetPasswordResponse(
        username=user.username,
        initial_password=payload.new_password,
    )


@router.post("/{user_id}/enable", response_model=UserResponse)
async def enable_user(
    user_id: str,
    _: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    user = await get_target(db, user_id)
    user.is_active = True
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/{user_id}/disable", response_model=UserResponse)
async def disable_user(
    user_id: str,
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    user = await get_target(db, user_id)
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="不能禁用当前登录账号")
    user.is_active = False
    user.session_version += 1
    await db.commit()
    await db.refresh(user)
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: str,
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    user = await get_target(db, user_id)
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="不能删除当前登录账号")
    job_count = int(
        await db.scalar(select(func.count(VideoJob.id)).where(VideoJob.user_id == user.id))
        or 0
    )
    asset_count = int(
        await db.scalar(select(func.count(Asset.id)).where(Asset.user_id == user.id)) or 0
    )
    if job_count or asset_count:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="账号已产生业务数据，不能删除；请改为禁用",
        )
    await db.delete(user)
    await db.commit()
