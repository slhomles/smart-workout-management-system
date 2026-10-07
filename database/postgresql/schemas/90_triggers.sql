-- =====================================================================
-- Smart Workout AI — 90: Gắn trigger updated_at cho mọi bảng có cột updated_at
-- Chạy lại an toàn: bỏ qua bảng đã có trigger.
-- =====================================================================

DO $$
DECLARE
    r record;
BEGIN
    FOR r IN
        SELECT c.table_schema, c.table_name
        FROM information_schema.columns c
        JOIN information_schema.tables t
          ON t.table_schema = c.table_schema
         AND t.table_name = c.table_name
         AND t.table_type = 'BASE TABLE'
        WHERE c.column_name = 'updated_at'
          AND c.table_schema IN ('auth', 'media', 'catalog', 'body', 'training', 'ai', 'analytics')
        ORDER BY c.table_schema, c.table_name
    LOOP
        IF NOT EXISTS (
            SELECT 1 FROM pg_trigger tg
            WHERE tg.tgrelid = format('%I.%I', r.table_schema, r.table_name)::regclass
              AND tg.tgname = 'trg_set_updated_at'
        ) THEN
            EXECUTE format(
                'CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON %I.%I FOR EACH ROW EXECUTE FUNCTION util.set_updated_at()',
                r.table_schema, r.table_name);
        END IF;
    END LOOP;
END
$$;
