-- =====================================================================
-- Smart Workout AI — Kiểm tra chất lượng schema (chạy tay, KHÔNG nằm trong init)
--   psql -U smart_workout -d smart_workout_db -f tools/verify_schema.sql
-- Mọi truy vấn "vi phạm" phải trả về 0 dòng.
-- =====================================================================
\pset pager off
\set app_schemas '''auth'',''media'',''catalog'',''body'',''training'',''ai'',''analytics'''

\echo '== 1. Số bảng theo schema'
SELECT n.nspname AS schema, count(*) AS tables
FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE c.relkind = 'r' AND n.nspname IN (:app_schemas)
GROUP BY n.nspname ORDER BY n.nspname;

\echo '== 2. [vi phạm] Bảng không có khoá chính'
SELECT c.oid::regclass AS table_name
FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE c.relkind = 'r' AND n.nspname IN (:app_schemas)
  AND NOT EXISTS (SELECT 1 FROM pg_constraint k WHERE k.conrelid = c.oid AND k.contype = 'p');

\echo '== 3. [vi phạm] Khoá ngoại không có index hỗ trợ (cột FK phải là tiền tố của một index)'
SELECT k.conrelid::regclass AS table_name, k.conname
FROM pg_constraint k
JOIN pg_namespace n ON n.oid = k.connamespace
WHERE k.contype = 'f' AND n.nspname IN (:app_schemas)
  AND NOT EXISTS (
      SELECT 1 FROM pg_index i
      WHERE i.indrelid = k.conrelid
        AND (string_to_array(i.indkey::text, ' ')::int2[])[1:cardinality(k.conkey)] @> k.conkey
        AND (string_to_array(i.indkey::text, ' ')::int2[])[1:cardinality(k.conkey)] <@ k.conkey
  )
  -- FK kép mà cột đầu tiên đã có index unique riêng cũng được chấp nhận
  AND NOT EXISTS (
      SELECT 1 FROM pg_index i
      WHERE i.indrelid = k.conrelid AND i.indisunique AND i.indnatts = 1
        AND i.indkey[0] = ANY (k.conkey)
  );

\echo '== 4. [vi phạm] Bảng/view thiếu COMMENT'
SELECT c.oid::regclass AS relation, c.relkind
FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE c.relkind IN ('r', 'v', 'm') AND n.nspname IN (:app_schemas)
  AND obj_description(c.oid, 'pg_class') IS NULL;

\echo '== 5. [vi phạm] Cột của bảng thiếu COMMENT'
SELECT c.oid::regclass AS table_name, a.attname AS column_name
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum > 0 AND NOT a.attisdropped
WHERE c.relkind = 'r' AND n.nspname IN (:app_schemas)
  AND col_description(c.oid, a.attnum) IS NULL;

\echo '== 6. [vi phạm] Tên constraint sai quy ước (pk_/fk_/uq_/ck_)'
SELECT k.conrelid::regclass AS table_name, k.conname, k.contype
FROM pg_constraint k JOIN pg_namespace n ON n.oid = k.connamespace
WHERE n.nspname IN (:app_schemas) AND k.conrelid <> 0
  AND NOT (
      (k.contype = 'p' AND k.conname LIKE 'pk\_%') OR
      (k.contype = 'f' AND k.conname LIKE 'fk\_%') OR
      (k.contype = 'u' AND k.conname LIKE 'uq\_%') OR
      (k.contype = 'c' AND k.conname LIKE 'ck\_%'));

\echo '== 7. [vi phạm] Tên index sai quy ước (pk_/uq_/ix_/brin_)'
SELECT i.indexrelid::regclass AS index_name
FROM pg_index i
JOIN pg_class c ON c.oid = i.indexrelid
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname IN (:app_schemas)
  AND c.relname !~ '^(pk|uq|ix|brin)_';

\echo '== 8. [vi phạm] Bảng có cột updated_at nhưng thiếu trigger trg_set_updated_at'
SELECT c.oid::regclass AS table_name
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
JOIN pg_attribute a ON a.attrelid = c.oid AND a.attname = 'updated_at' AND NOT a.attisdropped
WHERE c.relkind = 'r' AND n.nspname IN (:app_schemas)
  AND NOT EXISTS (SELECT 1 FROM pg_trigger t WHERE t.tgrelid = c.oid AND t.tgname = 'trg_set_updated_at');

\echo '== 9. [vi phạm] Cột kiểu timestamp không có múi giờ'
SELECT c.oid::regclass AS table_name, a.attname
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum > 0 AND NOT a.attisdropped
WHERE c.relkind = 'r' AND n.nspname IN (:app_schemas)
  AND a.atttypid = 'timestamp'::regtype;

\echo '== 10. [vi phạm] Cột kiểu mảng / json (vi phạm 1NF)'
SELECT c.oid::regclass AS table_name, a.attname, format_type(a.atttypid, a.atttypmod) AS data_type
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum > 0 AND NOT a.attisdropped
JOIN pg_type t ON t.oid = a.atttypid
WHERE c.relkind = 'r' AND n.nspname IN (:app_schemas)
  AND (t.typcategory = 'A' OR a.atttypid IN ('json'::regtype, 'jsonb'::regtype));
