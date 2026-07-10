import uuid
from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Limite do LinkedIn para o campo commentary (~3000 chars).
COMMENTARY_MAX = 3000


class BriefCreate(BaseModel):
    theme: str = Field(min_length=3, max_length=500)
    instructions: str | None = Field(default=None, max_length=2000)
    posts_per_week: int = Field(default=3, ge=1, le=7)
    language: str = "pt-BR"
    linkedin_account_id: uuid.UUID


class PostOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    commentary: str
    hashtags: list[str]
    sources: list
    status: str
    publish_at: datetime | None
    published_at: datetime | None
    linkedin_post_urn: str | None
    last_error: str | None


class PostUpdate(BaseModel):
    commentary: str | None = Field(default=None, min_length=1, max_length=COMMENTARY_MAX)
    hashtags: list[str] | None = None


class PostApprove(BaseModel):
    publish_at: datetime

    @field_validator("publish_at")
    @classmethod
    def _tz_aware_and_future(cls, v: datetime) -> datetime:
        # Datetime naive é ambíguo em um sistema multi-fuso: assumimos UTC
        # explicitamente para não depender do timezone do servidor.
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        if v <= datetime.now(timezone.utc):
            raise ValueError("publish_at deve estar no futuro (UTC)")
        return v
