"""Model `analytics.report_exports` — khớp database/postgresql/schemas/09_analytics.sql."""

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.common import pg_enum
from app.models.enums import ReportType

SCHEMA = "analytics"


class ReportExport(Base):
    __tablename__ = "report_exports"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("auth.users.id"), nullable=False)
    report_type: Mapped[ReportType] = mapped_column(pg_enum(ReportType, "report_type", SCHEMA), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    media_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("media.media_files.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
