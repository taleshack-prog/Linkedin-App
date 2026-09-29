import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger, Boolean, Date, DateTime, Enum, ForeignKey, Integer, LargeBinary,
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
    api_key_hash: Mapped[str | None] = mapped_column(String, nullable=True)  # legado (transição p/ JWT)
    password_hash: Mapped[str | None] = mapped_column(String, nullable=True)   # bcrypt
    google_sub: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    referral_code: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    referred_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # Billing (Stripe)
    stripe_customer_id: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    plan_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    referral_active: Mapped[bool] = mapped_column(Boolean, default=False)  # já assinou pago ao menos 1x (conta p/ o padrinho)
    referral_months_granted: Mapped[int] = mapped_column(SmallInteger, default=0)  # meses de crédito já concedidos
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # passive_deletes=True: deixa o ON DELETE CASCADE do banco fazer o trabalho.
    # Sem isso o ORM tenta setar user_id=NULL (que é NOT NULL) e a EXCLUSÃO DE
    # CONTA falha — violando o direito de exclusão da LGPD (art. 18, VI).
    linkedin_accounts: Mapped[list["LinkedInAccount"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )


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
    use_profile: Mapped[bool] = mapped_column(Boolean, default=True)
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
    video_urn: Mapped[str | None] = mapped_column(String, nullable=True)
    video_status: Mapped[str | None] = mapped_column(String, nullable=True)  # processing | available | failed
    video_title: Mapped[str | None] = mapped_column(String, nullable=True)
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
    images: Mapped[list["PostImage"]] = relationship(
        order_by="PostImage.ordinal", cascade="all, delete-orphan", passive_deletes=True
    )

    @property
    def has_image(self) -> bool:
        # Tem imagem se existe pelo menos uma linha em post_images (fonte única)
        return len(self.images) > 0

    @property
    def has_video(self) -> bool:
        return self.video_urn is not None


class PostImage(Base):
    __tablename__ = "post_images"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    post_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"))
    ordinal: Mapped[int] = mapped_column(SmallInteger, default=0)
    image_data: Mapped[bytes] = deferred(mapped_column(LargeBinary, nullable=False))
    image_mime: Mapped[str] = mapped_column(String)
    image_filename: Mapped[str | None] = mapped_column(String, nullable=True)
    alt_text: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


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


# ===========================================================================
# Auditoria de marca — alimentada por upload (PDF do perfil, export .xlsx de
# analytics, textos de posts). Nada aqui vem de API do LinkedIn: os escopos
# self-serve não dão perfil nem métrica.
# ===========================================================================
class ProfileAudit(Base):
    __tablename__ = "profile_audits"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    # Componentes nulos quando faltou material — nunca preenchidos por estimativa.
    score_total: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    score_perfil: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    score_conteudo: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    score_consistencia: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    fontes: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    resultado: Mapped[dict] = mapped_column(JSONB, default=dict)  # JSON completo do auditor
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AnalyticsSnapshot(Base):
    """Uma janela do export de analytics.

    O LinkedIn só entrega períodos curtos e não guarda histórico para o usuário.
    Acumulando cada upload aqui, o Posthink passa a ter a série que a própria
    plataforma não mostra.
    """

    __tablename__ = "analytics_snapshots"
    __table_args__ = (UniqueConstraint("user_id", "periodo_inicio", "periodo_fim",
                                       name="uq_snapshot_periodo"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    periodo_inicio: Mapped[datetime] = mapped_column(Date)
    periodo_fim: Mapped[datetime] = mapped_column(Date)
    impressoes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    alcance: Mapped[int | None] = mapped_column(Integer, nullable=True)
    engajamentos: Mapped[int | None] = mapped_column(Integer, nullable=True)
    seguidores_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    seguidores_novos: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dados: Mapped[dict] = mapped_column(JSONB, default=dict)  # série diária + demografia
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PostMetric(Base):
    """Desempenho por publicação, acumulado entre uploads.

    `share_id` é o número final do URN, extraído da URL do export. Quando ele
    casa com o `linkedin_post_urn` de um post nosso, `post_id` é preenchido e
    passamos a ter métrica e texto do mesmo post — que é o que permite avaliar
    o que funcionou sem depender de API de analytics.
    """

    __tablename__ = "post_metrics"
    __table_args__ = (UniqueConstraint("user_id", "share_id", name="uq_metric_post"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    post_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("posts.id", ondelete="SET NULL"), nullable=True
    )
    share_id: Mapped[str] = mapped_column(String)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    publicado_em: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    impressoes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    engajamentos: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tema_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    medido_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
