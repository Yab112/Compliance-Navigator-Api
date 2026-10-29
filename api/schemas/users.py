from pydantic import BaseModel, EmailStr, Field

from schemas.telegram import TelegramUsername

PHONE_PATTERN = r"^(\+251|0)[79]\d{8}$"
SUB_CITY_PATTERN = "^(addis_ketema|akaki|arada|bole|gulele|kirkos|kolfe|lideta|nifas_silk|yeka)$"


class UserCreate(BaseModel):
    email: EmailStr
    # Strength rules live in auth.security.password_problem so every path shares them
    password: str = Field(min_length=1, max_length=200)
    fullname: str = Field(min_length=2, max_length=120)
    phone: str | None = Field(None, pattern=PHONE_PATTERN)


class LoginBody(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class ProfileUpdate(BaseModel):
    fullname: str | None = Field(None, min_length=2, max_length=120)
    phone: str | None = Field(None, pattern=PHONE_PATTERN)
    preferred_sub_city: str | None = Field(None, pattern=SUB_CITY_PATTERN)
    telegram_username: TelegramUsername = None


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=1, max_length=200)


class ForgotPassword(BaseModel):
    email: EmailStr


class PasswordReset(BaseModel):
    token: str = Field(min_length=20, max_length=200)
    new_password: str = Field(min_length=1, max_length=200)
