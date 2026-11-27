"""Nghiệp vụ phục hồi cơ (chức năng 2): Heatmap, lịch sử dự đoán và chạy dự đoán AI cho một buổi tập.

Giá trị phục hồi (%, giờ còn lại, trạng thái) lấy nguyên từ view, không tính lại (doc 05 §2.2).
"""

import logging
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, DataValidationError, NotFoundError, ServiceUnavailableError
from app.crud import recovery as crud
from app.crud import workout as workout_crud
from app.models.enums import SessionStatus
from app.models.training import WorkoutSession
from app.schemas.base import ErrorDetail, Page, build_page, decode_cursor
from app.schemas.recovery import (
    MuscleLoadSchema,
    MuscleRecoveryListQuery,
    MuscleRecoveryStatusResponse,
    PredictRecoveryResponse,
    RecoveryPredictionInput,
    RecoveryPredictionListQuery,
    RecoveryPredictionOutput,
    RecoveryPredictionResponse,
)

# Gọi qua thuộc tính module (không `from … import predict_recovery`) để test monkeypatch được (spec §6 ý 9).
from app.services import recovery_ai_client

logger = logging.getLogger("app.recovery")

_INVALID_CURSOR = ErrorDetail(field="cursor", message="Cursor không hợp lệ", code="invalid_cursor")
# Khoảng giá trị của catalog.muscle_groups.id (smallint); ngoài khoảng này cursor chắc chắn bị sửa tay.
_MUSCLE_GROUP_ID_MAX = 32767


def _muscle_group_id_of(values: dict[str, Any]) -> int:
    """`muscle_group_id` của cursor phải là int thật (bool cũng là int trong Python nên loại riêng)."""
    value = values["muscle_group_id"]
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= _MUSCLE_GROUP_ID_MAX:
        raise ValueError("muscle_group_id")
    return value


def _decode_muscle_cursor(cursor: str | None) -> int | None:
    """Cursor dạng {"muscle_group_id": n} cho sắp xếp `muscle_group_id ASC`."""
    if cursor is None:
        return None
    try:
        return _muscle_group_id_of(decode_cursor(cursor))
    except (KeyError, ValueError):
        raise DataValidationError([_INVALID_CURSOR]) from None


def _decode_prediction_cursor(cursor: str | None) -> crud.PredictionPosition | None:
    """Cursor dạng {"trained_at": ISO có múi giờ, "session_id": uuid, "muscle_group_id": n}."""
    if cursor is None:
        return None
    values = decode_cursor(cursor)
    try:
        trained_at = datetime.fromisoformat(values["trained_at"])
        session_id = uuid.UUID(values["session_id"])
        muscle_group_id = _muscle_group_id_of(values)
    except (KeyError, ValueError, TypeError, AttributeError):
        raise DataValidationError([_INVALID_CURSOR]) from None
    # So với cột timestamptz, mốc không có múi giờ sẽ bị hiểu theo giờ máy chủ: coi là cursor hỏng.
    if trained_at.tzinfo is None:
        raise DataValidationError([_INVALID_CURSOR])
    return trained_at, session_id, muscle_group_id


async def list_muscle_recovery(
    db: AsyncSession, user_id: uuid.UUID, query: MuscleRecoveryListQuery
) -> Page[MuscleRecoveryStatusResponse]:
    """Trang Heatmap của chính user: mọi nhóm cơ có `heatmap_region_key`, lọc `recovery_status`."""
    rows = await crud.list_muscle_recovery(db, user_id, query, _decode_muscle_cursor(query.cursor))
    return build_page(
        rows,
        query.limit,
        to_item=lambda row: MuscleRecoveryStatusResponse.model_validate(dict(row)),
        cursor_of=lambda row: {"muscle_group_id": row["muscle_group_id"]},
    )


async def list_predictions(
    db: AsyncSession, user_id: uuid.UUID, query: RecoveryPredictionListQuery
) -> Page[RecoveryPredictionResponse]:
    """Lịch sử dự đoán của chính user (bản mới nhất mỗi buổi × nhóm cơ), buổi tập gần nhất trước."""
    rows = await crud.list_prediction_history(db, user_id, query, _decode_prediction_cursor(query.cursor))
    return build_page(
        rows,
        query.limit,
        to_item=lambda row: RecoveryPredictionResponse.model_validate(dict(row)),
        cursor_of=lambda row: {
            "trained_at": row["trained_at"].isoformat(),
            "session_id": str(row["session_id"]),
            "muscle_group_id": row["muscle_group_id"],
        },
    )


async def _owned_finished_session(db: AsyncSession, user_id: uuid.UUID, session_id: uuid.UUID) -> WorkoutSession:
    """Buổi của chính user, chưa xoá và đã kết thúc (buổi đang tập chưa có tải cuối cùng để dự đoán)."""
    session = await workout_crud.get_session(db, user_id, session_id)
    if session is None:
        raise NotFoundError("workout_session_not_found", "Không tìm thấy buổi tập")
    if session.status == SessionStatus.IN_PROGRESS:
        raise ConflictError("conflict", "Buổi tập chưa kết thúc, chưa thể dự đoán phục hồi")
    return session


def _ensure_known_muscles(output: RecoveryPredictionOutput, loaded_ids: set[int]) -> None:
    """AI chỉ được trả nhóm cơ có trong tải đã gửi, mỗi nhóm một lần; sai thì coi là trả sai hợp đồng."""
    returned_ids = [prediction.muscle_group_id for prediction in output.predictions]
    if len(set(returned_ids)) != len(returned_ids) or not set(returned_ids) <= loaded_ids:
        raise recovery_ai_client.RecoveryServiceError("invalid_response")


async def _request_predictions(payload: RecoveryPredictionInput) -> RecoveryPredictionOutput:
    """Gọi AI và kiểm tra kết quả; mọi lỗi AI thành 503 `service_unavailable` (chi tiết chỉ ghi log server)."""
    try:
        output = await recovery_ai_client.predict_recovery(payload)
        _ensure_known_muscles(output, {load.muscle_group_id for load in payload.muscle_loads})
    except recovery_ai_client.RecoveryServiceError as err:
        logger.warning("recovery prediction failed: reason=%s session_id=%s", err.reason, payload.session_id)
        raise ServiceUnavailableError(
            "Không thể dự đoán phục hồi lúc này, vui lòng thử lại sau",
            [ErrorDetail(field="ai_service", message="Dịch vụ dự đoán phục hồi tạm thời không khả dụng", code=err.reason)],
        ) from None
    return output


async def predict_for_session(
    db: AsyncSession, user_id: uuid.UUID, session_id: uuid.UUID
) -> PredictRecoveryResponse:
    """Dự đoán phục hồi cho một buổi đã kết thúc của user rồi upsert vào training.recovery_predictions.

    Buổi không có hiệp tính tải thì trả danh sách rỗng và không gọi AI. Lỗi AI → 503, không ghi gì.
    """
    session = await _owned_finished_session(db, user_id, session_id)
    loads = await crud.list_session_muscle_loads(db, session_id)
    if not loads:
        return PredictRecoveryResponse(session_id=session_id, model_version=None, predictions=[])
    payload = RecoveryPredictionInput(
        session_id=session_id,
        user_id=user_id,
        trained_at=session.ended_at or session.started_at,
        muscle_loads=[MuscleLoadSchema.model_validate(dict(row)) for row in loads],
    )
    output = await _request_predictions(payload)
    await crud.upsert_predictions(db, session_id, output)
    await db.commit()
    rows = await crud.list_session_predictions(db, session_id, output.model_version)
    return PredictRecoveryResponse(
        session_id=session_id,
        model_version=output.model_version,
        predictions=[RecoveryPredictionResponse.model_validate(dict(row)) for row in rows],
    )
