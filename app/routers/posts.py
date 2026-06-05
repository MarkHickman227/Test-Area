from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.post import LinkedInAccount, ScheduledPost
from app.services.session import get_current_account
from app.services.tasks import schedule_linkedin_post

router = APIRouter(prefix="/posts", tags=["posts"])


class PostCreate(BaseModel):
    content: str = Field(min_length=1, max_length=3000)
    scheduled_at: datetime

    @field_validator("scheduled_at")
    @classmethod
    def scheduled_at_must_be_future(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        value = value.astimezone(timezone.utc)
        if value <= datetime.now(timezone.utc):
            raise ValueError("scheduled_at must be in the future")
        return value


class PostResponse(BaseModel):
    id: int
    content: str
    scheduled_at: datetime
    status: str
    linkedin_post_id: str | None = None
    error_message: str | None = None

    model_config = {"from_attributes": True}


@router.post("/schedule", response_model=PostResponse)
async def schedule_post(
    post: PostCreate,
    account: LinkedInAccount = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    """Schedule a LinkedIn post for future publishing."""
    db_post = ScheduledPost(
        account_id=account.id,
        content=post.content,
        scheduled_at=post.scheduled_at,
        status="pending",
    )
    db.add(db_post)
    db.commit()
    db.refresh(db_post)

    schedule_linkedin_post.apply_async(
        args=[db_post.id],
        eta=post.scheduled_at,
    )

    return db_post


@router.get("/", response_model=list[PostResponse])
async def list_posts(
    account: LinkedInAccount = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    """List all scheduled posts."""
    return (
        db.query(ScheduledPost)
        .filter(ScheduledPost.account_id == account.id)
        .order_by(ScheduledPost.scheduled_at.desc())
        .all()
    )


@router.get("/{post_id}", response_model=PostResponse)
async def get_post(
    post_id: int,
    account: LinkedInAccount = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    """Get a specific scheduled post."""
    post = (
        db.query(ScheduledPost)
        .filter(ScheduledPost.id == post_id, ScheduledPost.account_id == account.id)
        .first()
    )
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return post


@router.post("/{post_id}/cancel", response_model=PostResponse)
async def cancel_post(
    post_id: int,
    account: LinkedInAccount = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    """Cancel a pending scheduled post."""
    post = (
        db.query(ScheduledPost)
        .filter(ScheduledPost.id == post_id, ScheduledPost.account_id == account.id)
        .first()
    )
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if post.status != "pending":
        raise HTTPException(status_code=400, detail="Only pending posts can be cancelled")

    post.status = "cancelled"
    db.commit()
    db.refresh(post)
    return post
