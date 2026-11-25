"""Integration test /body, /dashboard, /reports (chức năng 3) trên PostgreSQL thật, rollback sau mỗi test."""

from datetime import date, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from app.core.config import get_settings

MISSING_ID = "00000000-0000-4000-8000-000000000000"


def _err(res, status: int, code: str) -> dict:
    assert res.status_code == status, res.text
    assert res.json()["error"]["code"] == code
    return res.json()["error"]


@pytest.fixture
def local_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "STORAGE_BACKEND", "local")
    monkeypatch.setattr(get_settings(), "LOCAL_STORAGE_DIR", str(tmp_path))
    return tmp_path


# --- Danh mục ---
async def test_lookups_require_login_and_return_page(client: AsyncClient, auth_headers):
    _err(await client.get("/api/v1/body/activity-levels"), 401, "token_invalid")
    h = await auth_headers("demo")
    for path, count in (("activity-levels", 5), ("goal-types", 5), ("body-sites", 11)):
        body = (await client.get(f"/api/v1/body/{path}", headers=h)).json()
        assert len(body["data"]) == count
        assert body["pagination"] == {"next_cursor": None, "has_more": False}


# --- Hồ sơ thể chất ---
async def test_profile_get_existing_and_empty(client: AsyncClient, auth_headers):
    demo = (await client.get("/api/v1/body/profile", headers=await auth_headers("demo"))).json()
    assert demo["gender"] == "male" and demo["height_cm"] is not None
    newbie = (await client.get("/api/v1/body/profile", headers=await auth_headers("newbie"))).json()
    assert newbie["updated_at"] is None and newbie["gender"] == "unspecified"


async def test_profile_put_creates_and_validates(client: AsyncClient, auth_headers):
    h = await auth_headers("newbie")
    body = {"gender": "female", "date_of_birth": "2001-01-15", "height_cm": 160.5, "activity_level_id": 2, "experience_level_id": 1}
    res = await client.put("/api/v1/body/profile", json=body, headers=h)
    assert res.status_code == 200, res.text
    assert res.json()["height_cm"] == 160.5 and res.json()["updated_at"] is not None
    err = _err(await client.put("/api/v1/body/profile", json={**body, "activity_level_id": 999}, headers=h), 422, "validation_error")
    assert err["details"][0]["field"] == "activity_level_id"
    _err(await client.put("/api/v1/body/profile", json={"gender": "female"}, headers=h), 422, "validation_error")


# --- Lần đo ---
async def test_measurements_list_desc_with_metrics_and_cursor(client: AsyncClient, auth_headers):
    h = await auth_headers("demo")
    first = (await client.get("/api/v1/body/measurements?limit=3", headers=h)).json()
    assert len(first["data"]) == 3 and first["pagination"]["has_more"] is True
    assert first["data"][0]["metrics"]["bmi"] is not None
    times = [m["measured_at"] for m in first["data"]]
    assert times == sorted(times, reverse=True)
    second = (
        await client.get(f"/api/v1/body/measurements?limit=3&cursor={first['pagination']['next_cursor']}", headers=h)
    ).json()
    assert {m["id"] for m in first["data"]}.isdisjoint({m["id"] for m in second["data"]})
    _err(await client.get("/api/v1/body/measurements?limit=101", headers=h), 422, "validation_error")
    _err(await client.get("/api/v1/body/measurements?cursor=@@", headers=h), 422, "validation_error")


async def test_measurements_null_metrics_when_profile_incomplete(client: AsyncClient, auth_headers):
    data = (await client.get("/api/v1/body/measurements", headers=await auth_headers("unspecified"))).json()["data"]
    assert data and data[0]["metrics"]["bmi"] is None and data[0]["metrics"]["tdee_kcal"] is None


async def test_measurement_create_get_update_delete(client: AsyncClient, auth_headers):
    h = await auth_headers("demo")
    body = {"measured_at": "2026-01-02T00:30:00Z", "weight_kg": 69.4, "body_fat_pct": 17.9,
            "circumferences": [{"body_site_id": 4, "value_cm": 79.0}]}
    res = await client.post("/api/v1/body/measurements", json=body, headers=h)
    assert res.status_code == 201, res.text
    created = res.json()
    assert res.headers["Location"] == f"/api/v1/body/measurements/{created['id']}"
    assert created["metrics"]["bmr_kcal"] is not None
    assert created["circumferences"][0]["body_site_code"] == "waist"

    _err(await client.post("/api/v1/body/measurements", json=body, headers=h), 409, "measurement_already_exists")

    res = await client.patch(
        f"/api/v1/body/measurements/{created['id']}", json={"weight_kg": 69.0, "circumferences": []}, headers=h
    )
    assert res.status_code == 200, res.text
    assert res.json()["weight_kg"] == 69.0 and res.json()["circumferences"] == []

    assert (await client.delete(f"/api/v1/body/measurements/{created['id']}", headers=h)).status_code == 204
    _err(await client.get(f"/api/v1/body/measurements/{created['id']}", headers=h), 404, "measurement_not_found")


async def test_measurement_validation_errors(client: AsyncClient, auth_headers):
    h = await auth_headers("demo")
    _err(await client.post("/api/v1/body/measurements", json={"weight_kg": 10}, headers=h), 422, "validation_error")
    _err(await client.post("/api/v1/body/measurements", json={"weight_kg": 60, "muscle_mass_kg": 70}, headers=h), 422, "validation_error")
    err = _err(
        await client.post(
            "/api/v1/body/measurements",
            json={"weight_kg": 60, "circumferences": [{"body_site_id": 999, "value_cm": 50}]},
            headers=h,
        ),
        422,
        "validation_error",
    )
    assert err["details"][0]["field"] == "circumferences"


async def test_measurement_of_other_user_is_404(client: AsyncClient, auth_headers, db):
    power_id = await db.scalar(
        text("SELECT m.id FROM body.body_measurements m JOIN auth.users u ON u.id = m.user_id "
             "WHERE u.email = 'power@smartworkout.local' LIMIT 1")
    )
    h = await auth_headers("demo")
    _err(await client.get(f"/api/v1/body/measurements/{power_id}", headers=h), 404, "measurement_not_found")
    _err(await client.delete(f"/api/v1/body/measurements/{power_id}", headers=h), 404, "measurement_not_found")


# --- Mục tiêu ---
async def test_goals_list_and_conflict(client: AsyncClient, auth_headers):
    h = await auth_headers("demo")
    active = (await client.get("/api/v1/body/goals?status=active", headers=h)).json()["data"]
    assert len(active) == 1 and active[0]["goal_type"]["code"] == "lose_fat"
    _err(await client.post("/api/v1/body/goals", json={"goal_type_id": 2}, headers=h), 409, "active_goal_already_exists")
    _err(await client.get(f"/api/v1/body/goals/{MISSING_ID}", headers=h), 404, "goal_not_found")


async def test_goal_create_close_and_reject_edit(client: AsyncClient, auth_headers):
    h = await auth_headers("newbie")
    _err(await client.post("/api/v1/body/goals", json={"goal_type_id": 99}, headers=h), 422, "validation_error")
    res = await client.post("/api/v1/body/goals", json={"goal_type_id": 2, "target_weight_kg": 55}, headers=h)
    assert res.status_code == 201, res.text
    goal = res.json()
    assert res.headers["Location"] == f"/api/v1/body/goals/{goal['id']}"
    assert goal["status"] == "active" and goal["closed_at"] is None

    closed = (await client.patch(f"/api/v1/body/goals/{goal['id']}", json={"status": "achieved"}, headers=h)).json()
    assert closed["status"] == "achieved" and closed["closed_at"] is not None
    _err(await client.patch(f"/api/v1/body/goals/{goal['id']}", json={"target_weight_kg": 54}, headers=h), 422, "validation_error")
    _err(await client.patch(f"/api/v1/body/goals/{goal['id']}", json={"status": "active"}, headers=h), 422, "validation_error")


# --- Dashboard ---
async def test_dashboard_demo_and_empty_user(client: AsyncClient, auth_headers):
    demo = (await client.get("/api/v1/dashboard", headers=await auth_headers("demo"))).json()
    assert demo["latest_metrics"]["tdee_kcal"] is not None
    assert demo["active_goal"]["goal_type"]["code"] == "lose_fat"
    assert demo["this_week"]["planned_count"] >= 0
    newbie = (await client.get("/api/v1/dashboard", headers=await auth_headers("newbie"))).json()
    assert newbie["latest_metrics"] is None and newbie["active_goal"] is None
    assert newbie["today"]["sessions_completed"] == 0


async def test_dashboard_plateau_and_permission(client: AsyncClient, auth_headers):
    assert (await client.get("/api/v1/dashboard", headers=await auth_headers("plateau"))).json()["is_plateau"] is True
    _err(await client.get("/api/v1/dashboard", headers=await auth_headers("editor")), 403, "permission_denied")
    _err(await client.get("/api/v1/dashboard"), 401, "token_invalid")


async def test_weight_trend_ranges(client: AsyncClient, auth_headers):
    h = await auth_headers("power")
    month = (await client.get("/api/v1/dashboard/weight-trend?range=month", headers=h)).json()
    quarter = (await client.get("/api/v1/dashboard/weight-trend?range=3months", headers=h)).json()
    assert 0 < len(month["points"]) <= 5 and len(month["points"]) < len(quarter["points"]) <= 13
    assert quarter["points"][0]["week_start"] >= quarter["from_date"]
    _err(await client.get("/api/v1/dashboard/weight-trend?range=year", headers=h), 422, "validation_error")


# --- Báo cáo ---
def _last_monday() -> str:
    today = date.today()
    return (today - timedelta(days=today.weekday() + 7)).isoformat()


async def test_report_export_and_download_image(client: AsyncClient, auth_headers, local_storage):
    h = await auth_headers("power")
    body = {"report_type": "weekly_summary", "period_start": _last_monday()}
    res = await client.post("/api/v1/reports", json=body, headers=h)
    if res.status_code == 409:  # seed power@ đã có báo cáo tuần trước → lùi thêm 1 tuần
        body["period_start"] = (date.fromisoformat(body["period_start"]) - timedelta(days=7 * 30)).isoformat()
        res = await client.post("/api/v1/reports", json=body, headers=h)
    assert res.status_code == 201, res.text
    report = res.json()
    assert res.headers["Location"] == f"/api/v1/reports/{report['id']}"
    assert report["image_url"] == f"/api/v1/reports/{report['id']}/image"
    assert report["period_end"] == (date.fromisoformat(body["period_start"]) + timedelta(days=7)).isoformat()

    image = await client.get(report["image_url"], headers=h)
    assert image.status_code == 200 and image.headers["content-type"] == "image/png"
    assert image.content[:8] == b"\x89PNG\r\n\x1a\n"
    _err(await client.post("/api/v1/reports", json=body, headers=h), 409, "report_already_exists")


async def test_report_validation_and_not_found(client: AsyncClient, auth_headers):
    h = await auth_headers("demo")
    tuesday = (date.fromisoformat(_last_monday()) + timedelta(days=1)).isoformat()
    _err(await client.post("/api/v1/reports", json={"period_start": tuesday}, headers=h), 422, "validation_error")
    _err(await client.post("/api/v1/reports", json={"report_type": "monthly_summary", "period_start": tuesday}, headers=h), 422, "validation_error")
    _err(await client.get(f"/api/v1/reports/{MISSING_ID}", headers=h), 404, "report_not_found")
    _err(await client.get("/api/v1/reports", headers=await auth_headers("editor")), 403, "permission_denied")


async def test_seed_report_listed_but_image_missing(client: AsyncClient, auth_headers):
    h = await auth_headers("demo")
    page = (await client.get("/api/v1/reports", headers=h)).json()
    assert len(page["data"]) >= 1 and "summary" in page["data"][0]
    # file seed chưa tồn tại trên kho lưu trữ (test-dataset.md §4)
    _err(await client.get(page["data"][0]["image_url"], headers=h), 404, "report_not_found")
