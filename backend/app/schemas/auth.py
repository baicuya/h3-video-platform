from __future__ import annotations

import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,32}$")


def validate_username(value: str) -> str:
    if not USERNAME_RE.fullmatch(value):
        raise ValueError("用户名须为 3～32 位字母、数字、下划线、点或短横线")
    return value


def validate_password(value: str) -> str:
    if len(value) < 8:
        raise ValueError("密码至少 8 位")
    return value


class LoginRequest(BaseModel):
    username: str
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str
    confirm_password: str

    _password_length = field_validator("new_password")(validate_password)

    @model_validator(mode="after")
    def passwords_match(self) -> "ChangePasswordRequest":
        if self.new_password != self.confirm_password:
            raise ValueError("两次输入的新密码不一致")
        return self


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    username: str
    display_name: str
    role: str
    is_active: bool
    must_change_password: bool
    remark: str | None
    last_login_at: datetime | None
    created_by: str | None
    created_at: datetime
    updated_at: datetime


class AdminUserCreate(BaseModel):
    username: str
    display_name: str = Field(min_length=1, max_length=64)
    initial_password: str
    confirm_password: str
    role: str = "user"
    is_active: bool = True
    remark: str | None = Field(default=None, max_length=2000)

    _username_format = field_validator("username")(validate_username)
    _password_length = field_validator("initial_password")(validate_password)

    @field_validator("role")
    @classmethod
    def role_allowed(cls, value: str) -> str:
        if value not in {"admin", "user"}:
            raise ValueError("角色只能是 admin 或 user")
        return value

    @model_validator(mode="after")
    def passwords_match(self) -> "AdminUserCreate":
        if self.initial_password != self.confirm_password:
            raise ValueError("两次输入的初始密码不一致")
        return self


class AdminUserCreated(BaseModel):
    user: UserResponse
    initial_password: str


class AdminUserUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=64)
    role: str | None = None
    remark: str | None = Field(default=None, max_length=2000)

    @field_validator("role")
    @classmethod
    def role_allowed(cls, value: str | None) -> str | None:
        if value is not None and value not in {"admin", "user"}:
            raise ValueError("角色只能是 admin 或 user")
        return value


class ResetPasswordRequest(BaseModel):
    new_password: str
    confirm_password: str

    _password_length = field_validator("new_password")(validate_password)

    @model_validator(mode="after")
    def passwords_match(self) -> "ResetPasswordRequest":
        if self.new_password != self.confirm_password:
            raise ValueError("两次输入的新密码不一致")
        return self


class ResetPasswordResponse(BaseModel):
    username: str
    initial_password: str


class UserListResponse(BaseModel):
    items: list[UserResponse]
    total: int
    page: int
    page_size: int
