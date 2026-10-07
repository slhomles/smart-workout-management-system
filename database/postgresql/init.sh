#!/usr/bin/env bash
# =====================================================================
# Smart Workout AI — PostgreSQL initializer
#
# Chạy tự động bởi image postgres khi volume dữ liệu còn trống
# (thư mục này được mount vào /docker-entrypoint-initdb.d).
# Có thể chạy tay với biến môi trường PGHOST/PGUSER/PGDATABASE/PGPASSWORD.
#
# Thứ tự: schemas/*.sql → views/*.sql → seeds/*.sql → refresh materialized views
# Mỗi file chạy trong một transaction, dừng ngay khi có lỗi.
# seeds/0*.sql = master data (luôn chạy); seeds/9*.sql = dữ liệu test.
# Đặt SW_SEED_TEST=false để bỏ qua dữ liệu test (môi trường production).
# =====================================================================
set -eo pipefail

SW_DB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SW_DB_USER="${POSTGRES_USER:-${PGUSER:-postgres}}"
SW_DB_NAME="${POSTGRES_DB:-${PGDATABASE:-$SW_DB_USER}}"

sw_psql() {
    psql -v ON_ERROR_STOP=1 --no-psqlrc --quiet \
        --username "$SW_DB_USER" --dbname "$SW_DB_NAME" "$@"
}

sw_apply_dir() {
    local dir="$1" file
    for file in "$SW_DB_DIR/$dir"/*.sql; do
        [ -e "$file" ] || continue
        case "$dir/$(basename "$file")" in
            seeds/9*)
                if [ "${SW_SEED_TEST:-true}" = "false" ]; then
                    echo "[smart-workout] skip   $dir/$(basename "$file") (SW_SEED_TEST=false)"
                    continue
                fi
                ;;
        esac
        echo "[smart-workout] apply  $dir/$(basename "$file")"
        sw_psql --single-transaction --file "$file"
    done
}

sw_apply_dir schemas
sw_apply_dir views
sw_apply_dir seeds

echo "[smart-workout] refresh materialized views"
sw_psql --command "SELECT analytics.refresh_materialized_views(false);"

echo "[smart-workout] database initialized"
