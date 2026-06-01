import asyncio
import logging

from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.models.post import ScheduledPost
from app.services.linkedin import create_post

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def schedule_linkedin_post(self, post_id: int, access_token: str, author_urn: str):
    """Publish a scheduled post to LinkedIn."""
    db = SessionLocal()
    try:
        post = db.query(ScheduledPost).filter(ScheduledPost.id == post_id).first()
        if not post:
            logger.error("Post %d not found", post_id)
            return

        result = asyncio.run(create_post(access_token, author_urn, post.content))

        post.status = "published"
        post.linkedin_post_id = result.get("id")
        db.commit()
        logger.info("Post %d published successfully", post_id)
    except Exception as exc:
        logger.error("Failed to publish post %d: %s", post_id, exc)
        db.rollback()
        post = db.query(ScheduledPost).filter(ScheduledPost.id == post_id).first()
        if post:
            post.status = "failed"
            db.commit()
        raise self.retry(exc=exc)
    finally:
        db.close()
