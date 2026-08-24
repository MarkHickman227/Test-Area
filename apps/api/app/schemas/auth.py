from __future__ import annotations

from datetime import datetime

from pydantic import EmailStr, Field

from app.schemas.common import APIModel, ConsentPayload


class RegisterRequest(APIModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=200)
    acceptances: ConsentPayload
    invite_code: str | None = None


class LoginRequest(APIModel):
    email: EmailStr
    password: str


class VerifyEmailRequest(APIModel):
    token: str


class PasswordForgotRequest(APIModel):
    email: EmailStr


class PasswordResetRequest(APIModel):
    token: str
    password: str = Field(min_length=10, max_length=200)


class MfaVerifyRequest(APIModel):
    code: str = Field(min_length=6, max_length=8)


class UserPublic(APIModel):
    id: str
    email: str
    status: str
    role: str
    email_verified_at: datetime | None
    age_verified_at: datetime | None
    age_verification_status: str
    mfa_enabled: bool
    plan_id: str | None = None


class SessionResponse(APIModel):
    user: UserPublic
    csrf_token: str
    mfa_required: bool = False
