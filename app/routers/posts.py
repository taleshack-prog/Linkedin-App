import os
import tempfile
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session, selectinload

from pydantic import BaseModel, Field

from app.database import get_db
from app.models import LinkedInAccount, Post, PostImage, PostStatus, User
from app.schemas import PostApprove, PostOut, PostUpdate
from app.security import get_current_user, require_subscription
from app.services import image_generator, linkedin_client as li
from app.services.plans import max_images_for, require_feature
from app.tasks.publish_tasks import _ensure_fresh_token

router = APIRouter(prefix="/posts", tags=["posts"])


def _own_post(post_id: uuid.UUID, db: Session, user: User) -> Post:
    post = db.query(Post).filter_by(id=post_id, user_id=user.id).first()
    if not post:
        raise HTTPException(404, "Post não encontrado")
    return post


def _post_images(db: Session, post: Post) -> list[PostImage]:
    return db.query(PostImage).filter_by(post_id=post.id).order_by(PostImage.ordinal).all()


def _clear_legacy_image(post: Post) -> None:
    post.image_data = None
    post.image_mime = None
    post.image_filename = None


def _clear_video(post: Post) -> None:
    post.video_urn = None
    post.video_status = None
    post.video_title = None


@router.get("", response_model=list[PostOut])
def list_posts(
    status: PostStatus | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = db.query(Post).options(selectinload(Post.images)).filter_by(user_id=user.id)
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
    user: User = Depends(require_subscription),
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


# ============ Imagens do post (unificado em post_images; até max_images do plano) ============
ALLOWED_IMAGE_MIMES = {"image/jpeg", "image/png", "image/gif"}
MAX_IMAGE_BYTES = 8 * 1024 * 1024  # 8 MB por imagem


class PostImageOut(BaseModel):
    id: uuid.UUID
    ordinal: int
    image_mime: str
    image_filename: str | None
    alt_text: str | None

    class Config:
        from_attributes = True


async def _read_image_upload(file: UploadFile) -> bytes:
    if file.content_type not in ALLOWED_IMAGE_MIMES:
        raise HTTPException(415, "Formato não suportado — use JPG, PNG ou GIF")
    data = await file.read()
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(413, "Imagem acima de 8 MB")
    if not data:
        raise HTTPException(400, "Arquivo vazio")
    return data


# ---- Múltiplas imagens (carrossel) ----
@router.get("/{post_id}/images", response_model=list[PostImageOut])
def list_post_images(
    post_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    post = _own_post(post_id, db, user)
    return _post_images(db, post)


@router.post("/{post_id}/images", response_model=PostOut)
async def add_post_image(
    post_id: uuid.UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Adiciona uma imagem ao post, respeitando o teto do plano (max_images)."""
    post = _own_post(post_id, db, user)
    if post.status not in (PostStatus.draft, PostStatus.approved):
        raise HTTPException(409, "Post não é mais editável")
    data = await _read_image_upload(file)
    existing = _post_images(db, post)
    limit = max_images_for(user)
    if len(existing) >= limit:
        if limit <= 1:
            raise HTTPException(402, "Múltiplas imagens por post estão disponíveis nos planos Pro e Agency")
        raise HTTPException(409, f"Limite de {limit} imagens por post atingido")
    db.add(PostImage(post_id=post.id, ordinal=len(existing),
                     image_data=data, image_mime=file.content_type, image_filename=file.filename))
    _clear_legacy_image(post)
    _clear_video(post)
    db.commit()
    return post


@router.get("/{post_id}/images/{image_id}")
def get_post_image_by_id(
    post_id: uuid.UUID,
    image_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    post = _own_post(post_id, db, user)
    img = db.query(PostImage).filter_by(id=image_id, post_id=post.id).first()
    if not img:
        raise HTTPException(404, "Imagem não encontrada")
    return Response(content=img.image_data, media_type=img.image_mime)


@router.delete("/{post_id}/images/{image_id}", response_model=PostOut)
def delete_post_image_by_id(
    post_id: uuid.UUID,
    image_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    post = _own_post(post_id, db, user)
    if post.status not in (PostStatus.draft, PostStatus.approved):
        raise HTTPException(409, "Post não é mais editável")
    img = db.query(PostImage).filter_by(id=image_id, post_id=post.id).first()
    if not img:
        raise HTTPException(404, "Imagem não encontrada")
    db.delete(img)
    db.flush()
    remaining = _post_images(db, post)
    for i, im in enumerate(remaining):
        im.ordinal = i
    if not remaining:
        _clear_legacy_image(post)
    db.commit()
    return post


# ---- Imagem única (legado): mantém o frontend atual funcionando, sobre post_images ----
@router.post("/{post_id}/image", response_model=PostOut)
async def upload_post_image(
    post_id: uuid.UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Anexa uma imagem, substituindo qualquer imagem existente (semântica de imagem única)."""
    post = _own_post(post_id, db, user)
    if post.status not in (PostStatus.draft, PostStatus.approved):
        raise HTTPException(409, "Post não é mais editável")
    data = await _read_image_upload(file)
    db.query(PostImage).filter_by(post_id=post.id).delete()
    db.flush()
    db.add(PostImage(post_id=post.id, ordinal=0, image_data=data,
                     image_mime=file.content_type, image_filename=file.filename))
    _clear_legacy_image(post)
    _clear_video(post)
    db.commit()
    return post


@router.get("/{post_id}/image")
def get_post_image(
    post_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    post = _own_post(post_id, db, user)
    imgs = _post_images(db, post)
    if not imgs:
        raise HTTPException(404, "Post sem imagem")
    return Response(content=imgs[0].image_data, media_type=imgs[0].image_mime)


@router.delete("/{post_id}/image", response_model=PostOut)
def delete_post_image(
    post_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    post = _own_post(post_id, db, user)
    if post.status not in (PostStatus.draft, PostStatus.approved):
        raise HTTPException(409, "Post não é mais editável")
    db.query(PostImage).filter_by(post_id=post.id).delete()
    _clear_legacy_image(post)
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
    """Gera imagem via IA a partir do texto do post (substitui as imagens atuais)."""
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
    db.query(PostImage).filter_by(post_id=post.id).delete()
    db.flush()
    db.add(PostImage(post_id=post.id, ordinal=0, image_data=data,
                     image_mime=mime, image_filename="gemini-ai.png"))
    _clear_legacy_image(post)
    _clear_video(post)
    db.commit()
    return post


# ============ Vídeo opcional do post (Pro/Agency) ============
ALLOWED_VIDEO_MIMES = {"video/mp4", "application/mp4"}
MAX_VIDEO_BYTES = 100 * 1024 * 1024  # 100 MB (v1: upload síncrono via API)


@router.post("/{post_id}/video", response_model=PostOut)
async def upload_post_video(
    post_id: uuid.UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Anexa um vídeo MP4 (até 100 MB). Sobe pro LinkedIn na hora (guarda só a URN);
    a publicação continua no horário agendado. Disponível em Pro/Agency."""
    if not require_feature(user, "video"):
        raise HTTPException(402, "Upload de vídeo está disponível nos planos Pro e Agency")
    post = _own_post(post_id, db, user)
    if post.status not in (PostStatus.draft, PostStatus.approved):
        raise HTTPException(409, "Post não é mais editável")
    if file.content_type not in ALLOWED_VIDEO_MIMES:
        raise HTTPException(415, "Formato não suportado — envie um vídeo MP4")
    account = db.get(LinkedInAccount, post.linkedin_account_id)
    if not account:
        raise HTTPException(404, "Conta LinkedIn do post não encontrada")

    tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    size = 0
    try:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_VIDEO_BYTES:
                raise HTTPException(413, "Vídeo acima do limite de 100 MB")
            tmp.write(chunk)
        tmp.close()
        if size == 0:
            raise HTTPException(400, "Arquivo vazio")
        try:
            token = _ensure_fresh_token(db, account)
        except li.LinkedInError:
            raise HTTPException(409, "Sua conta LinkedIn precisa ser reconectada")
        try:
            init = li.initialize_video_upload(token, account.person_urn, size)
            etags = li.upload_video_parts(token, tmp.name, init["instructions"])
            li.finalize_video_upload(token, init["video_urn"], init["upload_token"], etags)
        except li.LinkedInError as exc:
            raise HTTPException(502, f"LinkedIn recusou o upload do vídeo: {exc}")
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass

    post.video_urn = init["video_urn"]
    post.video_status = "processing"
    post.video_title = (file.filename or "video")[:200]
    db.query(PostImage).filter_by(post_id=post.id).delete()
    _clear_legacy_image(post)
    db.commit()
    return post


@router.delete("/{post_id}/video", response_model=PostOut)
def delete_post_video(
    post_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    post = _own_post(post_id, db, user)
    if post.status not in (PostStatus.draft, PostStatus.approved):
        raise HTTPException(409, "Post não é mais editável")
    _clear_video(post)
    db.commit()
    return post
