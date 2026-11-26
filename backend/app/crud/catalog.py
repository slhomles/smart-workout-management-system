"""Truy vấn chỉ đọc schema `catalog` bằng `text()` (module Catalog/Wiki không có model ORM, không commit)."""

from dataclasses import asdict, dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


# --- Bài tập ---
@dataclass(frozen=True)
class ExerciseSearchFilter:
    """Đối số lọc của `catalog.fn_search_exercises`; `None` = không lọc theo điều kiện đó."""

    keyword: str | None
    muscle_group_ids: list[int] | None
    is_primary_only: bool
    available_equipment_ids: list[int] | None
    max_difficulty_rank: int | None


# CAST để asyncpg biết kiểu tham số (NULL không mang kiểu). WITH ORDINALITY + ORDER BY s.ord giữ đúng thứ tự
# hàm trả về (độ khó, mức khớp, tên) sau khi JOIN view lấy thêm tên độ khó và thumbnail.
_SEARCH_EXERCISES_SQL = """
SELECT s.exercise_id AS id, s.slug, s.name, s.name_en, s.category,
       s.difficulty_code, s.difficulty_rank, c.difficulty_name, c.thumbnail_media_id
FROM catalog.fn_search_exercises(
         CAST(:keyword AS text), CAST(:muscle_group_ids AS smallint[]), CAST(:is_primary_only AS boolean),
         CAST(:available_equipment_ids AS integer[]), CAST(:max_difficulty_rank AS smallint),
         CAST(:limit AS integer), CAST(:offset AS integer)
     ) WITH ORDINALITY
       AS s(exercise_id, slug, name, name_en, difficulty_code, difficulty_rank, category, match_score, ord)
LEFT JOIN catalog.v_exercise_cards c ON c.exercise_id = s.exercise_id
ORDER BY s.ord
"""


async def search_exercises(
    db: AsyncSession, search: ExerciseSearchFilter, *, limit: int, offset: int
) -> list[Any]:
    """Bài đã xuất bản khớp bộ lọc, theo thứ tự của `catalog.fn_search_exercises` (LIMIT/OFFSET)."""
    params = {**asdict(search), "limit": limit, "offset": offset}
    return list((await db.execute(text(_SEARCH_EXERCISES_SQL), params)).mappings().all())


_PUBLISHED_EXERCISE_SELECT = """
SELECT e.id, e.slug, e.name, e.name_en, e.description, e.category, e.mechanic, e.force_type,
       e.is_unilateral, e.met_value, e.supports_ai_tracking,
       d.id AS difficulty_id, d.code AS difficulty_code, d.name AS difficulty_name, d.rank AS difficulty_rank
FROM catalog.exercises e
JOIN catalog.difficulty_levels d ON d.id = e.difficulty_level_id
WHERE e.status = 'published' AND e.deleted_at IS NULL
"""


async def get_published_exercise_by_id(db: AsyncSession, exercise_id: int) -> Any | None:
    """Bài đã xuất bản, chưa xoá mềm, kèm độ khó, theo `id`; None nếu không có."""
    sql = _PUBLISHED_EXERCISE_SELECT + " AND e.id = :exercise_id"
    return (await db.execute(text(sql), {"exercise_id": exercise_id})).mappings().first()


async def get_published_exercise_by_slug(db: AsyncSession, slug: str) -> Any | None:
    """Bài đã xuất bản, chưa xoá mềm, kèm độ khó, theo `slug`; None nếu không có."""
    sql = _PUBLISHED_EXERCISE_SELECT + " AND e.slug = :slug"
    return (await db.execute(text(sql), {"slug": slug})).mappings().first()


async def _rows_of_exercise(db: AsyncSession, sql: str, exercise_id: int) -> list[Any]:
    return list((await db.execute(text(sql), {"exercise_id": exercise_id})).mappings().all())


# Thứ tự cố định theo spec exercise-wiki §6 mục 9; cột cuối (id) chỉ để thứ tự ổn định khi trùng.
# `ORDER BY em.role` / `em.media_role` theo thứ tự khai báo của enum PostgreSQL, không theo chữ cái.
async def list_exercise_muscles(db: AsyncSession, exercise_id: int) -> list[Any]:
    """Nhóm cơ của bài: vai trò (primary → secondary → stabilizer), tỷ lệ kích hoạt giảm, tên."""
    sql = """
    SELECT em.muscle_group_id, mg.code, mg.name, mg.name_en, em.role, em.activation_ratio
    FROM catalog.exercise_muscles em
    JOIN catalog.muscle_groups mg ON mg.id = em.muscle_group_id
    WHERE em.exercise_id = :exercise_id
    ORDER BY em.role, em.activation_ratio DESC, mg.name, mg.id
    """
    return await _rows_of_exercise(db, sql, exercise_id)


async def list_exercise_equipment(db: AsyncSession, exercise_id: int) -> list[Any]:
    """Thiết bị chưa xoá mềm của bài: bắt buộc trước, tuỳ chọn sau, rồi theo tên."""
    sql = """
    SELECT ee.equipment_id, eq.code, eq.name, eq.name_en, ee.is_optional
    FROM catalog.exercise_equipment ee
    JOIN catalog.equipment eq ON eq.id = ee.equipment_id
    WHERE ee.exercise_id = :exercise_id AND eq.deleted_at IS NULL
    ORDER BY ee.is_optional, eq.name, eq.id
    """
    return await _rows_of_exercise(db, sql, exercise_id)


async def list_exercise_instructions(db: AsyncSession, exercise_id: int) -> list[Any]:
    """Các bước thực hiện theo `step_no`."""
    sql = """
    SELECT step_no, content FROM catalog.exercise_instructions
    WHERE exercise_id = :exercise_id
    ORDER BY step_no
    """
    return await _rows_of_exercise(db, sql, exercise_id)


async def list_exercise_mistakes(db: AsyncSession, exercise_id: int) -> list[Any]:
    """Lỗi sai thường gặp theo `display_order, id`; cột `ai_detectable` đổi tên thành `is_ai_detectable`."""
    sql = """
    SELECT id, code, title, description, correction_cue, at_risk_joint,
           ai_detectable AS is_ai_detectable, display_order
    FROM catalog.exercise_mistakes
    WHERE exercise_id = :exercise_id
    ORDER BY display_order, id
    """
    return await _rows_of_exercise(db, sql, exercise_id)


async def list_exercise_media(db: AsyncSession, exercise_id: int) -> list[Any]:
    """Media sẵn sàng (chưa xoá) của bài theo `display_order, media_role`; chỉ metadata, không bucket/object_key.

    Đọc `media.media_files` chỉ đọc bằng `text()` vì module Gallery & Media chưa có service (spec §6 mục 9).
    """
    sql = """
    SELECT em.media_id, em.media_role, em.is_primary, em.display_order, em.caption,
           f.mime_type, f.width_px, f.height_px, f.duration_ms
    FROM catalog.exercise_media em
    JOIN media.media_files f ON f.id = em.media_id
    WHERE em.exercise_id = :exercise_id AND f.status = 'available' AND f.deleted_at IS NULL
    ORDER BY em.display_order, em.media_role, em.media_id
    """
    return await _rows_of_exercise(db, sql, exercise_id)


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
