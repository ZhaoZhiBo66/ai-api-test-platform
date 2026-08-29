from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.db import Base
from app.utils.time_utils import utc_now


class TestRun(Base):
    __tablename__ = "test_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    interface_id: Mapped[int | None] = mapped_column(ForeignKey("api_interfaces.id"), nullable=True)
    suite_id: Mapped[int | None] = mapped_column(ForeignKey("test_suites.id"), nullable=True)
    environment_id: Mapped[int | None] = mapped_column(ForeignKey("test_environments.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="running")
    total: Mapped[int] = mapped_column(Integer, default=0)
    passed: Mapped[int] = mapped_column(Integer, default=0)
    failed: Mapped[int] = mapped_column(Integer, default=0)
    ai_summary: Mapped[str] = mapped_column(Text, default="")
    variables: Mapped[dict] = mapped_column(JSON, default=dict)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class TestResult(Base):
    __tablename__ = "test_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("test_runs.id"), nullable=False)
    case_id: Mapped[int] = mapped_column(ForeignKey("test_cases.id"), nullable=False)
    case_name: Mapped[str] = mapped_column(String(150), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    request_data: Mapped[dict] = mapped_column(JSON, default=dict)
    response_data: Mapped[dict] = mapped_column(JSON, default=dict)
    response_headers: Mapped[dict] = mapped_column(JSON, default=dict)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    extracted_variables: Mapped[dict] = mapped_column(JSON, default=dict)
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    assertion_message: Mapped[str] = mapped_column(Text, default="")
    ai_analysis: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

