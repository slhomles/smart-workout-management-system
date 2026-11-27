"""Nghiệp vụ giáo án mẫu của module Catalog/Wiki (`GET /plan-templates`).

Tách khỏi `catalog_service.py` theo spec exercise-wiki §2 để giữ file dưới ngưỡng 300 dòng.
Module chỉ đọc DB nên không có ranh giới transaction/commit.
"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import catalog as crud
from app.schemas.base import Page, build_page, decode_keyset_cursor
from app.schemas.catalog import DifficultySchema, PlanTemplateQuery, PlanTemplateSummaryResponse


def _difficulty(row: Any) -> DifficultySchema | None:
    # Cột `difficulty_level_id` cho phép null: giáo án chưa gắn độ khó trả `difficulty=null`.
    if row["difficulty_id"] is None:
        return None
    return DifficultySchema(
        id=row["difficulty_id"], code=row["difficulty_code"], name=row["difficulty_name"], rank=row["difficulty_rank"]
    )


def _plan_template_item(row: Any) -> PlanTemplateSummaryResponse:
    return PlanTemplateSummaryResponse(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        goal_type_id=row["goal_type_id"],
        difficulty=_difficulty(row),
        duration_weeks=row["duration_weeks"],
        day_count=row["day_count"],
        created_at=row["created_at"],
    )


def _cursor_of(row: Any) -> dict[str, Any]:
    return {"created_at": row["created_at"].isoformat(), "id": str(row["id"])}


async def list_plan_templates(db: AsyncSession, query: PlanTemplateQuery) -> Page[PlanTemplateSummaryResponse]:
    """Giáo án mẫu đang áp dụng, mới nhất trước; cursor `{"created_at", "id"}` (keyset)."""
    template_filter = crud.PlanTemplateFilter(
        goal_type_id=query.goal_type_id, difficulty_level_id=query.difficulty_level_id
    )
    after = decode_keyset_cursor(query.cursor, "created_at")
    rows = await crud.list_plan_templates(db, template_filter, after=after, limit=query.limit + 1)
    return build_page(rows, query.limit, _plan_template_item, _cursor_of)
