-- =====================================================================
-- Smart Workout AI — Views: body (Dashboard chỉ số cơ thể)
-- Các chỉ số dẫn xuất (tuổi, BMI, BMR, TDEE, LBM) được TÍNH, không lưu → đảm bảo 3NF.
-- =====================================================================

-- ---------------------------------------------------------------------
-- body.v_body_metrics — mỗi lần đo kèm chỉ số tính toán
--   BMI  = kg / m²  (phân loại theo chuẩn châu Á – Thái Bình Dương của WHO)
--   BMR  = Mifflin-St Jeor: 10·kg + 6.25·cm − 5·tuổi + s  (s = +5 nam, −161 nữ, −78 khác)
--   BMR2 = Katch-McArdle: 370 + 21.6·LBM  (chỉ khi có %mỡ)
--   TDEE = BMR × hệ số vận động
-- Lưu ý: dùng chiều cao & mức vận động HIỆN TẠI trong hồ sơ.
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW body.v_body_metrics AS
WITH base AS (
    SELECT
        m.id            AS measurement_id,
        m.user_id,
        m.measured_at,
        m.weight_kg,
        m.body_fat_pct,
        m.muscle_mass_kg,
        m.source,
        p.gender,
        p.height_cm,
        a.code          AS activity_level_code,
        a.multiplier    AS activity_multiplier,
        CASE WHEN p.date_of_birth IS NOT NULL
             THEN date_part('year', age(m.measured_at::date, p.date_of_birth))::int
        END             AS age_years
    FROM body.body_measurements m
    LEFT JOIN body.user_body_profiles p ON p.user_id = m.user_id
    LEFT JOIN body.activity_levels a ON a.id = p.activity_level_id
),
calc AS (
    SELECT
        b.*,
        round(b.weight_kg / power(b.height_cm / 100.0, 2), 1) AS bmi,
        CASE WHEN b.body_fat_pct IS NOT NULL
             THEN round(b.weight_kg * (1 - b.body_fat_pct / 100.0), 2)
        END AS lean_body_mass_kg,
        CASE WHEN b.height_cm IS NOT NULL AND b.age_years IS NOT NULL
             THEN round(10 * b.weight_kg + 6.25 * b.height_cm - 5 * b.age_years
                        + CASE b.gender WHEN 'male' THEN 5 WHEN 'female' THEN -161 ELSE -78 END)
        END AS bmr_kcal
    FROM base b
)
SELECT
    c.measurement_id,
    c.user_id,
    c.measured_at,
    c.weight_kg,
    c.body_fat_pct,
    c.muscle_mass_kg,
    c.source,
    c.gender,
    c.height_cm,
    c.age_years,
    c.bmi,
    CASE
        WHEN c.bmi IS NULL THEN NULL
        WHEN c.bmi < 18.5 THEN 'underweight'
        WHEN c.bmi < 23   THEN 'normal'
        WHEN c.bmi < 25   THEN 'overweight'
        ELSE 'obese'
    END AS bmi_category,
    c.lean_body_mass_kg,
    c.bmr_kcal,
    CASE WHEN c.lean_body_mass_kg IS NOT NULL
         THEN round(370 + 21.6 * c.lean_body_mass_kg)
    END AS bmr_katch_mcardle_kcal,
    c.activity_level_code,
    round(c.bmr_kcal * c.activity_multiplier) AS tdee_kcal
FROM calc c;

COMMENT ON VIEW body.v_body_metrics IS 'Số đo cơ thể kèm tuổi, BMI (+ phân loại châu Á), LBM, BMR (Mifflin-St Jeor & Katch-McArdle), TDEE. Tính tại thời điểm truy vấn.';

-- ---------------------------------------------------------------------
-- body.v_latest_body_metrics — chỉ số mới nhất của mỗi user (thẻ Dashboard)
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW body.v_latest_body_metrics AS
SELECT DISTINCT ON (v.user_id) v.*
FROM body.v_body_metrics v
ORDER BY v.user_id, v.measured_at DESC;

COMMENT ON VIEW body.v_latest_body_metrics IS 'Lần đo gần nhất của mỗi user cùng các chỉ số tính toán.';

-- ---------------------------------------------------------------------
-- body.v_weekly_weight_trend — xu hướng cân nặng theo tuần + cờ chững cân
-- is_plateau: thay đổi trung bình tuần < 0.2 kg trong 3 tuần liên tiếp (heuristic).
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW body.v_weekly_weight_trend AS
WITH weekly AS (
    SELECT
        m.user_id,
        date_trunc('week', m.measured_at AT TIME ZONE coalesce(up.timezone, 'Asia/Ho_Chi_Minh'))::date AS week_start,
        round(avg(m.weight_kg), 2)      AS avg_weight_kg,
        min(m.weight_kg)                AS min_weight_kg,
        max(m.weight_kg)                AS max_weight_kg,
        round(avg(m.body_fat_pct), 1)   AS avg_body_fat_pct,
        count(*)                        AS measurement_count
    FROM body.body_measurements m
    LEFT JOIN auth.user_profiles up ON up.user_id = m.user_id
    GROUP BY m.user_id, 2
),
deltas AS (
    SELECT
        w.*,
        w.avg_weight_kg - lag(w.avg_weight_kg) OVER (PARTITION BY w.user_id ORDER BY w.week_start) AS change_kg
    FROM weekly w
)
SELECT
    d.user_id,
    d.week_start,
    d.avg_weight_kg,
    d.min_weight_kg,
    d.max_weight_kg,
    d.avg_body_fat_pct,
    d.measurement_count,
    d.change_kg,
    coalesce(
        abs(d.change_kg) < 0.2
        AND abs(lag(d.change_kg, 1) OVER (PARTITION BY d.user_id ORDER BY d.week_start)) < 0.2
        AND abs(lag(d.change_kg, 2) OVER (PARTITION BY d.user_id ORDER BY d.week_start)) < 0.2,
        false) AS is_plateau
FROM deltas d;

COMMENT ON VIEW body.v_weekly_weight_trend IS 'Cân nặng/%mỡ trung bình theo tuần (theo múi giờ user), chênh lệch so với tuần trước và cờ chững cân (plateau).';
