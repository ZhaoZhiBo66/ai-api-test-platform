from app.database.db import Base, engine

# Import models so SQLAlchemy can register metadata before create_all.
from app.models.interface import ApiInterface  # noqa: F401
from app.models.result import TestResult, TestRun  # noqa: F401
from app.models.testcase import TestCase  # noqa: F401


def init_database() -> None:
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    init_database()
    print("database initialized")

