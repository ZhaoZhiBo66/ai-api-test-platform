import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.db import Base, get_db
from main import app


@pytest.fixture
def db_session() -> Session:
    # StaticPool + check_same_thread=False keep every checkout on the one
    # connection that owns the in-memory database; the default pool would hand
    # out a fresh, empty database and lose the tables created here.
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autocommit=False, autoflush=False)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def client(db_session: Session) -> TestClient:
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        # Not a context manager on purpose: that would run the lifespan handler,
        # which builds tables on the real engine and configures file logging.
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
