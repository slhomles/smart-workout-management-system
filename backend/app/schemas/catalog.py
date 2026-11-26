"""Schema Pydantic module Catalog/Wiki (chức năng 1): nhóm cơ, thiết bị.

ID danh mục là số nguyên (smallint/integer IDENTITY), media là UUID (doc 05 §2.2, §2.4).
Ví dụ dùng dữ liệu seed `02_reference.sql`, `91_test_catalog.sql`.
"""

import uuid

from pydantic import BaseModel, ConfigDict, Field


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
