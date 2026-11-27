"""Nghiệp vụ /scheduled-workouts (chức năng 2: xếp lịch tập).

"Đã hoàn thành" không phải một `ScheduleStatus`: suy ra từ buổi tập gắn với lịch (doc 05 §2.3).
"""

import uuid
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DataValidationError
from app.crud import body as body_crud
from app.crud import recovery as recovery_crud
from app.crud import schedule as crud
from app.schemas.base import ErrorDetail, Page, build_page, decode_cursor
from app.schemas.schedule import (
    CreateScheduledWorkoutRequest,
    ScheduledPlanDaySchema,
    ScheduledWorkoutListQuery,
    ScheduledWorkoutResponse,
)

# Một message cho mọi lý do (không tồn tại, của user khác, mẫu nháp, lưu trữ, đã xoá) để không lộ dữ liệu.
_INVALID_PLAN_DAY = "Buổi giáo án không tồn tại hoặc không dùng được"
_INVALID_CURSOR = ErrorDetail(field="cursor", message="Cursor không hợp lệ", code="invalid_cursor")


def _decode_schedule_cursor(cursor: str | None) -> tuple[date, uuid.UUID] | None:
    """Cursor dạng {"scheduled_date": "YYYY-MM-DD", "id": "<uuid>"} cho sắp xếp (scheduled_date, id) ASC."""
    if cursor is None:
        return None
    values = decode_cursor(cursor)
    try:
        return date.fromisoformat(values["scheduled_date"]), uuid.UUID(values["id"])
    # AttributeError: uuid.UUID() với giá trị không phải chuỗi (vd số nguyên) trong cursor do client sửa.
    except (KeyError, ValueError, TypeError, AttributeError):
        raise DataValidationError([_INVALID_CURSOR]) from None


def _schedule_response(row: Any) -> ScheduledWorkoutResponse:
    plan_day = None
    if row["plan_day_id"] is not None:
        plan_day = ScheduledPlanDaySchema(
            id=row["plan_day_id"],
            plan_id=row["plan_id"],
            plan_name=row["plan_name"],
            day_no=row["day_no"],
            name=row["plan_day_name"],
        )
    return ScheduledWorkoutResponse(
        id=row["id"],
        scheduled_date=row["scheduled_date"],
        title=row["title"],
        notes=row["notes"],
        status=row["status"],
        plan_day=plan_day,
        recovery_warning_ack_at=row["recovery_warning_ack_at"],
        workout_session_id=row["workout_session_id"],
        is_completed=row["is_completed"],
        created_at=row["created_at"],
    )


async def list_schedules(
    db: AsyncSession, user_id: uuid.UUID, query: ScheduledWorkoutListQuery
) -> Page[ScheduledWorkoutResponse]:
    """Trang lịch tập của chính user, ngày sớm trước; lọc `from`/`to` (tính cả hai đầu), `status`."""
    if query.from_date is not None and query.to_date is not None and query.from_date > query.to_date:
        raise DataValidationError([ErrorDetail(field="to", message="`to` phải không trước `from`", code="value_error")])
    rows = await crud.list_schedule_rows(db, user_id, query, _decode_schedule_cursor(query.cursor))
    return build_page(
        rows,
        query.limit,
        to_item=_schedule_response,
        cursor_of=lambda row: {"scheduled_date": row["scheduled_date"].isoformat(), "id": str(row["id"])},
    )


async def _validation_errors(
    db: AsyncSession, user_id: uuid.UUID, req: CreateScheduledWorkoutRequest
) -> list[ErrorDetail]:
    """Bước 2–4 của spec §6 ý 5; báo đủ mọi lỗi theo đúng thứ tự kiểm tra."""
    errors = []
    # Khớp ck_scheduled_workouts_has_content; title đã strip, rỗng thành None ở schema.
    if req.plan_day_id is None and req.title is None:
        errors.append(ErrorDetail(field="plan_day_id", message="Cần chọn buổi giáo án hoặc nhập tiêu đề", code="missing"))
    today = await body_crud.local_today(db, await body_crud.get_user_timezone(db, user_id))
    if req.scheduled_date < today:
        errors.append(
            ErrorDetail(field="scheduled_date", message="Không xếp lịch vào ngày đã qua", code="value_error")
        )
    # Kiểm tra trước khi ghi: trigger trg_scheduled_workouts_plan_access ném check_violation không có
    # tên constraint, handler IntegrityError sẽ dịch thành 409 thay vì 422.
    if req.plan_day_id is not None and not await crud.can_schedule_plan_day(db, user_id, req.plan_day_id):
        errors.append(ErrorDetail(field="plan_day_id", message=_INVALID_PLAN_DAY, code="invalid_reference"))
    return errors


def _not_recovered_detail(row: Any) -> ErrorDetail:
    recovered_at = row["recovered_at"].astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
    return ErrorDetail(
        field="acknowledge_recovery_warning",
        message=f"{row['muscle_name']} chưa hồi phục, dự kiến hồi phục lúc {recovered_at}",
        code="muscle_not_recovered",
    )


async def _recovery_ack_at(
    db: AsyncSession, user_id: uuid.UUID, req: CreateScheduledWorkoutRequest
) -> datetime | None:
    """Bước 5 (spec §6 ý 6): chặn nếu nhóm cơ đích chưa hồi phục mà user chưa xác nhận.

    Trả thời điểm xác nhận để ghi `recovery_warning_ack_at`; None khi không có gì để xác nhận
    (buổi tự do, hoặc mọi nhóm cơ đích đã hồi phục) dù client gửi `true`.
    """
    if req.plan_day_id is None:
        return None
    tz = await body_crud.get_user_timezone(db, user_id)
    unrecovered = await recovery_crud.list_unrecovered_target_muscles(db, user_id, req, tz)
    if not unrecovered:
        return None
    if not req.acknowledge_recovery_warning:
        raise DataValidationError([_not_recovered_detail(row) for row in unrecovered])
    # Giờ của DB (không phải giờ máy app) để cùng nguồn với now() mà view phục hồi dùng.
    return await body_crud.db_now(db)


async def create_schedule(
    db: AsyncSession, user_id: uuid.UUID, req: CreateScheduledWorkoutRequest
) -> ScheduledWorkoutResponse:
    """Xếp một lịch tập cho chính user; mọi kiểm tra chạy trước khi ghi, commit đúng một lần.

    Lỗi bước 2–4 được báo trước, khi đó không chạy kiểm tra phục hồi (spec §6 ý 5).
    """
    errors = await _validation_errors(db, user_id, req)
    if errors:
        raise DataValidationError(errors)
    recovery_warning_ack_at = await _recovery_ack_at(db, user_id, req)
    schedule_id = await crud.create_schedule(db, user_id, req, recovery_warning_ack_at)
    await db.commit()
    return _schedule_response(await crud.get_schedule_row(db, user_id, schedule_id))
