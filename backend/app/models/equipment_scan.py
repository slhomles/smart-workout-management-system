"""Model nhận diện thiết bị (chức năng 7) — khớp database/postgresql/schemas/07_ai.sql."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.common import pg_enum
from app.models.enums import ScanFeedback

SCHEMA = "ai"
NOW = text("now()")


class EquipmentScan(Base):
    """Một lần user quét thiết bị bằng camera (ai.equipment_scans)."""

    __tablename__ = "equipment_scans"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("auth.users.id", ondelete="CASCADE"), nullable=False
    )
    image_media_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("media.media_files.id", ondelete="SET NULL")
    )
    model_name: Mapped[str] = mapped_column(String(50), nullable=False)
    model_version: Mapped[str] = mapped_column(String(50), nullable=False)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    scanned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=NOW)
    feedback: Mapped[ScanFeedback | None] = mapped_column(pg_enum(ScanFeedback, "scan_feedback", SCHEMA))
    feedback_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # FK catalog.equipment có trong DB; không khai ForeignKey vì metadata chưa có model catalog
    # (cùng cách training.SessionExercise.exercise_id).
    corrected_equipment_id: Mapped[int | None] = mapped_column(Integer)


class EquipmentScanPrediction(Base):
    """Một dự đoán (thiết bị + độ tin cậy) của một lần quét (ai.equipment_scan_predictions)."""

    __tablename__ = "equipment_scan_predictions"
    __table_args__ = {"schema": SCHEMA}

    scan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai.equipment_scans.id", ondelete="CASCADE"), primary_key=True
    )
    # FK catalog.equipment (ON DELETE RESTRICT) có trong DB; xem ghi chú ở corrected_equipment_id.
    equipment_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    confidence: Mapped[float] = mapped_column(Numeric(5, 4, asdecimal=False), nullable=False)
