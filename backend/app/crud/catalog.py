"""Truy vấn chỉ đọc schema `catalog` bằng `text()` (module Catalog/Wiki không có model ORM, không commit)."""

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def list_muscle_groups(db: AsyncSession) -> list[Any]:
    """Mọi nhóm cơ (cây phẳng) kèm vùng cơ thể của nút gốc, sắp `display_order, id`."""
    sql = """
    SELECT mg.id, mg.code, mg.name, mg.name_en, mg.parent_id, mg.heatmap_region_key,
           mg.base_recovery_hours, mg.display_order, mg.description,
           br.id AS body_region_id, br.code AS body_region_code, br.name AS body_region_name
    FROM catalog.muscle_groups mg
    LEFT JOIN catalog.body_regions br ON br.id = mg.body_region_id
    ORDER BY mg.display_order, mg.id
    """
    return list((await db.execute(text(sql))).mappings().all())


# `alias_type = 'synonym'` để không lộ nhãn `ai_label` của chức năng 7 (spec exercise-wiki §6 mục 5).
_EQUIPMENT_SELECT = """
SELECT e.id, e.code, e.name, e.name_en, e.description, e.image_media_id,
       c.id AS category_id, c.code AS category_code, c.name AS category_name,
       ARRAY(
           SELECT a.alias FROM catalog.equipment_aliases a
           WHERE a.equipment_id = e.id AND a.alias_type = 'synonym'
           ORDER BY a.alias
       ) AS synonyms
FROM catalog.equipment e
JOIN catalog.equipment_categories c ON c.id = e.category_id
WHERE e.deleted_at IS NULL
"""


async def list_equipment(
    db: AsyncSession, *, category_id: int | None, after_id: int | None, limit: int
) -> list[Any]:
    """Thiết bị chưa xoá mềm, keyset `id ASC` (sau `after_id`), lọc tuỳ chọn theo nhóm."""
    sql = _EQUIPMENT_SELECT
    params: dict[str, Any] = {"limit": limit}
    if category_id is not None:
        sql += " AND e.category_id = :category_id"
        params["category_id"] = category_id
    if after_id is not None:
        sql += " AND e.id > :after_id"
        params["after_id"] = after_id
    sql += " ORDER BY e.id LIMIT :limit"
    return list((await db.execute(text(sql), params)).mappings().all())
