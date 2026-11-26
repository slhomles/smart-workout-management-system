"""
Nghiệp vụ /reports: tổng hợp số liệu kỳ (từ view), vẽ thẻ PNG, lưu Object Storage,
ghi media.media_files + analytics.report_exports (chức năng 3, bước 5).
"""

import uuid
from datetime import date, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core.exceptions import ConflictError, DataValidationError, NotFoundError
from app.crud import auth as auth_crud
from app.crud import body as body_crud
from app.crud import dashboard as dashboard_crud
from app.crud import report as crud
from app.models.analytics import ReportExport
from app.models.enums import MediaStatus, ReportType
from app.models.media import MediaFile
from app.schemas.base import ErrorDetail, Page, build_page, decode_keyset_cursor
from app.schemas.report import CreateReportExportRequest, ReportExportResponse, ReportSummarySchema
from app.services import storage_service
from app.utils.report_card import CardStat, render_report_card

PNG = "image/png"


def period_end(report_type: ReportType, start: date) -> date:
    if report_type == ReportType.WEEKLY_SUMMARY:
        return start + timedelta(days=7)
    return date(start.year + start.month // 12, start.month % 12 + 1, 1)


def image_url(report_id: uuid.UUID) -> str:
    return f"/api/v1/reports/{report_id}/image"


async def _summary(db: AsyncSession, user_id: uuid.UUID, tz: str, start: date, end: date) -> ReportSummarySchema:
    s = await dashboard_crud.session_totals(db, user_id, tz, start, end)
    a = await dashboard_crud.adherence(db, user_id, start, end)
    w = await dashboard_crud.weight_in_period(db, user_id, tz, start, end)
    return ReportSummarySchema(
        sessions_completed=s["sessions_completed"],
        duration_minutes=s["duration_minutes"],
        total_volume_kg=s["total_volume_kg"],
        est_calories_burned_kcal=s["est_calories_kcal"],
        completed_set_count=s["completed_set_count"],
        total_reps=s["total_reps"],
        planned_count=a["planned_count"],
        completed_planned_count=a["completed_count"],
        adherence_pct=a["adherence_pct"],
        avg_weight_kg=w["avg_weight_kg"],
        weight_change_kg=w["weight_change_kg"],
    )


def _response(report: ReportExport, summary: ReportSummarySchema) -> ReportExportResponse:
    return ReportExportResponse(
        id=report.id,
        report_type=report.report_type,
        period_start=report.period_start,
        period_end=period_end(report.report_type, report.period_start),
        media_id=report.media_id,
        image_url=image_url(report.id),
        summary=summary,
        created_at=report.created_at,
    )


def _card_stats(summary: ReportSummarySchema) -> list[CardStat]:
    vi_separators = str.maketrans({",": ".", ".": ","})  # 1,234.5 → 1.234,5

    def num(value: float | None, unit: str, digits: int = 1, sign: str = "") -> str:
        return "—" if value is None else f"{value:{sign},.{digits}f}".translate(vi_separators) + f" {unit}"

    adherence = "—" if summary.adherence_pct is None else f"{summary.adherence_pct:.0f}%"
    change_text = num(summary.weight_change_kg, "kg", sign="+")
    return [
        CardStat("Buổi tập hoàn thành", f"{summary.sessions_completed} buổi · {num(summary.duration_minutes, 'phút', 0)}"),
        CardStat("Tổng khối lượng (Volume)", num(summary.total_volume_kg, "kg", 0)),
        CardStat("Calo tiêu hao ước tính", num(summary.est_calories_burned_kcal, "kcal", 0)),
        CardStat("Tuân thủ lịch tập", f"{adherence} ({summary.completed_planned_count}/{summary.planned_count})"),
        CardStat("Cân nặng trung bình", num(summary.avg_weight_kg, "kg")),
        CardStat("Thay đổi cân nặng", change_text),
    ]


async def create_report(db: AsyncSession, user_id: uuid.UUID, req: CreateReportExportRequest) -> ReportExportResponse:
    if req.report_type == ReportType.WEEKLY_SUMMARY and req.period_start.isoweekday() != 1:
        raise DataValidationError(
            [ErrorDetail(field="period_start", message="Báo cáo tuần phải bắt đầu vào thứ Hai", code="value_error")]
        )
    if req.report_type == ReportType.MONTHLY_SUMMARY and req.period_start.day != 1:
        raise DataValidationError(
            [ErrorDetail(field="period_start", message="Báo cáo tháng phải bắt đầu ngày 1", code="value_error")]
        )
    tz = await body_crud.get_user_timezone(db, user_id)
    if req.period_start > await body_crud.local_today(db, tz):
        raise DataValidationError(
            [ErrorDetail(field="period_start", message="Kỳ báo cáo chưa bắt đầu", code="value_error")]
        )
    if await crud.report_exists(db, user_id, req.report_type, req.period_start):
        raise ConflictError("report_already_exists", "Đã xuất báo cáo cho kỳ này")

    end = period_end(req.report_type, req.period_start)
    summary = await _summary(db, user_id, tz, req.period_start, end)
    profile = await auth_crud.get_profile(db, user_id)
    is_weekly = req.report_type == ReportType.WEEKLY_SUMMARY
    last_day = end - timedelta(days=1)
    png = await run_in_threadpool(
        render_report_card,
        "Báo cáo tuần" if is_weekly else "Báo cáo tháng",
        f"{req.period_start:%d/%m/%Y} – {last_day:%d/%m/%Y}",
        profile.display_name if profile else "",
        _card_stats(summary),
        "Xuất từ Smart Workout AI",
    )

    kind = "weekly" if is_weekly else "monthly"
    stored = await storage_service.put_object(
        f"users/{user_id}/reports/{kind}-{req.period_start.isoformat()}-{uuid.uuid4().hex[:8]}.png", png, PNG
    )
    media = MediaFile(
        uploaded_by_user_id=user_id,
        storage_provider=stored.provider,
        bucket=stored.bucket,
        object_key=stored.object_key,
        original_filename=f"{kind}-report-{req.period_start.isoformat()}.png",
        mime_type=PNG,
        size_bytes=stored.size_bytes,
        checksum_sha256=stored.checksum_sha256,
        width_px=1080,
        height_px=1920,
        status=MediaStatus.AVAILABLE,
    )
    db.add(media)
    await db.flush()
    report = ReportExport(user_id=user_id, report_type=req.report_type, period_start=req.period_start, media_id=media.id)
    db.add(report)
    await db.commit()
    await db.refresh(report)
    return _response(report, summary)


async def get_report(db: AsyncSession, user_id: uuid.UUID, report_id: uuid.UUID) -> ReportExportResponse:
    report = await crud.get_report(db, user_id, report_id)
    if report is None:
        raise NotFoundError("report_not_found", "Không tìm thấy báo cáo")
    tz = await body_crud.get_user_timezone(db, user_id)
    summary = await _summary(db, user_id, tz, report.period_start, period_end(report.report_type, report.period_start))
    return _response(report, summary)


async def list_reports(
    db: AsyncSession, user_id: uuid.UUID, *, report_type: ReportType | None, limit: int, cursor: str | None
) -> Page[ReportExportResponse]:
    reports = await crud.list_reports(
        db, user_id, report_type=report_type, after=decode_keyset_cursor(cursor, "created_at"), limit=limit + 1
    )
    tz = await body_crud.get_user_timezone(db, user_id)
    responses = {}
    for r in reports[:limit]:
        summary = await _summary(db, user_id, tz, r.period_start, period_end(r.report_type, r.period_start))
        responses[r.id] = _response(r, summary)
    return build_page(
        reports,
        limit,
        to_item=lambda r: responses[r.id],
        cursor_of=lambda r: {"created_at": r.created_at.isoformat(), "id": str(r.id)},
    )


async def get_report_image(db: AsyncSession, user_id: uuid.UUID, report_id: uuid.UUID) -> tuple[bytes, str]:
    report = await crud.get_report(db, user_id, report_id)
    if report is None:
        raise NotFoundError("report_not_found", "Không tìm thấy báo cáo")
    media = await crud.get_media(db, report.media_id)
    missing = NotFoundError("report_not_found", "Ảnh báo cáo không còn trên kho lưu trữ")
    if media is None or media.status != MediaStatus.AVAILABLE:
        raise missing
    data = await storage_service.read_object(media.bucket, media.object_key)
    if data is None:
        raise missing
    return data, media.mime_type
