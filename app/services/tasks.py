import asyncio
import logging
from datetime import datetime, timedelta, timezone

from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.models.post import LinkedInAccount, ScheduledPost
from app.services.linkedin import create_post, refresh_access_token

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def schedule_linkedin_post(self, post_id: int):
    """Publish a scheduled post to LinkedIn."""
    db = SessionLocal()
    try:
        post = db.query(ScheduledPost).filter(ScheduledPost.id == post_id).first()
        if not post:
            logger.error("Post %d not found", post_id)
            return
        if post.status not in {"pending", "retrying"}:
            logger.info("Post %d skipped because status is %s", post_id, post.status)
            return

        account = db.query(LinkedInAccount).filter(LinkedInAccount.id == post.account_id).first()
        if not account:
            raise RuntimeError(f"LinkedIn account for post {post_id} was not found")

        access_token = asyncio.run(resolve_access_token(account))
        result = asyncio.run(create_post(access_token, account.author_urn, post.content))

        post.status = "published"
        post.linkedin_post_id = result.get("id")
        post.error_message = None
        db.commit()
        logger.info("Post %d published successfully", post_id)
    except Exception as exc:
        logger.error("Failed to publish post %d: %s", post_id, exc)
        db.rollback()
        post = db.query(ScheduledPost).filter(ScheduledPost.id == post_id).first()
        if post:
            post.error_message = str(exc)
            post.status = "failed" if self.request.retries >= self.max_retries else "retrying"
            db.commit()
        countdown = min(60 * (2 ** self.request.retries), 900)
        raise self.retry(exc=exc, countdown=countdown)
    finally:
        db.close()


async def resolve_access_token(account: LinkedInAccount) -> str:
    if not token_needs_refresh(account.token_expires_at):
        return account.access_token
    if not account.refresh_token:
        raise RuntimeError("LinkedIn access token expired and no refresh token is available")

    token_data = await refresh_access_token(account.refresh_token)
    access_token = token_data.get("access_token")
    if not access_token:
        raise RuntimeError("LinkedIn did not return an access token during refresh")

    account.access_token = access_token
    account.refresh_token = token_data.get("refresh_token") or account.refresh_token
    expires_in = token_data.get("expires_in")
    if isinstance(expires_in, int):
        account.token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    return access_token


def token_needs_refresh(expires_at: datetime | None) -> bool:
    if expires_at is None:
        return False
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at <= datetime.now(timezone.utc) + timedelta(minutes=5)
