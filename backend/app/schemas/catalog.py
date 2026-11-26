"""Schema Pydantic module Catalog/Wiki (chức năng 1): bài tập, nhóm cơ, thiết bị.

ID danh mục là số nguyên (smallint/integer IDENTITY), media là UUID (doc 05 §2.2, §2.4).
Ví dụ dùng dữ liệu seed `02_reference.sql`, `03_exercises.sql`, `91_test_catalog.sql`.
"""

import uuid
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ExerciseCategory

# Giới hạn trên khớp kiểu cột DB để giá trị tràn kiểu trả 422 thay vì lỗi 500 từ PostgreSQL.
_SMALLINT_MAX = 32767
_INTEGER_MAX = 2147483647


# --- Bài tập ---
class ExerciseSearchQuery(BaseModel):
    """Query param của `GET /exercises`, ánh xạ 1-1 sang tham số `catalog.fn_search_exercises`."""

    q: str | None = Field(
        None, max_length=100, description="Từ khoá (không phân biệt dấu, hoa thường); rỗng = không lọc"
    )
    muscle_group_id: list[Annotated[int, Field(ge=1, le=_SMALLINT_MAX)]] = Field(
        default_factory=list, description="Lọc theo nhóm cơ, lặp param; chọn nhóm cha gồm cả nhóm con"
    )
    is_primary_only: bool = Field(False, description="Chỉ tính nhóm cơ đóng vai trò chính")
    available_equipment_id: list[Annotated[int, Field(ge=1, le=_INTEGER_MAX)]] = Field(
        default_factory=list, description="Thiết bị sẵn có, lặp param; bài chỉ cần thiết bị bắt buộc trong danh sách"
    )
    max_difficulty_rank: int | None = Field(None, ge=1, le=_SMALLINT_MAX, description="Hạng độ khó tối đa")
    limit: int = Field(20, ge=1, le=100, description="Số phần tử mỗi trang")
    cursor: str | None = Field(None, description="Giá trị `pagination.next_cursor` của trang trước")


class ExerciseSummaryResponse(BaseModel):
    """Thẻ bài tập trong kết quả tìm kiếm, giữ thứ tự của `catalog.fn_search_exercises`."""

    id: int
    slug: str
    name: str
    name_en: str | None
    category: ExerciseCategory
    difficulty_code: str
    difficulty_name: str
    difficulty_rank: int = Field(description="Hạng độ khó, 1 là dễ nhất")
    thumbnail_media_id: uuid.UUID | None = Field(description="Media thumbnail chính; null nếu chưa có")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": 10,
                "slug": "dumbbell-row",
                "name": "Chèo tạ đơn một tay",
                "name_en": "One-Arm Dumbbell Row",
                "category": "strength",
                "difficulty_code": "beginner",
                "difficulty_name": "Cơ bản",
                "difficulty_rank": 1,
                "thumbnail_media_id": "9ea73eb9-82e2-421b-866f-91f82ebffcbb",
            }
        }
    )


# --- Nhóm cơ ---
class BodyRegionSchema(BaseModel):
    """Vùng cơ thể (`catalog.body_regions`), chỉ gắn ở nút gốc của cây nhóm cơ."""

    id: int
    code: str
    name: str


class MuscleGroupResponse(BaseModel):
    """Một nút của cây nhóm cơ; `children` lồng đệ quy, sắp theo `display_order, id`."""

    id: int
    code: str
    name: str
    name_en: str | None
    parent_id: int | None
    body_region: BodyRegionSchema | None = Field(description="Chỉ có ở nút gốc; nút con là null")
    heatmap_region_key: str | None
    base_recovery_hours: int = Field(description="Giờ phục hồi tham chiếu")
    display_order: int
    description: str | None
    children: list["MuscleGroupResponse"]

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": 3,
                "code": "back",
                "name": "Lưng",
                "name_en": "Back",
                "parent_id": None,
                "body_region": {"id": 1, "code": "upper_body", "name": "Thân trên"},
                "heatmap_region_key": None,
                "base_recovery_hours": 48,
                "display_order": 2,
                "description": None,
                "children": [
                    {
                        "id": 16,
                        "code": "lats",
                        "name": "Lưng xô",
                        "name_en": "Latissimus Dorsi",
                        "parent_id": 3,
                        "body_region": None,
                        "heatmap_region_key": "lats",
                        "base_recovery_hours": 60,
                        "display_order": 1,
                        "description": None,
                        "children": [],
                    }
                ],
            }
        }
    )


# --- Thiết bị ---
class EquipmentCategorySchema(BaseModel):
    """Nhóm thiết bị (`catalog.equipment_categories`)."""

    id: int
    code: str
    name: str


class EquipmentResponse(BaseModel):
    """Thiết bị chưa xoá mềm; `synonyms` chỉ gồm alias loại từ đồng nghĩa (không có nhãn AI)."""

    id: int
    code: str
    name: str
    name_en: str | None
    description: str | None
    category: EquipmentCategorySchema
    image_media_id: uuid.UUID | None
    synonyms: list[str] = Field(description="Từ đồng nghĩa, sắp tăng dần; [] nếu không có")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": 3,
                "code": "dumbbell",
                "name": "Tạ đơn",
                "name_en": "Dumbbell",
                "description": "Tạ cầm một tay, cho phép tập từng bên.",
                "category": {"id": 1, "code": "free_weight", "name": "Tạ tự do"},
                "image_media_id": "2c5a859d-cc1f-42a0-8c8f-10b3f05d206b",
                "synonyms": ["tạ tay"],
            }
        }
    )


class EquipmentQuery(BaseModel):
    """Query param của `GET /equipment` (gom vào một model theo coding-standards §1, §6)."""

    category_id: int | None = Field(None, ge=1, le=32767, description="Lọc theo nhóm thiết bị")
    limit: int = Field(20, ge=1, le=100, description="Số phần tử mỗi trang")
    cursor: str | None = Field(None, description="Giá trị `pagination.next_cursor` của trang trước")
