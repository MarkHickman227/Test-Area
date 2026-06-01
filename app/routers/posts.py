from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.post import ScheduledPost
from app.services.tasks import schedule_linkedin_post

router = APIRouter(prefix="/posts", tags=["posts"])


class PostCreate(BaseModel):
    content: str
    scheduled_at: datetime
    access_token: str
    author_urn: str


class PostResponse(BaseModel):
    id: int
    content: str
    scheduled_at: datetime
    status: str

    model_config = {"from_attributes": True}


@router.post("/schedule", response_model=PostResponse)
async def schedule_post(post: PostCreate, db: Session = Depends(get_db)):
    """Schedule a LinkedIn post for future publishing."""
    db_post = ScheduledPost(
        content=post.content,
        scheduled_at=post.scheduled_at,
        status="pending",
    )
    db.add(db_post)
    db.commit()
    db.refresh(db_post)

    schedule_linkedin_post.apply_async(
        args=[db_post.id, post.access_token, post.author_urn],
        eta=post.scheduled_at,
    )

    return db_post


@router.get("/", response_model=list[PostResponse])
async def list_posts(db: Session = Depends(get_db)):
    """List all scheduled posts."""
    return db.query(ScheduledPost).order_by(ScheduledPost.scheduled_at.desc()).all()


@router.get("/{post_id}", response_model=PostResponse)
async def get_post(post_id: int, db: Session = Depends(get_db)):
    """Get a specific scheduled post."""
    post = db.query(ScheduledPost).filter(ScheduledPost.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return post
