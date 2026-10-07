# PostgreSQL — Smart Workout AI

Lược đồ CSDL (PostgreSQL 16): 7 schema nghiệp vụ, 51 bảng, chuẩn 3NF.
Tài liệu thiết kế: [`docs/database/`](../../docs/database/design-overview.md).

## Cấu trúc

```
database/postgresql/
├── init.sh                    # Bộ khởi tạo: schemas → views → seeds → refresh MV
├── schemas/                   # DDL (thứ tự theo tiền tố số)
│   ├── 00_extensions_schemas.sql   extensions, schema, timezone UTC
│   ├── 01_common.sql               hàm util, enum dùng chung
│   ├── 02_auth.sql                 tài khoản, RBAC, OAuth, thiết bị, token, log đăng nhập
│   ├── 03_media.sql                sổ đăng ký file Object Storage
│   ├── 04_catalog.sql              Exercise Wiki
│   ├── 05_body.sql                 hồ sơ thể chất, số đo, mục tiêu
│   ├── 06_training.sql             giáo án, lịch, buổi tập, set/rep, phục hồi
│   ├── 07_ai.sql                   phân tích tư thế, job video, nhận diện thiết bị
│   ├── 08_gallery.sql              ảnh tiến độ, so sánh Before/After
│   ├── 09_analytics.sql            báo cáo đã xuất
│   ├── 90_triggers.sql             gắn trigger updated_at
│   └── 99_roles_grants.sql         role sw_app_rw / sw_readonly
├── views/                     # View, hàm nghiệp vụ, materialized view
├── seeds/
│   ├── 01–05_*.sql                 MASTER DATA (mọi môi trường): RBAC, danh mục, 71 bài tập, 6 giáo án mẫu
│   └── 90–99_test_*.sql            DỮ LIỆU TEST: 16 persona, media placeholder, lịch sử tập 6 tháng
└── tools/                     # Chạy tay: kiểm tra schema/seed, sinh từ điển dữ liệu
```

## Khởi tạo bằng Docker (khuyến nghị)

`docker-compose.yml` mount thư mục này vào `/docker-entrypoint-initdb.d`. Image postgres **chỉ chạy `init.sh` khi volume dữ liệu còn trống**:

```bash
docker compose up -d postgres
docker compose logs -f postgres     # chờ dòng "[smart-workout] database initialized"
```

Khi đã có volume cũ và muốn khởi tạo lại (⚠️ **xoá toàn bộ dữ liệu** PostgreSQL local):

```bash
docker compose down
docker volume rm smart_workout_postgres_data   # tên volume = <tên thư mục project>_postgres_data
docker compose up -d postgres
```

Chỉ nạp master data (bỏ toàn bộ `seeds/9*.sql`): đặt `SW_SEED_TEST: "false"` trong `environment` của service `postgres`. **Production phải đặt `false`.**

## Khởi tạo vào một PostgreSQL có sẵn

```bash
export PGHOST=localhost PGPORT=5432 PGUSER=smart_workout PGPASSWORD=... PGDATABASE=smart_workout_db
bash database/postgresql/init.sh
```

Script dừng ngay khi gặp lỗi, mỗi file chạy trong một transaction. Nên chạy trên database trống.

## Dữ liệu test (seeds/9*.sql)

16 persona dùng chung mật khẩu `Demo@123` (bcrypt), UUID cố định `5eed0000-0000-4000-8000-0000000000NN`. Mỗi persona phủ một nhóm tình huống: happy path (`demo@`), lịch sử 6 tháng (`power@`), chững cân, buổi đang tập, tài khoản chưa xác thực / bị khoá / vô hiệu / đã xoá, chỉ OAuth, vai trò hết hạn...
Danh sách đầy đủ, token thô để test và các ca biên: **[docs/database/test-dataset.md](../../docs/database/test-dataset.md)**.

Không có dữ liệu AI (bảng `ai.*`, `recovery_predictions`, `set_rep_events` trống).

## Truy vấn mẫu

```sql
-- Tìm bài tập (không dấu), lọc độ khó ≤ Cơ bản
SELECT * FROM catalog.fn_search_exercises('lung xo', p_max_difficulty_rank => 1::smallint);

-- Bài thay thế cho Dumbbell Row khi khu tạ đơn đang bận
SELECT * FROM catalog.fn_suggest_alternatives(
    (SELECT id FROM catalog.exercises WHERE slug = 'dumbbell-row'),
    ARRAY[(SELECT id FROM catalog.equipment WHERE code = 'dumbbell')]);

-- Heatmap phục hồi của một user
SELECT muscle_code, recovery_pct, remaining_hours, recovery_status
FROM training.v_muscle_recovery_status WHERE user_id = :user_id;

-- BMI / BMR / TDEE mới nhất
SELECT * FROM body.v_latest_body_metrics WHERE user_id = :user_id;

-- Nhãn YOLOv8 → bài tập
SELECT * FROM catalog.fn_exercises_for_ai_label('cable_crossover_machine');

-- Làm mới materialized view (đặt lịch 15–60 phút/lần)
SELECT analytics.refresh_materialized_views();
```

## Công cụ

```bash
# Kiểm tra chất lượng schema (mọi mục "vi phạm" phải trả 0 dòng)
docker compose exec -T postgres psql -U smart_workout -d smart_workout_db < database/postgresql/tools/verify_schema.sql

# Kiểm tra dữ liệu seed theo từng tình huống (không được có dòng FAIL)
docker compose exec -T postgres psql -U smart_workout -d smart_workout_db < database/postgresql/tools/verify_seed.sql

# Sinh lại từ điển dữ liệu sau khi đổi schema / COMMENT
docker compose exec -T postgres psql -At -U smart_workout -d smart_workout_db \
    < database/postgresql/tools/data_dictionary.sql > docs/database/data-dictionary.md
```

## Quy tắc khi sửa lược đồ

1. Thêm/sửa trong file `schemas/` đúng module, giữ quy ước tên `pk_/fk_/uq_/ck_/ix_`.
2. Mỗi bảng và cột mới **phải có** `COMMENT ON`; mỗi cột FK **phải có** index.
3. Không lưu giá trị suy ra được (tổng, đếm, BMI, URL...): tính bằng view trong `views/`.
4. Chạy `tools/verify_schema.sql` và sinh lại `docs/database/data-dictionary.md`.
5. Khi backend dùng Alembic: mọi thay đổi sau baseline đi qua migration (`backend/alembic/versions/`).
