import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from pydantic import BaseModel, Field

from app.database import get_db
from app.models import Post, PostStatus, User
from app.schemas import PostApprove, PostOut, PostUpdate
from app.security import get_current_user, require_subscription
from app.services import image_generator
from app.services.plans import require_feature

router = APIRouter(prefix="/posts", tags=["posts"])


def _own_post(post_id: uuid.UUID, db: Session, user: User) -> Post:
    post = db.query(Post).filter_by(id=post_id, user_id=user.id).first()
    if not post:
        raise HTTPException(404, "Post não encontrado")
    return post


@router.get("", response_model=list[PostOut])
def list_posts(
    status: PostStatus | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = db.query(Post).filter_by(user_id=user.id)
    if status:
        q = q.filter(Post.status == status)
    return q.order_by(Post.created_at.desc()).limit(100).all()


@router.patch("/{post_id}", response_model=PostOut)
def edit_post(
    post_id: uuid.UUID,
    payload: PostUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    post = _own_post(post_id, db, user)
    if post.status not in (PostStatus.draft, PostStatus.approved):
        raise HTTPException(409, "Post não é mais editável")
    if payload.commentary is not None:
        post.commentary = payload.commentary
    if payload.hashtags is not None:
        post.hashtags = payload.hashtags
    db.commit()
    return post


@router.post("/{post_id}/approve", response_model=PostOut)
def approve_post(
    post_id: uuid.UUID,
    payload: PostApprove,
    db: Session = Depends(get_db),
    user: User = Depends(require_subscription),   # publicar é o serviço: exige assinatura
):
    """Humano no loop: nada vai ao LinkedIn sem aprovação explícita + horário."""
    post = _own_post(post_id, db, user)
    if post.status != PostStatus.draft:
        raise HTTPException(409, f"Post em status {post.status.value}, não aprovável")
    post.status = PostStatus.approved
    post.publish_at = payload.publish_at
    db.commit()
    return post


@router.post("/{post_id}/cancel", response_model=PostOut)
def cancel_post(
    post_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    post = _own_post(post_id, db, user)
    if post.status not in (PostStatus.draft, PostStatus.approved):
        raise HTTPException(409, "Post já processado")
    post.status = PostStatus.cancelled
    db.commit()
    return post


# ============ Imagem opcional do post ============
ALLOWED_IMAGE_MIMES = {"image/jpeg", "image/png", "image/gif"}
MAX_IMAGE_BYTES = 8 * 1024 * 1024  # 8 MB


@router.post("/{post_id}/image", response_model=PostOut)
async def upload_post_image(
    post_id: uuid.UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Anexa uma imagem ao post (JPG/PNG/GIF, até 8 MB). Sobe ao LinkedIn só na publicação."""
    post = _own_post(post_id, db, user)
    if post.status not in (PostStatus.draft, PostStatus.approved):
        raise HTTPException(409, "Post não é mais editável")
    if file.content_type not in ALLOWED_IMAGE_MIMES:
        raise HTTPException(415, "Formato não suportado — use JPG, PNG ou GIF")
    data = await file.read()
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(413, "Imagem acima de 8 MB")
    if not data:
        raise HTTPException(400, "Arquivo vazio")
    post.image_data = data
    post.image_mime = file.content_type
    post.image_filename = file.filename
    db.commit()
    return post


@router.get("/{post_id}/image")
def get_post_image(
    post_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    post = _own_post(post_id, db, user)
    if not post.image_mime:
        raise HTTPException(404, "Post sem imagem")
    return Response(content=post.image_data, media_type=post.image_mime)


@router.delete("/{post_id}/image", response_model=PostOut)
def delete_post_image(
    post_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    post = _own_post(post_id, db, user)
    if post.status not in (PostStatus.draft, PostStatus.approved):
        raise HTTPException(409, "Post não é mais editável")
    post.image_data = None
    post.image_mime = None
    post.image_filename = None
    db.commit()
    return post


class GenerateImageIn(BaseModel):
    instructions: str | None = Field(default=None, max_length=500)


@router.post("/{post_id}/generate-image", response_model=PostOut)
def generate_post_image(
    post_id: uuid.UUID,
    payload: GenerateImageIn | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Gera imagem via Gemini a partir do texto do post (substitui a atual, se houver).

    A imagem entra no mesmo campo do upload manual e passa pela mesma revisão
    humana — nada muda no fluxo de aprovação.
    """
    post = _own_post(post_id, db, user)
    if post.status not in (PostStatus.draft, PostStatus.approved):
        raise HTTPException(409, "Post não é mais editável")
    if not require_feature(user, "ai_images"):
        raise HTTPException(402, "Geração de imagem por IA está disponível no plano Pro")
    instructions = payload.instructions if payload else None
    try:
        data, mime = image_generator.generate_post_image(post.commentary, instructions)
    except image_generator.ImageGenError as exc:
        raise HTTPException(exc.status if exc.status in (429, 503) else 502, str(exc))
    post.image_data = data
    post.image_mime = mime
    post.image_filename = "gemini-ai.png"
    db.commit()
    return post
