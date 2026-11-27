"""Model kết quả AI — khớp database/postgresql/schemas/07_ai.sql (schema `ai`)."""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Numeric, SmallInteger, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.common import pg_enum
from app.models.enums import AnalysisMode, JobStatus

SCHEMA = "ai"
NOW = text("now()")


class PoseAnalysis(Base):
    """Một lần phân tích tư thế cho một hiệp tập (realtime trên thiết bị hoặc video trên server)."""

    __tablename__ = "pose_analyses"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    set_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    mode: Mapped[AnalysisMode] = mapped_column(pg_enum(AnalysisMode, "analysis_mode", SCHEMA), nullable=False)
    model_name: Mapped[str] = mapped_column(String(50), nullable=False)
    model_version: Mapped[str] = mapped_column(String(50), nullable=False)
    overall_score: Mapped[float | None] = mapped_column(Numeric(5, 2, asdecimal=False))
    correct_form_pct: Mapped[float | None] = mapped_column(Numeric(5, 2, asdecimal=False))
    detected_rep_count: Mapped[int | None] = mapped_column(SmallInteger)
    feedback_summary: Mapped[str | None] = mapped_column(Text)
    keypoints_media_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    analyzed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=NOW)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=NOW)


class VideoAnalysisJob(Base):
    """Vòng đời xử lý video bất đồng bộ (1B): queued → processing → completed/failed."""

    __tablename__ = "video_analysis_jobs"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    pose_analysis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai.pose_analyses.id", ondelete="CASCADE"), nullable=False
    )
    source_video_media_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    result_video_media_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    # Kiểu enum nằm ở schema `util` (util.job_status), không phải `ai`.
    status: Mapped[JobStatus] = mapped_column(
        pg_enum(JobStatus, "job_status", "util"), nullable=False, server_default=text("'queued'")
    )
    priority: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default=text("5"))
    attempt_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default=text("0"))
    max_attempts: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default=text("3"))
    queued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=NOW)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    worker_id: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(Text)
    notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=NOW)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=NOW)
