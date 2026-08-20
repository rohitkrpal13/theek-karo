"""Auth and user endpoint schemas (API.md §3, SECURITY.md §2-§4)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    contact: str = Field(min_length=3, description="Phone (10-digit or E.164) or email")
    display_name: str = Field(min_length=1, max_length=80)
    password: str | None = Field(default=None, min_length=8, max_length=128)
    username: str | None = Field(default=None, min_length=3, max_length=30)
    consent: bool
    terms_version: str = "2026-v1"
    locale: str = Field(default="hi", min_length=2, max_length=8)
    location_pref: str | None = Field(default=None, max_length=120)


class VerifyOtpRequest(BaseModel):
    contact: str = Field(min_length=3)
    code: str = Field(min_length=6, max_length=6)


class ResendOtpRequest(BaseModel):
    contact: str = Field(min_length=3)


class VerifyEmailRequest(BaseModel):
    token: str = Field(min_length=16, max_length=128)


class ResendEmailVerificationRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)


class LoginPasswordRequest(BaseModel):
    contact: str = Field(min_length=3, description="Email, username, or phone")
    password: str = Field(min_length=1, max_length=128)


class LoginOtpRequest(BaseModel):
    contact: str = Field(min_length=3)


class ForgotPasswordRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=16, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)
    revoke_other_sessions: bool = True


class OAuthCallbackRequest(BaseModel):
    code: str = Field(min_length=1)
    state: str = Field(min_length=1)
    redirect_uri: str = Field(min_length=1)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=32)


class LogoutRequest(BaseModel):
    refresh_token: str = Field(min_length=32)


class ProfileUpdateRequest(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=80)
    username: str | None = Field(default=None, min_length=3, max_length=30)
    bio: str | None = Field(default=None, max_length=500)
    profile_image_url: str | None = Field(default=None, max_length=500)
    location_pref: str | None = Field(default=None, max_length=120)
    locale: str | None = Field(default=None, min_length=2, max_length=8)


class RoleChangeRequest(BaseModel):
    role: str = Field(min_length=2, max_length=32)


class ConsentRevokeRequest(BaseModel):
    purpose: str = Field(min_length=2, max_length=64)


class MfaCodeRequest(BaseModel):
    code: str = Field(min_length=6, max_length=6, description="6-digit TOTP code")


class MfaVerifyRequest(BaseModel):
    challenge_token: str = Field(min_length=16, max_length=2048)
    code: str = Field(min_length=6, max_length=6, description="6-digit TOTP code")
