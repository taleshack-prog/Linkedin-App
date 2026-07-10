import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Post, PostStatus, User
from app.schemas import PostApprove, PostOut, PostUpdate
from app.security import get_current_user

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
    user: User = Depends(get_current_user),
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
