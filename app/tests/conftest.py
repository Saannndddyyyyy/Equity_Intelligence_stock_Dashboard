import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base, get_db
from app.main import app

import os

# Use a temporary file SQLite database for isolated unit tests
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_temp.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db():
    """
    Creates a fresh database schema for each test function and deletes the file on teardown.
    """
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        # Remove the temp db file
        try:
            if os.path.exists("test_temp.db"):
                os.remove("test_temp.db")
        except Exception:
            pass


@pytest.fixture(scope="function")
def client(db):
    """
    Overrides the database dependency to inject the test database session.
    """

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
