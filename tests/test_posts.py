from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.models.post import ScheduledPost
from app.routers.posts import schedule_linkedin_post


def test_posts_require_authentication(client: TestClient):
    response = client.get("/posts/")

    assert response.status_code == 401


def test_schedule_post_for_authenticated_account(
    authenticated_client: TestClient,
    monkeypatch,
):
    calls = []

    def fake_apply_async(args, eta):
        calls.append({"args": args, "eta": eta})

    monkeypatch.setattr(schedule_linkedin_post, "apply_async", fake_apply_async)
    scheduled_at = datetime.now(timezone.utc) + timedelta(minutes=10)

    response = authenticated_client.post(
        "/posts/schedule",
        json={
            "content": "A useful LinkedIn update.",
            "scheduled_at": scheduled_at.isoformat(),
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["content"] == "A useful LinkedIn update."
    assert body["status"] == "pending"
    assert calls == [{"args": [body["id"]], "eta": scheduled_at}]


def test_schedule_rejects_past_dates(authenticated_client: TestClient):
    scheduled_at = datetime.now(timezone.utc) - timedelta(minutes=10)

    response = authenticated_client.post(
        "/posts/schedule",
        json={
            "content": "This should fail.",
            "scheduled_at": scheduled_at.isoformat(),
        },
    )

    assert response.status_code == 422


def test_cancel_pending_post(authenticated_client: TestClient, db_session):
    post = ScheduledPost(
        account_id=1,
        content="Cancel me.",
        scheduled_at=datetime.now(timezone.utc) + timedelta(minutes=10),
        status="pending",
    )
    db_session.add(post)
    db_session.commit()
    db_session.refresh(post)

    response = authenticated_client.post(f"/posts/{post.id}/cancel")

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
