from app.db import get_session_factory
from app.models.user import User
from app.services.credits import (
    capture_credits,
    grant_promotional,
    ledger_balance,
    release_credits,
    reserve_credits,
)
from sqlalchemy import select


def test_reserve_capture_release_zero_drift(client):
    db = get_session_factory()()
    user = db.scalar(select(User).where(User.email == "adult@example.com"))
    assert user
    start = ledger_balance(db, user.id)
    grant_promotional(db, user.id, 10, key="test-grant")
    db.commit()
    assert ledger_balance(db, user.id) == start + 10
    reserve_credits(db, user.id, "job-1", 8)
    db.commit()
    assert ledger_balance(db, user.id) == start + 2
    capture_credits(db, user.id, "job-1", 8)
    db.commit()
    assert ledger_balance(db, user.id) == start + 2
    # A second job that fails before GPU should release
    reserve_credits(db, user.id, "job-2", 2)
    release_credits(db, user.id, "job-2", 2, "JOB_FAILED")
    db.commit()
    assert ledger_balance(db, user.id) == start + 2
    db.close()
