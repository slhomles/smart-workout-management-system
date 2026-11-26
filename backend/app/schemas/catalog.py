"""Schema Pydantic module Catalog/Wiki (chức năng 1): bài tập, nhóm cơ, thiết bị.

ID danh mục là số nguyên (smallint/integer IDENTITY), media là UUID (doc 05 §2.2, §2.4).
Ví dụ dùng dữ liệu seed `02_reference.sql`, `03_exercises.sql`, `91_test_catalog.sql`.
"""

import uuid
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ExerciseCategory, ForceType, JointType, MechanicType, MediaRole, MuscleRole

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


class DifficultySchema(BaseModel):
    """Độ khó (`catalog.difficulty_levels`); `rank` tăng theo độ khó."""

    id: int
    code: str
    name: str
    rank: int = Field(description="Hạng độ khó, 1 là dễ nhất")


class ExerciseMuscleSchema(BaseModel):
    """Nhóm cơ bài tập tác động, kèm vai trò và tỷ lệ kích hoạt."""

    muscle_group_id: int
    code: str
    name: str
    name_en: str | None
    role: MuscleRole
    activation_ratio: float = Field(description="Tỷ lệ kích hoạt trong (0, 1]")


class ExerciseEquipmentSchema(BaseModel):
    """Thiết bị (chưa xoá mềm) bài tập cần; `is_optional=true` là thiết bị tuỳ chọn."""

    equipment_id: int
    code: str
    name: str
    name_en: str | None
    is_optional: bool


class ExerciseInstructionSchema(BaseModel):
    """Một bước thực hiện, `step_no` bắt đầu từ 1."""

    step_no: int
    content: str


class ExerciseMistakeSchema(BaseModel):
    """Lỗi sai thường gặp; `code` là mã model AI trả về khi phát hiện lỗi."""

    id: int
    code: str
    title: str
    description: str | None
    correction_cue: str | None = Field(description="Gợi ý sửa lỗi")
    at_risk_joint: JointType | None = Field(description="Khớp có nguy cơ chấn thương; null nếu không xác định")
    is_ai_detectable: bool = Field(description="AI có thể phát hiện lỗi này tự động")
    display_order: int


class ExerciseMediaSchema(BaseModel):
    """Metadata media minh hoạ. Không có URL: DB chỉ lưu bucket/object_key (design-overview §2)."""

    media_id: uuid.UUID
    media_role: MediaRole
    is_primary: bool = Field(description="Media chính của vai trò đó")
    display_order: int
    caption: str | None
    mime_type: str
    width_px: int | None
    height_px: int | None
    duration_ms: int | None = Field(description="Thời lượng GIF/video (ms); null với ảnh")


class ExerciseDetailResponse(BaseModel):
    """Chi tiết kỹ thuật của bài đã xuất bản; thứ tự các danh sách theo spec exercise-wiki §6 mục 9."""

    id: int
    slug: str
    name: str
    name_en: str | None
    description: str | None
    category: ExerciseCategory
    mechanic: MechanicType | None = Field(description="null với bài cardio/giãn cơ")
    force_type: ForceType | None
    is_unilateral: bool = Field(description="Tập từng bên (một tay/một chân)")
    met_value: float | None = Field(description="Chỉ số MET để ước tính calo")
    supports_ai_tracking: bool = Field(description="Có AI chấm tư thế/đếm rep cho bài này")
    difficulty: DifficultySchema
    muscles: list[ExerciseMuscleSchema] = Field(description="Sắp theo vai trò, tỷ lệ kích hoạt giảm, tên")
    equipment: list[ExerciseEquipmentSchema] = Field(description="Bắt buộc trước, tuỳ chọn sau, rồi theo tên")
    instructions: list[ExerciseInstructionSchema] = Field(description="Sắp theo `step_no`")
    mistakes: list[ExerciseMistakeSchema] = Field(description="Sắp theo `display_order`, `id`")
    media: list[ExerciseMediaSchema] = Field(description="Chỉ file sẵn sàng; sắp theo `display_order`, `media_role`")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": 10, "slug": "dumbbell-row", "name": "Chèo tạ đơn một tay", "name_en": "One-Arm Dumbbell Row",
                "description": "Kéo tạ đơn về hông, tay và gối tựa ghế.",
                "category": "strength", "mechanic": "compound", "force_type": "pull", "is_unilateral": True,
                "met_value": 4.5, "supports_ai_tracking": True,
                "difficulty": {"id": 1, "code": "beginner", "name": "Cơ bản", "rank": 1},
                "muscles": [
                    {"muscle_group_id": 16, "code": "lats", "name": "Lưng xô", "name_en": "Latissimus Dorsi",
                     "role": "primary", "activation_ratio": 1.0},
                    {"muscle_group_id": 14, "code": "upper_back", "name": "Lưng giữa", "name_en": "Rhomboids",
                     "role": "secondary", "activation_ratio": 0.6},
                ],
                "equipment": [
                    {"equipment_id": 3, "code": "dumbbell", "name": "Tạ đơn", "name_en": "Dumbbell", "is_optional": False},
                ],
                "instructions": [
                    {"step_no": 1, "content": "Tì gối và tay cùng bên lên ghế, lưng song song sàn, tay kia cầm tạ."},
                ],
                "mistakes": [
                    {"id": 30, "code": "DB_ROW_TORSO_ROTATION", "title": "Xoay thân khi kéo",
                     "description": "Xoay vai/hông để kéo tạ nặng.", "correction_cue": "Giữ vai song song sàn, giảm tạ.",
                     "at_risk_joint": "spine", "is_ai_detectable": True, "display_order": 1},
                ],
                "media": [
                    {"media_id": "4ff3c43a-baa6-4929-ab9d-2d3b4bfebe5d", "media_role": "gif", "is_primary": True,
                     "display_order": 1, "caption": None, "mime_type": "image/gif", "width_px": 480,
                     "height_px": 360, "duration_ms": 4310},
                ],
            }
        }
    )


class ExerciseAlternativesQuery(BaseModel):
    """Query param của `GET /exercises/{id_or_slug}/alternatives`."""

    unavailable_equipment_id: list[Annotated[int, Field(ge=1, le=_INTEGER_MAX)]] = Field(
        default_factory=list, description="Thiết bị đang bận, lặp param; loại bài cần thiết bị bắt buộc trong danh sách"
    )
    limit: int = Field(20, ge=1, le=100, description="Số phần tử mỗi trang")
    cursor: str | None = Field(None, description="Giá trị `pagination.next_cursor` của trang trước")


class ExerciseAlternativeResponse(BaseModel):
    """Bài thay thế, giữ thứ tự của `catalog.fn_suggest_alternatives` (`score` giảm dần, rồi tên)."""

    id: int
    slug: str
    name: str
    difficulty_rank: int = Field(description="Hạng độ khó, 1 là dễ nhất")
    is_curated: bool = Field(description="Bài thay thế do biên tập viên chọn")
    muscle_overlap: float = Field(description="Độ trùng nhóm cơ chính với bài gốc, 0–1")
    score: float = Field(description="Điểm gợi ý, càng cao càng phù hợp")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"id": 23, "slug": "barbell-row", "name": "Chèo tạ đòn", "difficulty_rank": 2,
                        "is_curated": True, "muscle_overlap": 1.0, "score": 1.55}
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


class EquipmentExerciseSchema(BaseModel):
    """Bài tập dùng thiết bị khớp nhãn AI (`catalog.fn_exercises_for_ai_label`), cho chức năng 7."""

    equipment_id: int
    equipment_name: str
    exercise_id: int
    slug: str
    exercise_name: str
    difficulty_rank: int
