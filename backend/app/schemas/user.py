import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.models.user import PlanTier


class UserCreate(BaseModel):
    email: EmailStr
    # Length, not complexity rules (no forced uppercase/digit/symbol) -
    # current guidance (NIST 800-63B) favors length over composition rules,
    # which push people toward predictable substitutions ("Password1!")
    # rather than actually harder-to-guess passwords. max_length is a sanity
    # cap, not a security control - bcrypt itself only hashes the first 72
    # bytes of whatever it's given.
    password: str = Field(min_length=8, max_length=128)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: uuid.UUID
    email: EmailStr
    plan: PlanTier
    created_at: datetime

    model_config = {"from_attributes": True}


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
