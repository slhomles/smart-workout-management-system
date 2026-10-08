# Task 5 — Chốt Công Cụ & Quy Trình Làm Việc (Tooling & Workflow)

> **Trạng thái:** Chuẩn thống nhất — mọi thành viên PHẢI tuân theo.
> **Cập nhật:** 2026-10-08 · **Stack:** FastAPI · Pydantic v2 · SQLAlchemy 2 (async) · Alembic · Swagger/OpenAPI · pytest · ruff · mypy
> **Nguồn sự thật về dữ liệu:** `database/postgresql/` và `docs/database/`. Doc này KHÔNG định nghĩa lại bảng/cột; nếu mâu thuẫn, **DB đúng** và doc phải sửa.
> **Từ khoá:** PHẢI / KHÔNG ĐƯỢC / NÊN có nghĩa như trong RFC 2119.

Tài liệu đi kèm: [`04-auth-strategy.md`](04-auth-strategy.md) (token, role, permission, mã lỗi auth).

---

## 0. Tóm tắt một trang

| Hạng mục | Quyết định |
|---|---|
| Quy trình | **Contract-first**: Pydantic Schema → API Mock (≤ 24 giờ) → Frontend làm song song → thay bằng logic thật |
| Tài liệu API | Swagger tự sinh: `/docs`, `/redoc`, `/openapi.json` |
| Envelope | `BaseResponse[T]` / `ErrorResponse` / `PaginatedResponse[T]` (mục 3) |
| ID | **UUID** cho dữ liệu của user, **số nguyên** cho danh mục (exercise, equipment, muscle_group…) — đúng theo DB |
| Đơn vị | SI trong API & DB (kg, cm, m, ms, độ); đổi sang imperial là việc của client |
| Thời gian | ISO-8601 UTC có hậu tố `Z` |
| Tầng code | `api → services → crud → models` |
| Core/Shared | Do **một người** (Core owner) chịu trách nhiệm; người khác chỉ sửa qua PR được Core owner duyệt |
| Schema DB | SQL trong `database/postgresql/` là **baseline v1 (đóng băng)**; thay đổi sau đó chỉ bằng **migration Alembic** |
| Git | `main` ← `develop` ← `feature/*`; PR ≥ 1 reviewer, CI xanh, không tự merge |
| Test | ≥ 2 test/endpoint, coverage ≥ 70%, chạy trên PostgreSQL thật |

---

## 1. Quy trình làm việc Contract-first

### 1.1. Luồng chuẩn cho một tính năng

```
Tuần 1:  Core setup (mục 7) ─────────────────────────────┐
                                                          ▼
Từ tuần 2, mỗi endpoint/nhóm endpoint:
  [BE] 1. Schema PR   → viết Pydantic Request/Response + khai báo route (chưa logic)
  [BE+FE] 2. Review   → FE xác nhận schema đủ dùng cho màn hình
  [BE] 3. Mock PR     → trả dữ liệu giả đúng schema, SAU ≤ 24 giờ kể từ khi schema được duyệt
  [FE] 4. Làm UI      → gọi mock qua Swagger/Postman/app, KHÔNG chờ BE
  [BE] 5. Logic thật  → thay mock bằng service/crud, giữ NGUYÊN contract
  [BE] 6. Test + gỡ [MOCK] → merge
```

**Quy tắc vàng:** Frontend không bao giờ phải chờ Backend xong logic. Backend không được để schema đã duyệt mà chưa có mock quá 24 giờ.

### 1.2. Thay đổi contract sau khi merge

| Loại thay đổi | Được phép? | Quy trình |
|---|---|---|
| Thêm field **tuỳ chọn** vào response | ✅ | Ghi trong mô tả PR |
| Thêm field tuỳ chọn vào request | ✅ | Ghi trong mô tả PR |
| Thêm field **bắt buộc** vào request, đổi tên/kiểu/xoá field, đổi status code, đổi `error_code` | ⚠️ Phá vỡ contract | PHẢI báo kênh chung của nhóm, đính kèm nhãn `breaking-change` trên PR, FE xác nhận trước khi merge |

### 1.3. Ranh giới trách nhiệm

| Việc | Ai làm |
|---|---|
| Pydantic schema, route, mock, logic, test của một module | Owner của module (mục 6.3) |
| File core (mục 7) | Core owner |
| Bảng/migration | Owner module cần thay đổi, được Core owner + 1 người khác duyệt (mục 8) |
| Màn hình, gọi API, xử lý token | Frontend; chỉ gọi endpoint đã có trong Swagger |
| Model AI, worker | AI team; giao tiếp với backend qua hợp đồng riêng (ngoài phạm vi doc này) |

---

## 2. Quy ước API chung

Các quy ước này áp dụng cho MỌI endpoint. Vi phạm = PR bị từ chối.

### 2.1. URL & JSON

- Prefix: `/api/v1`. Path dùng **danh từ số nhiều, kebab-case**: `/workout-sessions`, `/progress-photos`. Hành động phi-CRUD dùng động từ ở cuối: `/workout-sessions/{id}/finish`.
- Field JSON: **`snake_case`** (cả request lẫn response).
- Method: `GET` đọc · `POST` tạo/hành động · `PUT` thay thế · `PATCH` sửa một phần · `DELETE` xoá.
- Status code: `200` đọc/sửa · `201` tạo · `204` xoá (không body) · `202` nhận job bất đồng bộ (video AI).

### 2.2. Kiểu dữ liệu

| Loại | Quy ước | Ví dụ |
|---|---|---|
| ID dữ liệu của user (user, session, photo, measurement, plan…) | **UUID v4** dạng chuỗi (ngoại lệ `bigint`: `exercise_sets`, `posture_issues`, `muscle_soreness_reports`, `login_attempts` — xem mục 2.4) | `"5eed0000-0000-4000-8000-000000000003"` |
| ID danh mục/lookup (exercise, equipment, muscle_group, difficulty_level, goal_type, activity_level…) | **Số nguyên** | `"exercise_id": 42` |
| Thời điểm | ISO-8601 UTC, hậu tố `Z` (`timestamptz`) | `"2026-10-08T07:30:00Z"` |
| Ngày (không giờ) | `YYYY-MM-DD` | `"scheduled_date": "2026-10-09"` |
| Cân nặng | kg (số thực) | `70.5` |
| Chiều cao, vòng đo | cm | `175.0` |
| Quãng đường | mét | `5000` |
| Thời lượng/tempo | **mili-giây** (`*_ms`) hoặc giây (`*_seconds`) đúng theo tên cột DB | `"eccentric_ms": 3000` |
| Góc khớp | độ (°) | `"min_angle_deg": 78.5` |
| Tỷ lệ phần trăm | số 0–100, hậu tố `_pct` | `"body_fat_pct": 18.5` |
| Điểm AI | số 0–100 | `"overall_score": 85` |

- Đổi sang imperial (lb, in…) là việc của **client** dựa trên `unit_system` trong hồ sơ. API/DB luôn là SI.
- Chuỗi rỗng KHÔNG đồng nghĩa `null`: trường không có giá trị phải là `null` (hoặc vắng mặt nếu schema cho phép), không dùng `""`/`0`/`-1` để đại diện "không có".
- Tính toán dẫn xuất (BMI, BMR, TDEE, volume, 1RM, trạng thái phục hồi) lấy từ **view/hàm SQL** của DB (`body.v_body_metrics`, `training.v_set_metrics`, `training.v_muscle_recovery_status`…); KHÔNG tính lại bằng công thức khác trong Python/Frontend.

### 2.3. Enum

Giá trị enum trong API là **chuỗi `snake_case` trùng khớp enum của DB** (không đổi tên, không viết hoa). Định nghĩa Python đặt tại `app/models/enums.py` (một nơi duy nhất; Pydantic schema import từ đây).

| Enum Python | Giá trị | Nguồn DB |
|---|---|---|
| `UserStatus` | `pending_verification` `active` `locked` `disabled` | `auth.user_status` |
| `UnitSystem` | `metric` `imperial` | `auth.unit_system` |
| `DevicePlatform` | `ios` `android` `web` | `auth.device_platform` |
| `RoleCode` | `admin` `content_editor` `user` | `auth.roles.code` |
| `ContentStatus` | `draft` `published` `archived` | `catalog.content_status` |
| `ExerciseCategory` | `strength` `cardio` `stretching` `plyometric` `mobility` | `catalog.exercise_category` |
| `MechanicType` | `compound` `isolation` | `catalog.mechanic_type` |
| `ForceType` | `push` `pull` `static` | `catalog.force_type` |
| `MuscleRole` | `primary` `secondary` `stabilizer` | `catalog.muscle_role` |
| `MediaRole` | `thumbnail` `gif` `video` `image` | `catalog.media_role` |
| `JointType` | `neck` `shoulder` `elbow` `wrist` `spine` `hip` `knee` `ankle` | `catalog.joint_type` |
| `Gender` | `male` `female` `other` `unspecified` | `body.gender` |
| `MeasurementSource` | `manual` `smart_scale` `imported` | `body.measurement_source` |
| `GoalStatus` | `active` `achieved` `abandoned` | `body.goal_status` |
| `PlanStatus` | `draft` `active` `archived` | `training.plan_status` |
| `ScheduleStatus` | `planned` `skipped` `cancelled` | `training.schedule_status` |
| `SessionStatus` | `in_progress` `completed` `abandoned` | `training.session_status` |
| `SetType` | `warmup` `working` `drop` `failure` | `training.set_type` |
| `LogSource` | `manual` `ai_realtime` `ai_video` | `training.log_source` |
| `AddedVia` | `plan` `manual` `wiki` `equipment_scan` | `training.added_via` |
| `AnalysisMode` | `realtime_edge` `video_server` | `ai.analysis_mode` |
| `IssueSeverity` | `info` `warning` `critical` | `ai.issue_severity` |
| `ScanFeedback` | `correct` `incorrect` | `ai.scan_feedback` |
| `JobStatus` | `queued` `processing` `completed` `failed` `cancelled` | `util.job_status` |
| `MediaStatus` | `pending_upload` `available` `failed` `quarantined` | `media.media_status` |
| `PhotoAngle` | `front` `side` `back` | `media.photo_angle` |
| `CaptureSource` | `camera` `library` | `media.capture_source` |
| `ReportType` | `weekly_summary` `monthly_summary` | `analytics.report_type` |

> **Tránh nhầm lẫn thường gặp:** trạng thái buổi tập KHÔNG phải một enum duy nhất. **Lịch** (`scheduled_workouts`) dùng `ScheduleStatus` = `planned/skipped/cancelled`; **buổi tập thực tế** (`workout_sessions`) dùng `SessionStatus` = `in_progress/completed/abandoned`. Một lịch "đã hoàn thành" được suy ra từ việc có buổi tập `completed` gắn với nó, không có giá trị `completed` trong `ScheduleStatus`.

### 2.4. Danh tính (ID) chi tiết — đúng như DB

- **Số nguyên (`integer`):** `catalog.exercises.id`, `equipment.id`, `equipment_aliases.id`, `exercise_mistakes.id`.
- **Số nguyên (`smallint`):** `muscle_groups.id`, `difficulty_levels.id`, `body_regions.id`, `equipment_categories.id`, `body.activity_levels.id`, `fitness_goal_types.id`, `body_sites.id`, `auth.roles.id`, `auth.permissions.id`.
- **Số nguyên (`bigint`):** `training.exercise_sets.id`, `training.muscle_soreness_reports.id`, `ai.posture_issues.id`, `auth.login_attempts.id`.
- **Khoá ghép, không có `id` riêng:** `set_rep_events` (`set_id`, `rep_no`), `ai.bar_path_points` (`pose_analysis_id`, `frame_index`), `body.body_circumferences`, `exercise_muscles`, `exercise_equipment`… — API định danh bằng các thành phần của khoá.
- **UUID:** `auth.users`, `user_devices`, `refresh_tokens`, `media_files`, `progress_photos`, `photo_comparisons`, `body_measurements`, `user_goals`, `workout_plans`, `workout_plan_days`, `workout_plan_exercises`, `scheduled_workouts`, `workout_sessions`, `session_exercises`, `pose_analyses`, `video_analysis_jobs`, `equipment_scans`, `report_exports`… Khi nghi ngờ, tra `docs/database/data-dictionary.md`.
- Danh mục có thêm khoá tự nhiên: bài tập tra theo `slug` (`GET /exercises/{id_or_slug}` NÊN hỗ trợ cả hai).

### 2.5. Phân trang, sắp xếp, lọc

- Query phân trang: `page` (≥ 1, mặc định 1) và `limit` (mặc định **20**, tối đa **100**). Vượt tối đa → `422 VALIDATION_ERROR`.
- Sắp xếp: `sort=field` (tăng) hoặc `sort=-field` (giảm); chỉ cho phép các field nằm trong danh sách trắng ghi ở Swagger.
- Lọc: mỗi điều kiện là một query param riêng, tên trùng field (`muscle_group_id=3`), danh sách dùng lặp param (`equipment_id=1&equipment_id=5`) — không dùng chuỗi phân tách bằng dấu phẩy.
- Tìm kiếm văn bản: param `q`. Tìm kiếm bài tập PHẢI gọi hàm SQL `catalog.fn_search_exercises` (đã hỗ trợ không dấu, pg_trgm); KHÔNG tự viết `LIKE '%…%'`.
- Chuỗi thời gian (số đo, thống kê): `from` / `to` (ISO-8601) hoặc `range=week|month|3months`.

### 2.6. Dữ liệu của người dùng & xoá mềm

- Mọi truy vấn dữ liệu cá nhân PHẢI lọc theo `user_id = current_user.id`. Lấy bản ghi không thuộc user → `404 NOT_FOUND` (không dùng `403` để tránh lộ sự tồn tại).
- Bảng có `deleted_at`: truy vấn mặc định PHẢI có `deleted_at IS NULL`; `DELETE` API thực hiện xoá mềm, trả `204`.
- Không bao giờ tin `user_id` từ body/query/path khi tạo dữ liệu cá nhân — lấy từ token.

---

## 3. Envelope phản hồi (`app/schemas/base.py`)

### 3.1. Định nghĩa

```python
from typing import Any, Generic, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")


class BaseResponse(BaseModel, Generic[T]):
    success: bool = True
    data: T | None = None
    message: str = "OK"


class ErrorDetail(BaseModel):
    field: str | None = Field(None, description="Tên field lỗi (dạng 'body.email')")
    message: str


class ErrorResponse(BaseModel):
    success: bool = False
    error_code: str
    message: str
    details: list[ErrorDetail] | dict[str, Any] | None = None


class PaginatedData(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    limit: int
    total_pages: int


class PaginatedResponse(BaseResponse[PaginatedData[T]], Generic[T]):
    pass
```

### 3.2. Ví dụ JSON

Thành công:

```json
{ "success": true, "data": { "id": 42, "name": "Dumbbell Row" }, "message": "OK" }
```

Danh sách phân trang:

```json
{
  "success": true,
  "data": { "items": [ { "id": 42, "name": "Dumbbell Row" } ], "total": 71, "page": 1, "limit": 20, "total_pages": 4 },
  "message": "OK"
}
```

Lỗi:

```json
{
  "success": false,
  "error_code": "VALIDATION_ERROR",
  "message": "Dữ liệu không hợp lệ",
  "details": [ { "field": "body.weight_kg", "message": "Giá trị phải nằm trong khoảng 20–500" } ]
}
```

- `204 No Content` không có body (không bọc envelope).
- `message` là chuỗi tiếng Việt thân thiện cho người dùng, **có thể thay đổi** — client không được dựa vào nó để rẽ nhánh (dùng `error_code`).
- Endpoint trả file/stream (ảnh, video) không bọc envelope; lỗi của chúng vẫn dùng `ErrorResponse`.

### 3.3. Bảng status code & `error_code`

| HTTP | `error_code` | Khi nào |
|:-:|---|---|
| 400 | `BAD_REQUEST` | Yêu cầu sai logic nghiệp vụ không thuộc nhóm khác |
| 401 | `INVALID_CREDENTIALS` `TOKEN_EXPIRED` `TOKEN_INVALID` `TOKEN_REUSED` | Xem doc 04, mục 5 |
| 403 | `PERMISSION_DENIED` `ACCOUNT_DISABLED` `EMAIL_NOT_VERIFIED` | Xem doc 04 |
| 404 | `NOT_FOUND` | Không tồn tại / không thuộc user / đã xoá mềm |
| 409 | `CONFLICT` `EMAIL_ALREADY_EXISTS` | Trùng dữ liệu / vi phạm ràng buộc duy nhất / trạng thái không cho phép |
| 422 | `VALIDATION_ERROR` `WEAK_PASSWORD` | Sai kiểu/khoảng giá trị (Pydantic, CHECK DB) |
| 423 | `ACCOUNT_LOCKED` | Tài khoản bị khoá |
| 429 | `RATE_LIMITED` | Vượt giới hạn tần suất |
| 500 | `INTERNAL_SERVER_ERROR` | Lỗi không lường trước (KHÔNG trả stack trace) |
| 503 | `SERVICE_UNAVAILABLE` | Phụ thuộc ngoài hỏng (DB/Redis/AI service) |

Thêm `error_code` mới: viết hoa, `SNAKE_CASE`, thêm vào bảng này trong cùng PR; ưu tiên tái sử dụng mã có sẵn. Ràng buộc DB bị vi phạm (unique, FK, CHECK) PHẢI được dịch sang `409 CONFLICT`/`422 VALIDATION_ERROR`, KHÔNG để lộ `500`.

---

## 4. Tài liệu API với Swagger/OpenAPI

- Swagger UI `/docs` · ReDoc `/redoc` · schema `/openapi.json`. `docs_url`/`redoc_url` cấu hình ở `main.py`. Ở production NÊN tắt `/docs` hoặc đặt sau xác thực (đặt qua `Settings`).
- Mỗi endpoint PHẢI có đủ:

| Thuộc tính | Yêu cầu |
|---|---|
| `tags` | Một trong: `Auth`, `Users`, `Exercises`, `Equipment`, `Workouts`, `Body`, `Gallery`, `AI`, `Reports`, `Health` |
| `summary` | Ngắn gọn, tiếng Việt, ≤ 80 ký tự |
| `description` | Quy tắc nghiệp vụ + **quyền yêu cầu** (công khai / đăng nhập / permission) |
| `response_model` | Luôn khai báo, dạng `BaseResponse[X]` hoặc `PaginatedResponse[X]` |
| `status_code` | Đúng mục 2.1 |
| `responses` | Liệt kê các lỗi có thể xảy ra (`ErrorResponse`) kèm `error_code` trong `description` |
| Ví dụ | `json_schema_extra={"example": …}` trong schema, dùng dữ liệu thực tế (ID seed, đơn vị SI) |

- Quy tắc đặt tên schema Pydantic (`app/schemas/<domain>.py`):
  - Request: `[Action][Domain]Request` — `CreateWorkoutSessionRequest`, `UpdateBodyMeasurementRequest`.
  - Response: `[Domain]Response` — `WorkoutSessionResponse`; danh sách tóm tắt: `[Domain]SummaryResponse`.
  - Thành phần dùng lại: `[Domain]Schema` — `ExerciseSchema`.
  - Dùng Pydantic v2: `model_config = ConfigDict(from_attributes=True)`; ràng buộc bằng `Field(ge=…, le=…, max_length=…)` khớp CHECK của DB.
- NÊN lưu bản chụp `docs/api/openapi.json` (sinh bằng script `scripts/export_openapi.py`) cập nhật mỗi khi đổi contract, để FE sinh type (openapi-typescript) và review diff dễ hơn.

---

## 5. Mock API

Mục đích: Frontend làm việc ngay khi schema được duyệt.

### 5.1. Quy tắc

1. Mock PHẢI cùng route, cùng `response_model`, cùng status code với bản thật — để khi thay logic thật, FE không phải sửa gì.
2. `summary` có tiền tố **`[MOCK]`** và `description` mở đầu bằng `🚧 MOCK DATA — chưa nối cơ sở dữ liệu`. Có comment `# TODO(mock): thay bằng service thật` ngay trên hàm.
3. Dữ liệu mock đặt trong `app/mocks/<domain>.py` (không rải trong endpoint). Dữ liệu PHẢI hợp lệ với schema và dùng **ID thật của seed** để FE gọi mock và gọi thật cho ra dữ liệu giống nhau:
   - Test users: `5eed0000-0000-4000-8000-0000000000NN` (`NN` theo persona, ví dụ `…03` = demo).
   - Giáo án mẫu: `5eed1000-0000-4000-8000-0000000000NN`.
   - Bài tập, thiết bị, nhóm cơ: dùng `id`/`slug` có trong `seeds/03_exercises.sql`, `02_reference.sql`.
4. Mock PHẢI mô phỏng được: ít nhất **1 trường hợp thành công**, **1 danh sách rỗng** (nếu là list), và **1 lỗi tiêu biểu** (kích hoạt bằng một giá trị đầu vào quy ước, ví dụ id `999999` → `404 NOT_FOUND`, được ghi trong `description`).
5. Mock của endpoint yêu cầu đăng nhập vẫn PHẢI dùng `Depends(get_current_user)`/`require_permission` thật (xem doc 04), để FE kiểm thử luồng token.
6. Không để mock chạm DB hay dịch vụ ngoài. Khi nối logic thật: xoá `[MOCK]`, xoá hàm mock (hoặc giữ ở `mocks/` để dùng cho test), cập nhật PR.

### 5.2. Mẫu

```python
# app/api/v1/endpoints/exercises.py
@router.get(
    "/{exercise_id}",
    response_model=BaseResponse[ExerciseDetailResponse],
    summary="[MOCK] Chi tiết bài tập",
    description="🚧 MOCK DATA — chưa nối cơ sở dữ liệu. Công khai với người đã đăng nhập (`exercise:read`). "
                "id=999999 trả 404 NOT_FOUND.",
    responses={404: {"model": ErrorResponse, "description": "NOT_FOUND"}},
    tags=["Exercises"],
)
async def get_exercise(exercise_id: int, user=Depends(require_permission("exercise", "read"))):
    # TODO(mock): thay bằng exercise_service.get_detail(db, exercise_id)
    if exercise_id == 999999:
        raise NotFoundException("Không tìm thấy bài tập")
    return BaseResponse(data=mocks.exercises.DUMBBELL_ROW_DETAIL)
```

---

## 6. Cấu trúc code, tầng & phân công

### 6.1. Tầng (bắt buộc)

```
api (endpoints)  ──►  services  ──►  crud  ──►  models (SQLAlchemy)
   HTTP, validate,      nghiệp vụ,      truy vấn DB,       ánh xạ bảng
   quyền, envelope      transaction     không nghiệp vụ    (khớp DB)
```

- **Endpoint mỏng:** chỉ nhận request, gọi dependency (auth, db), gọi service, trả envelope. KHÔNG viết SQL/ORM hay logic nghiệp vụ trong endpoint.
- **Service:** chứa nghiệp vụ và **ranh giới transaction** (một request = một transaction; `commit` ở service, không ở crud). Ném `AppException`.
- **CRUD:** kế thừa `CRUDBase` (`app/crud/base.py`), chỉ truy vấn; không biết gì về HTTP.
- Truy vấn phức tạp/dẫn xuất ưu tiên gọi **view/hàm SQL có sẵn** (xem mục 2.2) qua `text()`/`select(func.…)` thay vì tái hiện bằng ORM.
- Tất cả I/O là `async`. KHÔNG dùng thư viện chặn (requests, open() lớn) trong request; gọi AI service/S3 qua `httpx.AsyncClient`/thread executor.

### 6.2. Layout mỗi domain

```
backend/app/
  api/v1/endpoints/<domain>.py      # route, đăng ký trong api/v1/router.py
  schemas/<domain>.py               # Pydantic Request/Response
  services/<domain>_service.py      # nghiệp vụ
  crud/<domain>.py                  # truy vấn
  models/<domain>.py                # SQLAlchemy model (schema-qualified)
  mocks/<domain>.py                 # dữ liệu mock (mục 5)
backend/tests/{unit,integration}/test_<domain>.py
```

Model SQLAlchemy PHẢI: khai báo đúng schema (`__table_args__ = {"schema": "training"}`), khớp tên bảng/cột/kiểu với DB, dùng `naming_convention` của `Base` trùng quy ước `pk_/fk_/uq_/ck_/ix_`, KHÔNG gọi `Base.metadata.create_all()`. Cột dẫn xuất (BMI, volume…) KHÔNG được thêm vào model.

### 6.3. Tiền tố route & phân công module (một route chỉ thuộc một owner)

> Tiền tố dưới đây đã **chốt** để tránh trùng route. Endpoint chi tiết do owner định nghĩa qua Schema PR. Cột "Người phụ trách" nhóm điền ngay Tuần 1.

| Module | Tiền tố route | Chức năng đề tài | Schema DB chính | Người phụ trách |
|---|---|---|---|---|
| Auth & Users | `/auth`, `/users` | — | `auth` | `@TODO` |
| Catalog / Wiki | `/exercises`, `/equipment`, `/muscle-groups`, `/plan-templates` | 1 (Exercise Wiki), 7 (tra cứu theo thiết bị) | `catalog`, `training` (giáo án mẫu) | `@TODO` |
| Training & Recovery | `/workout-plans`, `/scheduled-workouts`, `/workout-sessions`, `/recovery` | 2 (Routine), 6 (ghi set/rep) | `training` | `@TODO` |
| Body & Dashboard | `/body` (`/measurements`, `/profile`, `/goals`, `/circumferences`), `/dashboard` | 3 | `body`, view `training` | `@TODO` |
| Gallery & Media | `/media`, `/progress-photos`, `/photo-comparisons` | 4 | `media` | `@TODO` |
| AI (API cầu nối) | `/ai/pose-analyses`, `/ai/video-jobs`, `/ai/equipment-scans` | 5, 6, 7 | `ai` | `@TODO` |
| Reports | `/reports` | 3 (xuất báo cáo tuần), `analytics` | `analytics` | `@TODO` |
| Health & hạ tầng | `/health` | — | — | Core owner |

Quy tắc:
- Hai module cần dữ liệu của nhau thì gọi qua **service** của module kia (import service), KHÔNG import crud/model chéo module để sửa dữ liệu.
- Nếu một endpoint không thuộc tiền tố nào → hỏi nhóm trước khi tạo; không tự thêm tiền tố mới.
- Tính năng **Food Control / dinh dưỡng (calo, macro) NGOÀI PHẠM VI** ở phiên bản hiện tại (DB đã loại bỏ). Dashboard chỉ gồm cân nặng, % mỡ, số đo vòng, BMI/BMR/TDEE, tiến độ giáo án. Nếu nhóm quyết định đưa vào, PHẢI bắt đầu bằng thiết kế bảng ở `docs/database/` trước.

---

## 7. Phần Core / Shared

### 7.1. Người phụ trách

- Core owner = **thành viên có kinh nghiệm nhất của nhóm** (`@TODO` ghi tên). Chịu trách nhiệm toàn bộ file ở mục 7.2.
- Các thành viên khác KHÔNG sửa trực tiếp file core. Cần thay đổi → mở PR, gắn Core owner làm reviewer bắt buộc.
- Thời hạn: hoàn thành toàn bộ mục 7.2 trong **Tuần 1**; trong lúc đó các module khác chỉ làm Schema/Mock (không phụ thuộc DB).

### 7.2. Thứ tự thực hiện

| # | File | Nội dung |
|:-:|---|---|
| 1 | `app/core/config.py` | `Settings` (pydantic-settings) + `get_settings()` duy nhất; thêm `CORS_ORIGINS`, `REQUIRE_EMAIL_VERIFICATION`, ngưỡng khoá tài khoản |
| 2 | `app/core/database.py` | Engine async, `get_db`, `Base` với `naming_convention`; (Mongo: **chưa dùng**, không khởi tạo) |
| 3 | `app/core/redis_client.py` | Kết nối Redis async + hàm `get_redis` dùng cho cache quyền, rate limit |
| 4 | `app/core/exceptions.py` | `AppException` + các lớp con + exception handlers (mục 7.4) |
| 5 | `app/middleware/logging.py` | Request ID, log JSON (mục 7.5) |
| 6 | `app/schemas/base.py` | Envelope mục 3 |
| 7 | `app/models/enums.py` | Toàn bộ enum mục 2.3 |
| 8 | `app/core/security.py` | Theo doc 04, mục 8.2 |
| 9 | `app/core/dependencies.py` | Theo doc 04, mục 8.3 |
| 10 | `app/main.py` + `api/v1/router.py` | Gắn handler, middleware, router; health check thật |

### 7.3. Cấu hình

- Một cách duy nhất để lấy cấu hình: `from app.core.config import get_settings`; KHÔNG `os.environ[...]` rải rác, KHÔNG tạo `Settings()` nơi khác.
- Biến môi trường khớp `backend/.env.example` (`POSTGRES_*`, `REDIS_*`, `JWT_*`, `AWS_*`, `AI_SERVICE_URL`…). Thêm biến mới: cập nhật `.env.example` cùng PR; giá trị mặc định chỉ dùng cho dev.
- CORS lấy từ `settings.CORS_ORIGINS` (danh sách); `*` chỉ cho `APP_ENV=development`.
- File `.env` KHÔNG commit (đã trong `.gitignore`).

### 7.4. Xử lý lỗi chung

Thay `HTTPException` rải rác bằng một hệ thống lỗi duy nhất:

```python
# app/core/exceptions.py
class AppException(Exception):
    def __init__(self, status_code: int, error_code: str, message: str, details=None, headers=None):
        self.status_code, self.error_code, self.message = status_code, error_code, message
        self.details, self.headers = details, headers


class NotFoundException(AppException):
    def __init__(self, message="Không tìm thấy tài nguyên", error_code="NOT_FOUND", details=None):
        super().__init__(404, error_code, message, details)

class ConflictException(AppException):
    def __init__(self, message="Dữ liệu đã tồn tại", error_code="CONFLICT", details=None):
        super().__init__(409, error_code, message, details)

class ForbiddenException(AppException):
    def __init__(self, message="Không có quyền truy cập", error_code="PERMISSION_DENIED", details=None):
        super().__init__(403, error_code, message, details)

class UnauthorizedException(AppException):
    def __init__(self, message="Chưa đăng nhập hoặc token hết hạn", error_code="TOKEN_INVALID", details=None):
        super().__init__(401, error_code, message, details, headers={"WWW-Authenticate": "Bearer"})

class BadRequestException(AppException):
    def __init__(self, message="Yêu cầu không hợp lệ", error_code="BAD_REQUEST", details=None):
        super().__init__(400, error_code, message, details)
```

Các handler đăng ký trong `main.py`:

| Bắt | Trả |
|---|---|
| `AppException` | `status_code` + `ErrorResponse(error_code, message, details)` |
| `RequestValidationError` | `422` + `VALIDATION_ERROR` + `details=[{field:"body.x", message}]` |
| `IntegrityError` (SQLAlchemy) | Dịch theo tên constraint: `uq_*` → `409 CONFLICT`; `fk_*`/`ck_*` → `409`/`422`; không rõ → `409 CONFLICT` |
| `Exception` | `500 INTERNAL_SERVER_ERROR`, log đầy đủ ở server, **không** lộ stack/SQL ra response |

### 7.5. Logging & middleware

- Mỗi request có `X-Request-ID` (nhận từ client hoặc tự sinh UUID, trả lại trong header response) và được gắn vào mọi dòng log.
- Log định dạng JSON: `timestamp, level, request_id, method, path, status, duration_ms, user_id`.
- KHÔNG log: mật khẩu, token (access/refresh/verification), `Authorization` header, nội dung ảnh/video, toàn bộ body request của `/auth/*`.
- Không dùng `print()`; dùng `logging`.

### 7.6. Health check

`GET /health` PHẢI kiểm tra thật (không trả hard-code): PostgreSQL (`SELECT 1`), Redis (`PING`), AI service (`GET {AI_SERVICE_URL}/health`, thất bại chỉ đánh dấu `degraded`). Trả `200` khi DB + Redis ổn; `503 SERVICE_UNAVAILABLE` khi DB/Redis hỏng. `docker-compose.yml` PHẢI thêm `healthcheck` cho `postgres`/`redis` và `depends_on: condition: service_healthy` cho `backend`.

---

## 8. Cơ sở dữ liệu & Migration (điểm dễ xung đột nhất)

### 8.1. Nguyên tắc

- **Baseline v1:** các file trong `database/postgresql/schemas/`, `views/` là hiện trạng đã thiết kế và đóng băng. KHÔNG sửa trực tiếp sau khi baseline được chốt (Tuần 1). `seeds/` vẫn được bổ sung/chỉnh.
- **Alembic quản lý mọi thay đổi sau baseline.** Thiết lập (Core owner, Tuần 1): `alembic.ini` + `alembic/env.py` (async, `include_schemas=True`, import tất cả model, `target_metadata = Base.metadata`), rồi:
  1. Dựng DB bằng `docker compose up` (chạy `init.sh`).
  2. Tạo revision rỗng `0001_baseline` (không chứa DDL).
  3. `alembic stamp head` để đánh dấu DB hiện tại ở baseline.
- **Mọi thay đổi schema sau đó** (thêm cột/bảng/index, đổi CHECK…): một PR gồm (a) model SQLAlchemy, (b) migration Alembic (`alembic revision --autogenerate`, rà soát tay), (c) cập nhật `docs/database/` (data dictionary/ERD nếu cần), (d) cập nhật seed nếu cần. Reviewer bắt buộc: Core owner.
- Autogenerate KHÔNG hiểu view, hàm, trigger, partial index đặc thù → viết tay bằng `op.execute(...)` và đặt trong migration; không để autogenerate xoá chúng.
- Model phải khớp DB: CI NÊN chạy `alembic check` (hoặc so sánh metadata) trên DB dựng từ `init.sh`.

### 8.2. Dựng & dựng lại DB local

| Việc | Lệnh |
|---|---|
| Khởi động Postgres/Redis/Mongo + dựng DB lần đầu (có seed test) | `docker compose up -d postgres redis mongodb` |
| Tắt seed test | đặt `SW_SEED_TEST=false` trong môi trường của service `postgres` |
| Dựng lại từ đầu (xoá dữ liệu!) | `docker compose down -v` rồi `docker compose up -d postgres` |
| Kiểm tra schema/seed | chạy `database/postgresql/tools/verify_schema.sql`, `verify_seed.sql` (không được có dòng `FAIL`) |

- `init.sh` chỉ chạy lần đầu khi volume rỗng. Muốn nạp lại seed phải xoá volume `postgres_data`.
- Mỗi thành viên có DB local riêng; KHÔNG dùng chung một DB để dev/test.

### 8.3. Quy ước (nhắc lại từ `docs/database/design-overview.md`)

`snake_case`, bảng số nhiều, `timestamptz` UTC, SI, xoá mềm bằng `deleted_at`, FK nào cũng có index, `COMMENT ON` tiếng Việt cho bảng/cột mới, tên ràng buộc `pk_/fk_/uq_/ck_/ix_/brin_`.

---

## 9. Quy trình Git

### 9.1. Nhánh

```
main     ← production, chỉ merge từ develop (có tag), KHÔNG push trực tiếp
develop  ← tích hợp, KHÔNG push trực tiếp (chỉ qua PR)
  ├─ feature/<domain>-<mô-tả>    vd: feature/exercise-search-api
  ├─ fix/<domain>-<mô-tả>
  ├─ chore/<mô-tả>
  └─ docs/<mô-tả>
```

- **Hành động Tuần 1:** hiện repo mới có `main`. Core owner tạo `develop` từ `main` và bật branch protection cho `main` + `develop` (yêu cầu PR, ≥ 1 approval, CI xanh).
- Nhánh phải ngắn hạn (≤ ~3 ngày làm việc); thường xuyên `git pull --rebase origin develop` để giảm xung đột. KHÔNG sửa cùng một file với người khác mà không báo (đặc biệt `router.py`, `enums.py`, `.env.example`, `requirements.txt` — dễ conflict; xem 9.4).

### 9.2. Commit

Định dạng: `<type>(<scope>): <mô tả ngắn, thể mệnh lệnh>`

| `type` | Dùng khi |
|---|---|
| `feat` | Tính năng mới |
| `fix` | Sửa lỗi |
| `docs` | Tài liệu |
| `refactor` | Tái cấu trúc, không đổi hành vi |
| `test` | Thêm/sửa test |
| `chore` | Build, dependency, cấu hình |
| `design` | Thiết kế (DB, kiến trúc) — giữ cho tương thích lịch sử commit hiện có |
| `style` | Format không ảnh hưởng logic |

`scope` (chọn **một**): `auth` · `exercise` · `workout` · `body` · `gallery` · `ai` · `report` · `core` · `db` · `docs` · `infra` · `frontend`.
Ví dụ: `feat(exercise): thêm API tìm kiếm bài tập theo nhóm cơ` · `fix(auth): xoay vòng refresh token trong transaction` · `docs(db): cập nhật data dictionary`.

> `CONTRIBUTING.md` cũ liệt kê scope `backend/frontend/ai/db/docs/infra`; danh sách trên thay thế nó (`CONTRIBUTING.md` được cập nhật theo doc này). Không dùng ký tự `<` `>` trong tiêu đề commit.

### 9.3. Pull Request

- PR vào `develop`. Dùng template `.github/PULL_REQUEST_TEMPLATE/pull_request_template.md`.
- Yêu cầu: ≥ **1 reviewer** (người khác tác giả), **không tự merge**, CI xanh, không conflict, mô tả rõ thay đổi + cách kiểm tra.
- PR chỉ làm **một việc**, NÊN < 400 dòng thay đổi (ngoại trừ dữ liệu sinh tự động/seed).
- Merge bằng **squash merge** để lịch sử `develop` gọn; tiêu đề squash theo định dạng commit ở 9.2.

### 9.4. File dễ xung đột — cách xử lý

| File | Quy tắc |
|---|---|
| `backend/requirements.txt` | Thêm thư viện ở dòng riêng, theo nhóm, ghim phiên bản; báo kênh chung khi nâng phiên bản chung |
| `api/v1/router.py` | Mỗi module chỉ thêm đúng 1 dòng `include_router` của mình (theo thứ tự bảng chữ cái) |
| `models/enums.py` | Chỉ thêm enum mới ở cuối nhóm của module mình; enum đã có do Core owner quản |
| `.env.example` | Thêm biến theo nhóm có comment; báo kênh chung |
| `database/postgresql/seeds/*` | Dùng file riêng cho dữ liệu mới thay vì sửa file của người khác |

---

## 10. Kiểm thử

- Công cụ: `pytest` + `pytest-asyncio` + `httpx.AsyncClient` (fixture trong `tests/conftest.py`). Lint `ruff`, kiểu `mypy app/`.
- **Mỗi endpoint ≥ 2 test**: 1 thành công + 1 lỗi (sai input / thiếu quyền / không tồn tại). Endpoint có quyền PHẢI test thêm "không đăng nhập" và "thiếu permission".
- Coverage tối thiểu **70%** (CI chạy `pytest --cov`).
- **Test chạy trên PostgreSQL thật** được dựng bằng `init.sh` (seed test bật), KHÔNG dùng SQLite (khác kiểu `citext`, schema, enum). Mỗi test chạy trong transaction rollback hoặc dùng DB dựng lại; test KHÔNG được phụ thuộc thứ tự chạy hay dữ liệu do test khác tạo.
- Fixture chuẩn (`tests/conftest.py`, Core owner viết):
  - `client` — `AsyncClient` gắn app.
  - `db` — session có rollback.
  - `auth_headers(persona)` — đăng nhập persona seed (`demo`, `admin`, `editor`, `newbie`…) và trả `{"Authorization": "Bearer …"}`.
- Đặt tên: `tests/unit/test_<domain>_<chủ_đề>.py`, `tests/integration/test_<domain>_api.py`; hàm `test_<hành_động>_<điều_kiện>_<kết_quả>`.
- Test mock: khi còn `[MOCK]`, test chỉ cần kiểm tra schema; khi nối logic thật, bổ sung test nghiệp vụ.

---

## 11. Checklist trước khi merge & Definition of Done

### 11.1. Checklist PR

**Chất lượng code**
- [ ] `ruff check .` và `mypy app/` sạch
- [ ] Không còn `print()`, không `# type: ignore` không giải thích, không code chết
- [ ] Hàm/lớp công khai có docstring ngắn

**Chuẩn API**
- [ ] Phản hồi theo envelope (mục 3); đúng status code (mục 2.1)
- [ ] Swagger đủ `tags`, `summary`, `description`, `response_model`, `responses`, ví dụ (mục 4)
- [ ] Đúng quy ước ID/đơn vị/thời gian/enum (mục 2); không tự thêm tiền tố route (mục 6.3)
- [ ] Endpoint cần đăng nhập dùng `get_current_user`/`require_permission`; dữ liệu cá nhân kiểm tra chủ sở hữu

**Kiểm thử**
- [ ] Test mới ≥ 2 case/endpoint, toàn bộ test xanh, coverage ≥ 70%

**CSDL**
- [ ] Model khớp DB; nếu đổi schema: có migration Alembic + cập nhật `docs/database/`
- [ ] Đã chạy `alembic upgrade head` cục bộ thành công

**Bảo mật**
- [ ] Không hard-code bí mật; `.env.example` đã cập nhật nếu thêm biến
- [ ] Không log dữ liệu nhạy cảm; không trả `password_hash`/token ngoài luồng cho phép

### 11.2. Definition of Done của một endpoint

1. Schema PR được duyệt → 2. Mock PR (≤ 24 giờ) → 3. Logic thật (service/crud) → 4. Test + checklist 11.1 → 5. Gỡ `[MOCK]` → 6. Cập nhật `docs/api/openapi.json` (nếu dùng) → 7. Thông báo FE trên kênh chung.

---

## 12. Việc cần làm Tuần 1 (Core owner & cả nhóm)

Các lệch giữa code hiện tại và chuẩn trong doc 04/05 (đã đối chiếu với repo ngày 2026-10-08):

| # | Việc | Người phụ trách |
|:-:|---|---|
| 1 | Điền bảng phân công module (mục 6.3) và tên Core owner (mục 7.1) | Cả nhóm |
| 2 | Tạo nhánh `develop`, bật branch protection; cập nhật `CONTRIBUTING.md` theo mục 9 | Core owner |
| 3 | Hoàn thành mục 7.2 (config → … → main.py) | Core owner |
| 4 | Thay `exceptions.py` hiện tại (các lớp `HTTPException` thiếu `error_code`) bằng `AppException` (7.4) | Core owner |
| 5 | Sửa `security.py`, `dependencies.py` theo doc 04, mục 8.2–8.3 | Core owner (+ Auth owner review) |
| 6 | `main.py`: bật `include_router`, CORS lấy từ settings, health check thật (7.6) | Core owner |
| 7 | `api/v1/router.py`: xoá nhắc tới module `nutrition` (ngoài phạm vi); thêm đúng các module ở 6.3 | Core owner |
| 8 | `config.py`: dùng một cách lấy cấu hình (`get_settings()`); thêm biến mới; chặn secret mặc định ngoài dev | Core owner |
| 9 | Thiết lập Alembic + `0001_baseline` + `alembic stamp head` (mục 8.1) | Core owner |
| 10 | `docker-compose.yml`: thêm `healthcheck` + `depends_on: service_healthy`; tạo `backend/.env` từ `.env.example` (ghi hướng dẫn) | Core owner |
| 11 | Viết `app/models/enums.py` (2.3) và model SQLAlchemy nền (`Base`, naming_convention) | Core owner |
| 12 | `tests/conftest.py`: fixture `client`, `db`, `auth_headers` | Core owner |
| 13 | Sửa các tham chiếu hỏng trong README (liên kết `docs/guides/*`, `LICENSE`, `docker-compose.dev.yml` → `docker-compose.yml`) và Dockerfile `ai-services` (`src/app.py` chưa có), CI `ai-services` (thiếu `ruff` trong requirements) | Cả nhóm / AI owner |
| 14 | Cả nhóm đọc xong doc 04, 05 và `docs/database/design-overview.md` | Cả nhóm |

---

## 13. Những điều KHÔNG ĐƯỢC làm

- ❌ Đợi Backend xong logic mới làm Frontend; hoặc để schema đã duyệt quá 24 giờ chưa có mock.
- ❌ Đổi/xoá field của contract đã merge mà không gắn `breaking-change` và báo FE.
- ❌ Viết SQL/logic nghiệp vụ trong endpoint; import crud/model chéo module để ghi dữ liệu.
- ❌ Sửa trực tiếp file `database/postgresql/schemas/*` sau khi baseline chốt; dùng `create_all()`.
- ❌ Tự tính BMI/BMR/TDEE/volume/1RM bằng công thức khác với view SQL.
- ❌ Dùng `HTTPException` trực tiếp; trả lỗi không theo `ErrorResponse`; so khớp `message` thay vì `error_code`.
- ❌ Dùng ID sai kiểu (UUID thay số nguyên hoặc ngược lại); đơn vị không phải SI trong API.
- ❌ Push thẳng `main`/`develop`; tự merge PR của mình; merge khi CI đỏ.
- ❌ Commit `.env`, khoá bí mật, dữ liệu cá nhân thật, file model/dataset lớn.
- ❌ Dùng chung một database dev cho cả nhóm.
