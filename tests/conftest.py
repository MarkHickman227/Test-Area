from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app
from app.models.post import LinkedInAccount
from app.services.session import create_session


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db_session: Session) -> Generator[TestClient, None, None]:
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def authenticated_client(client: TestClient, db_session: Session) -> TestClient:
    account = LinkedInAccount(
        linkedin_member_id="member-123",
        display_name="Test Member",
        author_urn="urn:li:person:member-123",
        access_token="test-access-token",
    )
    db_session.add(account)
    db_session.commit()
    db_session.refresh(account)
    raw_session = create_session(db_session, account)
    client.cookies.set("linkedin_agent_session", raw_session)
    return client
