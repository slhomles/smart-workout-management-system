-- =====================================================================
-- Smart Workout AI — Sinh từ điển dữ liệu (Markdown) từ catalog PostgreSQL
--   psql -At -U smart_workout -d smart_workout_db -f tools/data_dictionary.sql > docs/database/data-dictionary.md
-- Nguồn mô tả là COMMENT ON trong các file schemas/ → sửa mô tả ở đó, rồi sinh lại.
-- =====================================================================
\set QUIET on
\pset pager off
\pset format unaligned
\pset tuples_only on

WITH
schemas AS (
    SELECT n.oid, n.nspname, s.ord, obj_description(n.oid, 'pg_namespace') AS descr
    FROM pg_namespace n
    JOIN (VALUES ('auth', 1), ('media', 2), ('catalog', 3), ('body', 4), ('training', 5), ('ai', 6), ('analytics', 7))
         AS s(nspname, ord) ON s.nspname = n.nspname
),
tbls AS (
    SELECT c.oid, s.nspname, s.ord AS sord, c.relname,
           coalesce(obj_description(c.oid, 'pg_class'), '') AS descr
    FROM pg_class c JOIN schemas s ON s.oid = c.relnamespace
    WHERE c.relkind = 'r'
),
cols AS (
    SELECT t.oid AS relid, a.attnum, a.attname,
           format_type(a.atttypid, a.atttypmod) AS dtype,
           CASE WHEN a.attnotnull THEN 'NOT NULL' ELSE '' END AS nullable,
           coalesce(pg_get_expr(d.adbin, d.adrelid), '') AS dflt,
           CASE WHEN a.attidentity IN ('a', 'd') THEN 'IDENTITY' ELSE '' END AS ident,
           coalesce(col_description(t.oid, a.attnum), '') AS descr
    FROM tbls t
    JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum > 0 AND NOT a.attisdropped
    LEFT JOIN pg_attrdef d ON d.adrelid = t.oid AND d.adnum = a.attnum
),
col_keys AS (
    SELECT k.conrelid AS relid, u.attnum,
           string_agg(
               CASE k.contype
                   WHEN 'p' THEN 'PK'
                   WHEN 'u' THEN 'UQ'
                   WHEN 'f' THEN 'FK → ' || k.confrelid::regclass::text
               END, '<br>' ORDER BY k.contype DESC, k.conname) AS keys
    FROM pg_constraint k
    CROSS JOIN LATERAL unnest(k.conkey) AS u(attnum)
    WHERE k.contype IN ('p', 'u', 'f') AND k.conrelid IN (SELECT oid FROM tbls)
    GROUP BY k.conrelid, u.attnum
),
lines AS (
    -- Tiêu đề
    SELECT 0 AS s, 0 AS t, 0 AS p, 0 AS q,
           E'# Từ điển dữ liệu — Smart Workout AI\n\n'
        || E'> Tài liệu **tự sinh** từ `COMMENT ON` trong PostgreSQL bằng `database/postgresql/tools/data_dictionary.sql`. '
        || E'Không sửa tay — sửa mô tả trong `database/postgresql/schemas/*.sql` rồi sinh lại.\n\n'
        || E'Quy ước cột **Khoá**: `PK` khoá chính, `UQ` thuộc ràng buộc unique, `FK → bảng` khoá ngoại. '
        || E'Các unique index có điều kiện (partial) và CHECK được liệt kê dưới mỗi bảng.\n\n'
        || E'## Mục lục\n\n'
        || (SELECT string_agg(format('- [Schema `%s`](#schema-%s) — %s bảng', s.nspname, s.nspname,
                                     (SELECT count(*) FROM tbls t WHERE t.nspname = s.nspname)), E'\n' ORDER BY s.ord)
            FROM schemas s)
        || E'\n- [Views, materialized views & hàm](#views-materialized-views--hàm)\n' AS line
    UNION ALL
    -- Đầu mỗi schema + bảng tóm tắt
    SELECT s.ord, 0, 0, 0,
           format(E'\n## Schema `%s`\n\n%s\n\n| Bảng | Mô tả |\n|---|---|\n', s.nspname, coalesce(s.descr, ''))
        || (SELECT string_agg(format('| [`%s`](#%s) | %s |', t.relname, t.nspname || t.relname,
                                     replace(t.descr, '|', '\|')), E'\n' ORDER BY t.relname)
            FROM tbls t WHERE t.nspname = s.nspname)
    FROM schemas s
    UNION ALL
    -- Đầu mỗi bảng
    SELECT t.sord, t.oid::int, 0, 0,
           format(E'\n### `%s.%s`\n\n%s\n\n| # | Cột | Kiểu | Null | Mặc định | Khoá | Mô tả |\n|---|---|---|---|---|---|---|',
                  t.nspname, t.relname, t.descr)
    FROM tbls t
    UNION ALL
    -- Cột
    SELECT t.sord, t.oid::int, 1, c.attnum,
           format('| %s | `%s` | %s | %s | %s | %s | %s |',
                  c.attnum, c.attname, c.dtype, c.nullable,
                  replace(nullif(concat_ws(' ', nullif(c.ident, ''), nullif(c.dflt, '')), ''), '|', '\|'),
                  coalesce(ck.keys, ''), replace(c.descr, '|', '\|'))
    FROM tbls t
    JOIN cols c ON c.relid = t.oid
    LEFT JOIN col_keys ck ON ck.relid = t.oid AND ck.attnum = c.attnum
    UNION ALL
    -- CHECK + unique nhiều cột
    SELECT t.sord, t.oid::int, 2, 0,
           E'\n**Ràng buộc:**\n\n'
        || string_agg(format('- `%s` — `%s`', k.conname, replace(pg_get_constraintdef(k.oid), '|', '\|')), E'\n' ORDER BY k.contype, k.conname)
    FROM tbls t
    JOIN pg_constraint k ON k.conrelid = t.oid AND (k.contype = 'c' OR (k.contype = 'u' AND cardinality(k.conkey) > 1))
    GROUP BY t.sord, t.oid
    UNION ALL
    -- Index (bỏ index sinh ra từ PK/UNIQUE constraint)
    SELECT t.sord, t.oid::int, 3, 0,
           E'\n**Index:**\n\n'
        || string_agg(format('- `%s` — `%s`', ic.relname,
                             regexp_replace(pg_get_indexdef(i.indexrelid), '^CREATE (UNIQUE )?INDEX \S+ ON \S+ ', '\1')),
                      E'\n' ORDER BY ic.relname)
    FROM tbls t
    JOIN pg_index i ON i.indrelid = t.oid
    JOIN pg_class ic ON ic.oid = i.indexrelid
    WHERE NOT EXISTS (SELECT 1 FROM pg_constraint k WHERE k.conindid = i.indexrelid AND k.contype IN ('p', 'u'))
    GROUP BY t.sord, t.oid
    UNION ALL
    -- Trigger nghiệp vụ (bỏ trigger updated_at & trigger nội bộ của FK)
    SELECT t.sord, t.oid::int, 4, 0,
           E'\n**Trigger:**\n\n'
        || string_agg(format('- `%s` → `%s()` — %s', tg.tgname, p.proname, coalesce(obj_description(p.oid, 'pg_proc'), '')),
                      E'\n' ORDER BY tg.tgname)
    FROM tbls t
    JOIN pg_trigger tg ON tg.tgrelid = t.oid AND NOT tg.tgisinternal AND tg.tgname <> 'trg_set_updated_at'
    JOIN pg_proc p ON p.oid = tg.tgfoid
    GROUP BY t.sord, t.oid
    UNION ALL
    -- Views / MV / hàm
    SELECT 99, 0, 0, 0,
           E'\n## Views, materialized views & hàm\n\n| Đối tượng | Loại | Mô tả |\n|---|---|---|\n'
        || (SELECT string_agg(format('| `%s.%s` | %s | %s |', s.nspname, c.relname,
                                     CASE c.relkind WHEN 'v' THEN 'view' ELSE 'materialized view' END,
                                     replace(coalesce(obj_description(c.oid, 'pg_class'), ''), '|', '\|')),
                              E'\n' ORDER BY s.ord, c.relkind, c.relname)
            FROM pg_class c JOIN schemas s ON s.oid = c.relnamespace
            WHERE c.relkind IN ('v', 'm'))
        || E'\n'
        || (SELECT string_agg(format('| `%s.%s(%s)` | hàm | %s |', n.nspname, p.proname,
                                     pg_get_function_identity_arguments(p.oid),
                                     replace(coalesce(obj_description(p.oid, 'pg_proc'), ''), '|', '\|')),
                              E'\n' ORDER BY n.nspname, p.proname)
            FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
            WHERE n.nspname IN ('util', 'catalog', 'analytics') AND p.prokind = 'f'
              AND p.prorettype <> 'trigger'::regtype)
)
SELECT line FROM lines ORDER BY s, t, p, q;
