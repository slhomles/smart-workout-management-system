-- =====================================================================
-- Smart Workout AI — Views & functions: catalog (Exercise Wiki)
-- =====================================================================

-- ---------------------------------------------------------------------
-- catalog.v_exercise_cards — dữ liệu thẻ bài tập cho màn danh sách
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW catalog.v_exercise_cards AS
SELECT
    e.id                AS exercise_id,
    e.slug,
    e.name,
    e.name_en,
    e.category,
    e.mechanic,
    e.supports_ai_tracking,
    d.code              AS difficulty_code,
    d.name              AS difficulty_name,
    d.rank              AS difficulty_rank,
    (SELECT string_agg(mg.name, ', ' ORDER BY em.activation_ratio DESC, mg.name)
       FROM catalog.exercise_muscles em
       JOIN catalog.muscle_groups mg ON mg.id = em.muscle_group_id
      WHERE em.exercise_id = e.id AND em.role = 'primary')      AS primary_muscles,
    (SELECT string_agg(mg.name, ', ' ORDER BY em.activation_ratio DESC, mg.name)
       FROM catalog.exercise_muscles em
       JOIN catalog.muscle_groups mg ON mg.id = em.muscle_group_id
      WHERE em.exercise_id = e.id AND em.role <> 'primary')     AS secondary_muscles,
    (SELECT string_agg(eq.name, ', ' ORDER BY eq.name)
       FROM catalog.exercise_equipment ee
       JOIN catalog.equipment eq ON eq.id = ee.equipment_id
      WHERE ee.exercise_id = e.id AND NOT ee.is_optional)       AS required_equipment,
    (SELECT em2.media_id
       FROM catalog.exercise_media em2
      WHERE em2.exercise_id = e.id AND em2.media_role = 'thumbnail' AND em2.is_primary) AS thumbnail_media_id
FROM catalog.exercises e
JOIN catalog.difficulty_levels d ON d.id = e.difficulty_level_id
WHERE e.status = 'published'
  AND e.deleted_at IS NULL;

COMMENT ON VIEW catalog.v_exercise_cards IS 'Bài tập đã xuất bản kèm độ khó, nhóm cơ chính/phụ, thiết bị bắt buộc và thumbnail (chuỗi ghép chỉ để hiển thị).';

-- ---------------------------------------------------------------------
-- catalog.fn_search_exercises — tìm kiếm & lọc đa điều kiện (Wiki bước 1–2)
--   p_keyword: khớp tên bài (VI/EN), tên nhóm cơ (kể cả nhóm cha, vd "lưng" → lưng xô),
--              tên/alias thiết bị; không phân biệt dấu & hoa thường.
--   p_muscle_group_ids: lọc theo nhóm cơ (chọn nhóm cha sẽ gồm cả nhóm con).
--   p_primary_only: chỉ tính nhóm cơ đóng vai trò chính.
--   p_available_equipment_ids: chỉ trả bài mà mọi thiết bị BẮT BUỘC đều nằm trong danh sách
--              (bài tự thân luôn thoả). NULL = không lọc thiết bị.
--   p_max_difficulty_rank: độ khó tối đa.
-- Kết quả sắp xếp theo độ khó tăng dần, rồi mức khớp từ khoá.
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION catalog.fn_search_exercises(
    p_keyword                   text        DEFAULT NULL,
    p_muscle_group_ids          smallint[]  DEFAULT NULL,
    p_primary_only              boolean     DEFAULT false,
    p_available_equipment_ids   integer[]   DEFAULT NULL,
    p_max_difficulty_rank       smallint    DEFAULT NULL,
    p_limit                     integer     DEFAULT 50,
    p_offset                    integer     DEFAULT 0
)
RETURNS TABLE (
    exercise_id     integer,
    slug            varchar,
    name            varchar,
    name_en         varchar,
    difficulty_code varchar,
    difficulty_rank smallint,
    category        catalog.exercise_category,
    match_score     numeric
)
LANGUAGE sql
STABLE
AS $$
    WITH params AS (
        SELECT nullif(util.search_norm(btrim(p_keyword)), '') AS kw
    ),
    target_muscles AS (
        SELECT mg.id
        FROM catalog.muscle_groups mg
        WHERE mg.id = ANY (p_muscle_group_ids)
           OR mg.parent_id = ANY (p_muscle_group_ids)
    ),
    kw_muscles AS (
        SELECT mg.id
        FROM catalog.muscle_groups mg
        LEFT JOIN catalog.muscle_groups parent ON parent.id = mg.parent_id
        CROSS JOIN params p
        WHERE p.kw IS NOT NULL
          AND (util.search_norm(mg.name) LIKE '%' || p.kw || '%'
               OR util.search_norm(coalesce(mg.name_en, '')) LIKE '%' || p.kw || '%'
               OR util.search_norm(coalesce(parent.name, '')) LIKE '%' || p.kw || '%')
    ),
    kw_equipment AS (
        SELECT eq.id
        FROM catalog.equipment eq
        CROSS JOIN params p
        WHERE p.kw IS NOT NULL
          AND eq.deleted_at IS NULL
          AND (util.search_norm(eq.name) LIKE '%' || p.kw || '%'
               OR util.search_norm(coalesce(eq.name_en, '')) LIKE '%' || p.kw || '%'
               OR EXISTS (SELECT 1 FROM catalog.equipment_aliases a
                          WHERE a.equipment_id = eq.id AND a.alias_type = 'synonym'
                            AND util.search_norm(a.alias) LIKE '%' || p.kw || '%'))
    ),
    kw_hits AS (
        -- khớp tên bài tập
        SELECT e.id AS hit_exercise_id,
               greatest(similarity(util.search_norm(e.name), p.kw),
                        similarity(util.search_norm(coalesce(e.name_en, '')), p.kw), 0.5)::numeric AS score
        FROM catalog.exercises e
        CROSS JOIN params p
        WHERE p.kw IS NOT NULL
          AND (util.search_norm(e.name) LIKE '%' || p.kw || '%'
               OR util.search_norm(coalesce(e.name_en, '')) LIKE '%' || p.kw || '%')
        UNION ALL
        -- khớp nhóm cơ (bỏ vai trò stabilizer để tránh kết quả nhiễu)
        SELECT em.exercise_id,
               CASE em.role WHEN 'primary' THEN 0.8 ELSE 0.4 END
        FROM catalog.exercise_muscles em
        WHERE em.muscle_group_id IN (SELECT km.id FROM kw_muscles km)
          AND em.role <> 'stabilizer'
        UNION ALL
        -- khớp thiết bị
        SELECT ee.exercise_id, 0.6
        FROM catalog.exercise_equipment ee
        WHERE ee.equipment_id IN (SELECT ke.id FROM kw_equipment ke)
    ),
    kw_scores AS (
        SELECT h.hit_exercise_id, max(h.score) AS score
        FROM kw_hits h
        GROUP BY h.hit_exercise_id
    )
    SELECT
        e.id,
        e.slug,
        e.name,
        e.name_en,
        d.code,
        d.rank,
        e.category,
        round(coalesce(ks.score, 1.0), 3)
    FROM catalog.exercises e
    JOIN catalog.difficulty_levels d ON d.id = e.difficulty_level_id
    CROSS JOIN params p
    LEFT JOIN kw_scores ks ON ks.hit_exercise_id = e.id
    WHERE e.status = 'published'
      AND e.deleted_at IS NULL
      AND (p.kw IS NULL OR ks.hit_exercise_id IS NOT NULL)
      AND (p_muscle_group_ids IS NULL OR EXISTS (
            SELECT 1 FROM catalog.exercise_muscles em
            WHERE em.exercise_id = e.id
              AND em.muscle_group_id IN (SELECT tm.id FROM target_muscles tm)
              AND (NOT p_primary_only OR em.role = 'primary')))
      AND (p_available_equipment_ids IS NULL OR NOT EXISTS (
            SELECT 1 FROM catalog.exercise_equipment ee
            WHERE ee.exercise_id = e.id
              AND NOT ee.is_optional
              AND NOT (ee.equipment_id = ANY (p_available_equipment_ids))))
      AND (p_max_difficulty_rank IS NULL OR d.rank <= p_max_difficulty_rank)
    ORDER BY d.rank, coalesce(ks.score, 1.0) DESC, e.name
    LIMIT p_limit OFFSET p_offset
$$;

COMMENT ON FUNCTION catalog.fn_search_exercises(text, smallint[], boolean, integer[], smallint, integer, integer)
    IS 'Tìm & lọc bài tập theo từ khoá (không dấu), nhóm cơ chính/phụ, thiết bị sẵn có, độ khó; sắp xếp theo độ khó.';

-- ---------------------------------------------------------------------
-- catalog.fn_suggest_alternatives — gợi ý bài thay thế (Wiki bước 4)
--   Ứng viên: bài đã xuất bản cùng tác động (chính/phụ) lên nhóm cơ CHÍNH của bài gốc,
--   và không cần thiết bị đang bận (p_unavailable_equipment_ids).
--   score = độ trùng nhóm cơ (0–1) + 0.5 nếu là bài thay thế do biên tập viên chọn
--         + 0.1 nếu cùng kiểu compound/isolation − 0.05 × chênh lệch độ khó.
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION catalog.fn_suggest_alternatives(
    p_exercise_id               integer,
    p_unavailable_equipment_ids integer[]   DEFAULT '{}',
    p_limit                     integer     DEFAULT 10
)
RETURNS TABLE (
    exercise_id         integer,
    slug                varchar,
    name                varchar,
    difficulty_rank     smallint,
    is_curated          boolean,
    muscle_overlap      numeric,
    score               numeric
)
LANGUAGE sql
STABLE
AS $$
    WITH src_muscles AS (
        SELECT em.muscle_group_id, em.activation_ratio
        FROM catalog.exercise_muscles em
        WHERE em.exercise_id = p_exercise_id
          AND em.role = 'primary'
    ),
    src AS (
        SELECT e.mechanic, d.rank
        FROM catalog.exercises e
        JOIN catalog.difficulty_levels d ON d.id = e.difficulty_level_id
        WHERE e.id = p_exercise_id
    ),
    candidates AS (
        SELECT em.exercise_id AS cand_id,
               sum(least(em.activation_ratio, sm.activation_ratio))
                 / (SELECT sum(s2.activation_ratio) FROM src_muscles s2) AS overlap
        FROM catalog.exercise_muscles em
        JOIN src_muscles sm ON sm.muscle_group_id = em.muscle_group_id
        WHERE em.exercise_id <> p_exercise_id
          AND em.role IN ('primary', 'secondary')
        GROUP BY em.exercise_id
    )
    SELECT
        e.id,
        e.slug,
        e.name,
        d.rank,
        (ea.exercise_id IS NOT NULL),
        round(c.overlap, 3),
        round(c.overlap
              + CASE WHEN ea.exercise_id IS NOT NULL THEN 0.5 ELSE 0 END
              + CASE WHEN e.mechanic IS NOT DISTINCT FROM s.mechanic THEN 0.1 ELSE 0 END
              - 0.05 * abs(d.rank - s.rank), 3) AS score
    FROM candidates c
    JOIN catalog.exercises e ON e.id = c.cand_id AND e.status = 'published' AND e.deleted_at IS NULL
    JOIN catalog.difficulty_levels d ON d.id = e.difficulty_level_id
    CROSS JOIN src s
    LEFT JOIN catalog.exercise_alternatives ea
           ON ea.exercise_id = p_exercise_id AND ea.alternative_exercise_id = e.id
    WHERE NOT EXISTS (
        SELECT 1 FROM catalog.exercise_equipment ee
        WHERE ee.exercise_id = e.id
          AND NOT ee.is_optional
          AND ee.equipment_id = ANY (coalesce(p_unavailable_equipment_ids, '{}'))
    )
    ORDER BY 7 DESC, e.name
    LIMIT p_limit
$$;

COMMENT ON FUNCTION catalog.fn_suggest_alternatives(integer, integer[], integer)
    IS 'Gợi ý bài thay thế cùng nhóm cơ chính, loại bài cần thiết bị đang bận; ưu tiên bài do biên tập viên chọn.';

-- ---------------------------------------------------------------------
-- catalog.fn_exercises_for_ai_label — từ nhãn YOLOv8 → thiết bị → bài tập (chức năng 7)
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION catalog.fn_exercises_for_ai_label(
    p_ai_label  text,
    p_limit     integer DEFAULT 20
)
RETURNS TABLE (
    equipment_id    integer,
    equipment_name  varchar,
    exercise_id     integer,
    slug            varchar,
    exercise_name   varchar,
    difficulty_rank smallint
)
LANGUAGE sql
STABLE
AS $$
    SELECT eq.id, eq.name, e.id, e.slug, e.name, d.rank
    FROM catalog.equipment_aliases a
    JOIN catalog.equipment eq ON eq.id = a.equipment_id AND eq.deleted_at IS NULL
    JOIN catalog.exercise_equipment ee ON ee.equipment_id = eq.id
    JOIN catalog.exercises e ON e.id = ee.exercise_id AND e.status = 'published' AND e.deleted_at IS NULL
    JOIN catalog.difficulty_levels d ON d.id = e.difficulty_level_id
    WHERE a.alias_type = 'ai_label'
      AND a.alias = lower(btrim(p_ai_label))
    ORDER BY d.rank, e.name
    LIMIT p_limit
$$;

COMMENT ON FUNCTION catalog.fn_exercises_for_ai_label(text, integer)
    IS 'Ánh xạ nhãn lớp của model nhận diện thiết bị sang danh sách bài tập dùng thiết bị đó.';
