import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger, Boolean, DateTime, Enum, ForeignKey, Integer, LargeBinary,
    SmallInteger, String, Text, UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, deferred, mapped_column, relationship

from app.database import Base


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class PostStatus(str, enum.Enum):
    draft = "draft"
    approved = "approved"
    publishing = "publishing"
    published = "published"
    failed = "failed"
    cancelled = "cancelled"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String, unique=True)
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    plan: Mapped[str] = mapped_column(String, default="free")
    api_key_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    linkedin_accounts: Mapped[list["LinkedInAccount"]] = relationship(back_populates="user")


class LinkedInAccount(Base):
    __tablename__ = "linkedin_accounts"
    __table_args__ = (UniqueConstraint("user_id", "person_urn"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    person_urn: Mapped[str] = mapped_column(String)
    display_name: Mapped[str | None] = mapped_column(String, nullable=True)
    access_token_enc: Mapped[str] = mapped_column(Text)
    refresh_token_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    access_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    refresh_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scopes: Mapped[str] = mapped_column(String, default="openid profile w_member_social")
    status: Mapped[str] = mapped_column(String, default="active")  # active | needs_reauth | revoked
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="linkedin_accounts")


class ContentBrief(Base):
    __tablename__ = "content_briefs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    linkedin_account_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("linkedin_accounts.id", ondelete="SET NULL"), nullable=True
    )
    theme: Mapped[str] = mapped_column(Text)
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    posts_per_week: Mapped[int] = mapped_column(SmallInteger, default=3)
    source_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_filename: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str] = mapped_column(String, default="pt-BR")
    status: Mapped[str] = mapped_column(String, default="pending")  # pending|generating|generated|failed
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    brief_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("content_briefs.id", ondelete="SET NULL"), nullable=True
    )
    linkedin_account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("linkedin_accounts.id", ondelete="CASCADE")
    )
    commentary: Mapped[str] = mapped_column(Text)
    hashtags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    sources: Mapped[list] = mapped_column(JSONB, default=list)
    # Imagem opcional: blob deferred (listagens não carregam os bytes)
    image_data: Mapped[bytes | None] = deferred(mapped_column(LargeBinary, nullable=True))
    image_mime: Mapped[str | None] = mapped_column(String, nullable=True)
    image_filename: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[PostStatus] = mapped_column(
        Enum(
            PostStatus,
            name="post_status",
            values_callable=lambda e: [m.value for m in e],
        ),
        default=PostStatus.draft,
    )
    publish_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    linkedin_post_urn: Mapped[str | None] = mapped_column(String, nullable=True)
    attempts: Mapped[int] = mapped_column(SmallInteger, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    account: Mapped["LinkedInAccount"] = relationship()

    @property
    def has_image(self) -> bool:
        # image_mime funciona como flag — evita tocar o blob deferred
        return self.image_mime is not None


class PublishLog(Base):
    __tablename__ = "publish_logs"

    # BIGSERIAL no schema.sql -> BigInteger aqui (variant Integer p/ SQLite em testes)
    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    post_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"))
    attempt: Mapped[int] = mapped_column(SmallInteger)
    success: Mapped[bool] = mapped_column(Boolean)
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BrandProfile(Base):
    __tablename__ = "brand_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    entity_type: Mapped[str | None] = mapped_column(String, nullable=True)  # autonomo|colaborador|empresa
    role: Mapped[str | None] = mapped_column(Text, nullable=True)
    company: Mapped[str | None] = mapped_column(Text, nullable=True)
    industry: Mapped[str | None] = mapped_column(Text, nullable=True)
    audience: Mapped[str | None] = mapped_column(Text, nullable=True)
    goal: Mapped[str | None] = mapped_column(String, nullable=True)
    tone: Mapped[str | None] = mapped_column(Text, nullable=True)
    pillars: Mapped[str | None] = mapped_column(Text, nullable=True)
    positioning: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def to_context_dict(self) -> dict:
        return {
            "entity_type": self.entity_type, "role": self.role, "company": self.company,
            "industry": self.industry, "audience": self.audience, "goal": self.goal,
            "tone": self.tone, "pillars": self.pillars, "positioning": self.positioning,
        }
