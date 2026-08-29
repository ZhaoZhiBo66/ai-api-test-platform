from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.db import Base
from app.utils.time_utils import utc_now


class TestCase(Base):
    __tablename__ = "test_cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    interface_id: Mapped[int] = mapped_column(ForeignKey("api_interfaces.id"), nullable=False)
    case_name: Mapped[str] = mapped_column(String(150), nullable=False)
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    expected_status_code: Mapped[int] = mapped_column(Integer, default=200)
    expected_json: Mapped[dict] = mapped_column(JSON, default=dict)
    sql_check: Mapped[dict] = mapped_column(JSON, default=dict)
    assertions: Mapped[list] = mapped_column(JSON, default=list)
    extractors: Mapped[list] = mapped_column(JSON, default=list)
    dependencies: Mapped[list] = mapped_column(JSON, default=list)
    request_config: Mapped[dict] = mapped_column(JSON, default=dict)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)

