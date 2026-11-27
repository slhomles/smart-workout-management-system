"""Endpoint /workout-sessions (chức năng 6): buổi tập, bài trong buổi, hiệp, rep events và tempo."""

import uuid

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUser, require_permission
from app.models.enums import SessionStatus
from app.schemas.base import ERROR_RESPONSES, Page
from app.schemas.recovery import PredictRecoveryResponse
from app.schemas.workout import (
    AddSessionExerciseRequest,
    CreateExerciseSetRequest,
    CreateWorkoutSessionRequest,
    ExerciseSetDetailResponse,
    FinishWorkoutSessionRequest,
    SessionExerciseResponse,
    UpdateExerciseSetRequest,
    WorkoutSessionResponse,
    WorkoutSessionSummaryResponse,
)
from app.services import recovery_service, workout_service

router = APIRouter(prefix="/workout-sessions", tags=["Workouts"])

OWN = require_permission("workout", "manage_own")
PERM = "Quyền: `workout:manage_own`; chỉ thao tác trên buổi tập của chính mình (của người khác → 404)."
SET_PATH = "/{session_id}/exercises/{session_exercise_id}/sets"


# --- Buổi tập ---
@router.get(
    "",
    response_model=Page[WorkoutSessionSummaryResponse],
    responses=ERROR_RESPONSES,
    summary="Danh sách buổi tập (mới nhất trước)",
    description=PERM + " Lọc `status`. Thời lượng, volume, calo lấy từ `training.v_session_summary`.",
)
async def list_sessions(
    status: SessionStatus | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    cursor: str | None = Query(None),
    current: CurrentUser = Depends(OWN),
    db: AsyncSession = Depends(get_db),
) -> Page[WorkoutSessionSummaryResponse]:
    return await workout_service.list_sessions(db, current.id, status=status, limit=limit, cursor=cursor)


@router.post(
    "",
    response_model=WorkoutSessionResponse,
    status_code=201,
    responses=ERROR_RESPONSES,
    summary="Bắt đầu buổi tập mới",
    description=PERM + " Mỗi user tối đa 1 buổi `in_progress` → 409 `session_already_in_progress`.",
)
async def start_session(
    body: CreateWorkoutSessionRequest,
    response: Response,
    current: CurrentUser = Depends(OWN),
    db: AsyncSession = Depends(get_db),
) -> WorkoutSessionResponse:
    result = await workout_service.start_session(db, current.id, body)
    response.headers["Location"] = f"/api/v1/workout-sessions/{result.id}"
    return result


@router.get(
    "/{session_id}",
    response_model=WorkoutSessionResponse,
    responses=ERROR_RESPONSES,
    summary="Chi tiết buổi tập (bài, hiệp, tempo)",
    description=PERM + " Không có/đã xoá → 404 `workout_session_not_found`.",
)
async def get_session(
    session_id: uuid.UUID, current: CurrentUser = Depends(OWN), db: AsyncSession = Depends(get_db)
) -> WorkoutSessionResponse:
    return await workout_service.get_session(db, current.id, session_id)


@router.post(
    "/{session_id}/finish",
    response_model=WorkoutSessionResponse,
    status_code=200,
    responses=ERROR_RESPONSES,
    summary="Kết thúc buổi tập",
    description=PERM + " `status`: completed (mặc định) | abandoned. Buổi đã kết thúc → 409 `session_not_in_progress`.",
)
async def finish_session(
    session_id: uuid.UUID,
    body: FinishWorkoutSessionRequest,
    current: CurrentUser = Depends(OWN),
    db: AsyncSession = Depends(get_db),
) -> WorkoutSessionResponse:
    return await workout_service.finish_session(db, current.id, session_id, body)


@router.post(
    "/{session_id}/predict-recovery",
    response_model=PredictRecoveryResponse,
    status_code=200,
    responses=ERROR_RESPONSES,
    summary="Dự đoán phục hồi cơ sau buổi tập",
    description=(
        PERM + " Lấy tải theo nhóm cơ (`training.v_session_muscle_load`), gọi AI dự đoán rồi ghi/ghi đè "
        "`training.recovery_predictions` theo `model_version`. Buổi không có hiệp tính tải → `predictions: []`, "
        "`model_version: null`. Buổi còn `in_progress` → 409 `conflict`; AI lỗi → 503 `service_unavailable`."
    ),
)
async def predict_recovery(
    session_id: uuid.UUID, current: CurrentUser = Depends(OWN), db: AsyncSession = Depends(get_db)
) -> PredictRecoveryResponse:
    return await recovery_service.predict_for_session(db, current.id, session_id)


# --- Bài trong buổi ---
@router.post(
    "/{session_id}/exercises",
    response_model=SessionExerciseResponse,
    status_code=201,
    responses=ERROR_RESPONSES,
    summary="Thêm bài tập vào buổi đang tập",
    description=PERM + " Bài chưa xuất bản/không tồn tại → 404 `exercise_not_found`; buổi đã kết thúc → 409.",
)
async def add_exercise(
    session_id: uuid.UUID,
    body: AddSessionExerciseRequest,
    response: Response,
    current: CurrentUser = Depends(OWN),
    db: AsyncSession = Depends(get_db),
) -> SessionExerciseResponse:
    result = await workout_service.add_exercise(db, current.id, session_id, body)
    response.headers["Location"] = f"/api/v1/workout-sessions/{session_id}/exercises/{result.id}"
    return result


# --- Hiệp (set/rep/tempo) ---
@router.post(
    SET_PATH,
    response_model=ExerciseSetDetailResponse,
    status_code=201,
    responses=ERROR_RESPONSES,
    summary="Ghi một hiệp (kèm rep events từ AutoTracker)",
    description=(
        PERM + " Hiệp AI (`source` ≠ manual) cần thêm `ai:use`. Gửi `rep_events` (FSM trên thiết bị) "
        "→ server lưu từng rep, tự điền `reps` = số rep nếu bỏ trống, trả `tempo` trung bình & TUT."
    ),
)
async def create_set(
    session_id: uuid.UUID,
    session_exercise_id: uuid.UUID,
    body: CreateExerciseSetRequest,
    response: Response,
    current: CurrentUser = Depends(OWN),
    db: AsyncSession = Depends(get_db),
) -> ExerciseSetDetailResponse:
    result = await workout_service.create_set(db, current.id, session_id, session_exercise_id, body)
    response.headers["Location"] = f"/api/v1/workout-sessions/{session_id}/exercises/{session_exercise_id}/sets/{result.id}"
    return result


@router.get(
    SET_PATH + "/{set_id}",
    response_model=ExerciseSetDetailResponse,
    responses=ERROR_RESPONSES,
    summary="Chi tiết hiệp kèm từng rep và tempo",
    description=PERM + " Không có → 404 `exercise_set_not_found`.",
)
async def get_set(
    session_id: uuid.UUID,
    session_exercise_id: uuid.UUID,
    set_id: int,
    current: CurrentUser = Depends(OWN),
    db: AsyncSession = Depends(get_db),
) -> ExerciseSetDetailResponse:
    return await workout_service.get_set(db, current.id, session_id, session_exercise_id, set_id)


@router.patch(
    SET_PATH + "/{set_id}",
    response_model=ExerciseSetDetailResponse,
    responses=ERROR_RESPONSES,
    summary="Sửa hiệp (xác nhận lại số rep, mức tạ...)",
    description=PERM + " Chỉ khi buổi còn `in_progress` (ngược lại 409 `session_not_in_progress`).",
)
async def update_set(
    session_id: uuid.UUID,
    session_exercise_id: uuid.UUID,
    set_id: int,
    body: UpdateExerciseSetRequest,
    current: CurrentUser = Depends(OWN),
    db: AsyncSession = Depends(get_db),
) -> ExerciseSetDetailResponse:
    return await workout_service.update_set(db, current.id, session_id, session_exercise_id, set_id, body)


@router.delete(
    SET_PATH + "/{set_id}",
    status_code=204,
    responses=ERROR_RESPONSES,
    summary="Xoá hiệp",
    description=PERM + " Xoá luôn rep events. Chỉ khi buổi còn `in_progress`. Trả 204 không có body.",
)
async def delete_set(
    session_id: uuid.UUID,
    session_exercise_id: uuid.UUID,
    set_id: int,
    current: CurrentUser = Depends(OWN),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await workout_service.delete_set(db, current.id, session_id, session_exercise_id, set_id)
    return Response(status_code=204)
