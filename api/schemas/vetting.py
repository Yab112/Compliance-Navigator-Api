from datetime import date

from pydantic import BaseModel, Field

from schemas.providers import PHONE_PATTERN

LEVEL_PATTERN = "^(grade_10|grade_12|tvet|diploma|degree)$"


class ReferenceIn(BaseModel):
    name: str = Field(..., min_length=3, max_length=120)
    phone: str = Field(..., pattern=PHONE_PATTERN)
    relationship: str = Field(..., min_length=3, max_length=80)


class ReferencesIn(BaseModel):
    references: list[ReferenceIn] = Field(..., max_length=3)


class DocumentDecision(BaseModel):
    decision: str = Field(..., pattern="^(verified|rejected)$")
    note: str | None = Field(None, max_length=500)
    # Staff may correct these to what is printed on the document
    issued_on: date | None = None
    expires_on: date | None = None
    reference_no: str | None = Field(None, max_length=60)
    level: str | None = Field(None, pattern=LEVEL_PATTERN)


class ReferenceDecision(BaseModel):
    decision: str = Field(..., pattern="^(confirmed|failed)$")
    note: str | None = Field(None, max_length=500)


class ChangeDecision(BaseModel):
    decision: str = Field(..., pattern="^(approve|reject)$")
    note: str | None = Field(None, max_length=500)
