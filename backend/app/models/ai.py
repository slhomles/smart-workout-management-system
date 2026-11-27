"""Model kết quả AI — khớp database/postgresql/schemas/07_ai.sql (schema `ai`).

Không khai ForeignKey tới training/catalog/media: các bảng đó không (hoặc không chắc) có model trong
metadata, SQLAlchemy sẽ lỗi khi sắp thứ tự insert. Ràng buộc vẫn do DB kiểm tra.
"""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Identity, Integer, Numeric, SmallInteger, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.common import pg_enum
from app.models.enums import AnalysisMode, IssueSeverity

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


class PostureIssue(Base):
    """Một lỗi tư thế AI phát hiện trong một lần phân tích."""

    __tablename__ = "posture_issues"
    __table_args__ = {"schema": SCHEMA}

    # GENERATED ALWAYS AS IDENTITY: không được gửi id khi insert.
    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    pose_analysis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai.pose_analyses.id", ondelete="CASCADE"), nullable=False
    )
    mistake_id: Mapped[int] = mapped_column(Integer, nullable=False)
    rep_no: Mapped[int | None] = mapped_column(SmallInteger)
    offset_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    frame_index: Mapped[int | None] = mapped_column(Integer)
    severity: Mapped[IssueSeverity] = mapped_column(
        pg_enum(IssueSeverity, "issue_severity", SCHEMA), nullable=False, server_default=text("'warning'")
    )
    measured_angle_deg: Mapped[float | None] = mapped_column(Numeric(5, 2, asdecimal=False))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=NOW)
