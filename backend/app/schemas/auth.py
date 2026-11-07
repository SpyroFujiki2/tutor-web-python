from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr

from app.models.enums import UserRole, UserStatus


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr = Field(max_length=320)
    password: SecretStr = Field(min_length=1, max_length=1024)


class RefreshRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    refresh_token: SecretStr = Field(min_length=1, max_length=4096)


class CurrentUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str | None
    full_name: str | None = None
    role: UserRole | None
    status: UserStatus


class TokenResponse(BaseModel):
    access_token: str = Field(repr=False)
    refresh_token: str = Field(repr=False)
    token_type: Literal["bearer"] = "bearer"
    expires_in: int = Field(gt=0)
    refresh_expires_in: int = Field(gt=0)


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr = Field(max_length=320)
    password: SecretStr = Field(min_length=8, max_length=1024)
    full_name: str | None = Field(default=None, min_length=1, max_length=200, pattern=r"\S")


class ProfileRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    full_name: str = Field(min_length=1, max_length=200)


class ChangePasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    old_password: SecretStr = Field(min_length=1, max_length=1024)
    new_password: SecretStr = Field(min_length=8, max_length=1024)


class ChangeEmailRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr = Field(max_length=320)
    password: SecretStr = Field(min_length=1, max_length=1024)


class AuthSessionResponse(BaseModel):
    id: UUID
    created_at: datetime
    expires_at: datetime
    is_current: bool
