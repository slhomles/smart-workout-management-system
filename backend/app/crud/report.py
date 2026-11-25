"""Truy vấn analytics.report_exports + media.media_files."""

import uuid
from datetime import date, datetime

from sqlalchemy import select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analytics import ReportExport
from app.models.enums import ReportType
from app.models.media import MediaFile


async def get_report(db: AsyncSession, user_id: uuid.UUID, report_id: uuid.UUID) -> ReportExport | None:
    return await db.scalar(select(ReportExport).where(ReportExport.id == report_id, ReportExport.user_id == user_id))


async def report_exists(db: AsyncSession, user_id: uuid.UUID, report_type: ReportType, period_start: date) -> bool:
    found = await db.scalar(
        select(ReportExport.id).where(
            ReportExport.user_id == user_id,
            ReportExport.report_type == report_type,
            ReportExport.period_start == period_start,
        )
    )
    return found is not None


async def list_reports(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    report_type: ReportType | None,
    after: tuple[datetime, uuid.UUID] | None,
    limit: int,
) -> list[ReportExport]:
    stmt = select(ReportExport).where(ReportExport.user_id == user_id)
    if report_type is not None:
        stmt = stmt.where(ReportExport.report_type == report_type)
    if after is not None:
        stmt = stmt.where(tuple_(ReportExport.created_at, ReportExport.id) < tuple_(*after))
    stmt = stmt.order_by(ReportExport.created_at.desc(), ReportExport.id.desc()).limit(limit)
    return list((await db.scalars(stmt)).all())


async def get_media(db: AsyncSession, media_id: uuid.UUID) -> MediaFile | None:
    return await db.scalar(select(MediaFile).where(MediaFile.id == media_id, MediaFile.deleted_at.is_(None)))
