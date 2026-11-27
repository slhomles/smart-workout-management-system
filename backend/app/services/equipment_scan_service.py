"""Nghiệp vụ /ai/equipment-scans (chức năng 7: nhận diện thiết bị phòng tập)."""

import io
import logging
import uuid
from dataclasses import dataclass
from typing import Any

from fastapi import UploadFile
from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core.exceptions import DataValidationError
from app.crud import equipment_scan as crud
from app.schemas.base import ErrorDetail, Page, build_page, decode_keyset_cursor
from app.schemas.equipment_scan import (
    AiPrediction,
    EquipmentScanResponse,
    EquipmentScanSummaryResponse,
    SuggestedExerciseSchema,
)
from app.services import catalog_service, equipment_recognition_client

logger = logging.getLogger("app.equipment_scan")

MAX_IMAGE_BYTES = 10 * 1024 * 1024
ACCEPTED_CONTENT_TYPES = frozenset({"image/jpeg", "image/png"})
# Định dạng thật do Pillow nhận diện; không tin riêng content type của client.
ACCEPTED_IMAGE_FORMATS = frozenset({"JPEG", "PNG"})
# k của "top-k" dự đoán được lưu, module tự chốt (spec §6 ý 6).
MAX_STORED_PREDICTIONS = 5
SUGGESTION_LIMIT = 20


@dataclass(frozen=True)
class _MappedPrediction:
    """Dự đoán đã ánh xạ sang thiết bị; giữ nhãn đã chuẩn hoá để gọi Catalog khi thiết bị này là top-1."""

    equipment_id: int
    confidence: float
    ai_label: str


def _summary(row: Any) -> EquipmentScanSummaryResponse:
    return EquipmentScanSummaryResponse.model_validate(dict(row))


async def list_scans(
    db: AsyncSession, user_id: uuid.UUID, *, limit: int, cursor: str | None
) -> Page[EquipmentScanSummaryResponse]:
    """Lịch sử quét của chính user (keyset `scanned_at DESC, id DESC`); cursor hỏng → 422."""
    rows = await crud.list_scan_rows(
        db, user_id, after=decode_keyset_cursor(cursor, "scanned_at"), limit=limit + 1
    )
    return build_page(
        rows,
        limit,
        to_item=_summary,
        cursor_of=lambda r: {"scanned_at": r["scanned_at"].isoformat(), "id": str(r["id"])},
    )


async def create_scan(db: AsyncSession, user_id: uuid.UUID, image: UploadFile) -> EquipmentScanResponse:
    """Quét một ảnh: kiểm tra ảnh → gọi AI → ánh xạ nhãn → lưu lần quét + top-5 → gợi ý bài tập.

    Ảnh sai → 422 trước khi gọi AI; AI lỗi → 503 trước khi ghi DB. Ghi và đọc nằm trong một transaction,
    chỉ commit sau khi đã dựng xong response; lỗi ở bước nào thì `get_db` rollback (spec §6 ý 8).
    """
    data, content_type = await _read_valid_image(image)
    ai_result = await equipment_recognition_client.classify_image(data, image.filename, content_type)
    mapped = await _map_predictions(db, ai_result.predictions)
    scan_id = await crud.create_scan(db, user_id, ai_result, [(p.equipment_id, p.confidence) for p in mapped])
    response = await _load_scan_response(db, user_id, scan_id, {p.equipment_id: p.ai_label for p in mapped})
    await db.commit()
    return response


def _invalid_image(message: str) -> DataValidationError:
    return DataValidationError([ErrorDetail(field="image", message=message, code="value_error")])


def _detect_image_format(data: bytes) -> str | None:
    """Định dạng thật của ảnh sau `verify()` của Pillow; None nếu byte không phải ảnh giải mã được."""
    try:
        with Image.open(io.BytesIO(data)) as image:
            image.verify()
            return image.format
    except Exception as exc:
        # Byte do client gửi: Pillow ném nhiều loại lỗi (UnidentifiedImageError, SyntaxError, struct.error…),
        # mọi trường hợp đều là ảnh không hợp lệ (422), không phải lỗi server.
        logger.info("equipment scan: ảnh tải lên không giải mã được (%s)", type(exc).__name__)
        return None


async def _read_valid_image(image: UploadFile) -> tuple[bytes, str]:
    """Kiểm tra ảnh theo thứ tự spec §6 ý 3; trả bytes và content type đã kiểm."""
    content_type = image.content_type or ""
    if content_type not in ACCEPTED_CONTENT_TYPES:
        raise _invalid_image("Chỉ nhận ảnh JPEG hoặc PNG")
    # Đọc tối đa giới hạn + 1 byte: đủ biết file vượt giới hạn mà không phải đọc hết file lớn.
    data = await image.read(MAX_IMAGE_BYTES + 1)
    if not data:
        raise _invalid_image("Tệp ảnh rỗng")
    if len(data) > MAX_IMAGE_BYTES:
        raise _invalid_image("Ảnh vượt quá 10 MiB")
    if await run_in_threadpool(_detect_image_format, data) not in ACCEPTED_IMAGE_FORMATS:
        raise _invalid_image("Tệp không phải ảnh JPEG hoặc PNG hợp lệ")
    return data, content_type


async def _map_predictions(db: AsyncSession, predictions: list[AiPrediction]) -> list[_MappedPrediction]:
    """Nhãn → thiết bị (spec §6 ý 6): bỏ nhãn không ánh xạ được, gộp trùng theo confidence lớn nhất, giữ top-5."""
    labelled = [(prediction.label.strip().lower(), prediction.confidence) for prediction in predictions]
    if not labelled:
        return []
    equipment_by_label = await crud.map_ai_labels_to_equipment(db, sorted({label for label, _ in labelled}))
    best: dict[int, _MappedPrediction] = {}
    for label, confidence in labelled:
        equipment_id = equipment_by_label.get(label)
        if equipment_id is None:
            continue
        kept = best.get(equipment_id)
        if kept is None or confidence > kept.confidence:
            best[equipment_id] = _MappedPrediction(equipment_id, confidence, label)
    ranked = sorted(best.values(), key=lambda p: (-p.confidence, p.equipment_id))
    return ranked[:MAX_STORED_PREDICTIONS]


async def _load_scan_response(
    db: AsyncSession, user_id: uuid.UUID, scan_id: uuid.UUID, label_by_equipment: dict[int, str]
) -> EquipmentScanResponse:
    """Đọc lại lần quét vừa ghi: top-1 và `is_confident` từ view, dự đoán đã làm tròn từ DB (spec §6 ý 7, 9)."""
    row = await crud.get_scan_row(db, user_id, scan_id)
    predictions = await crud.list_prediction_rows(db, scan_id)
    suggestions = await _suggest_exercises(db, row, label_by_equipment)
    return EquipmentScanResponse.model_validate(
        {**dict(row), "predictions": [dict(p) for p in predictions], "suggested_exercises": suggestions}
    )


async def _suggest_exercises(
    db: AsyncSession, scan_row: Any, label_by_equipment: dict[int, str]
) -> list[SuggestedExerciseSchema]:
    """Bài tập dùng thiết bị top-1, chỉ khi view đánh dấu `is_confident`; thứ tự giữ nguyên như Catalog trả."""
    if not scan_row["is_confident"]:
        # Dưới ngưỡng tin cậy của view: không gợi ý và không gọi Catalog (spec §6 ý 7, Q7).
        return []
    ai_label = label_by_equipment[scan_row["predicted_equipment_id"]]
    exercises = await catalog_service.list_exercises_for_ai_label(db, ai_label, limit=SUGGESTION_LIMIT)
    return [SuggestedExerciseSchema.model_validate(exercise.model_dump()) for exercise in exercises]
