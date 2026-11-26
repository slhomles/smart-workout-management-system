"""Integration test /workout-sessions (chức năng 6: ghi hiệp, rep events, tempo) trên PostgreSQL thật."""

from httpx import AsyncClient
from sqlalchemy import text

BASE = "/api/v1/workout-sessions"
MISSING_ID = "00000000-0000-4000-8000-000000000000"

REP_EVENTS = [
    {"rep_no": 1, "start_offset_ms": 0, "eccentric_ms": 3000, "pause_bottom_ms": 200, "concentric_ms": 1000,
     "pause_top_ms": 300, "min_joint_angle_deg": 78.5, "max_joint_angle_deg": 172.0, "is_full_rom": True},
    {"rep_no": 2, "start_offset_ms": 4600, "eccentric_ms": 2900, "pause_bottom_ms": 100, "concentric_ms": 1200,
     "pause_top_ms": 300, "min_joint_angle_deg": 95.0, "max_joint_angle_deg": 171.0, "is_full_rom": False},
]


def _err(res, status: int, code: str) -> dict:
    assert res.status_code == status, res.text
    assert res.json()["error"]["code"] == code
    return res.json()["error"]


async def _exercise_id(db, slug: str) -> int:
    return await db.scalar(text("SELECT id FROM catalog.exercises WHERE slug = :slug"), {"slug": slug})


async def _start_with_exercise(client: AsyncClient, db, headers: dict) -> tuple[str, str]:
    session = (await client.post(BASE, json={"name": "Test AutoTracker"}, headers=headers)).json()
    res = await client.post(
        f"{BASE}/{session['id']}/exercises",
        json={"exercise_id": await _exercise_id(db, "dumbbell-row"), "added_via": "wiki"},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    return session["id"], res.json()["id"]


async def test_list_sessions_desc_filter_and_validation(client: AsyncClient, auth_headers):
    h = await auth_headers("demo")
    page = (await client.get(f"{BASE}?status=completed&limit=5", headers=h)).json()
    assert 0 < len(page["data"]) <= 5 and all(s["status"] == "completed" for s in page["data"])
    starts = [s["started_at"] for s in page["data"]]
    assert starts == sorted(starts, reverse=True)
    if page["pagination"]["has_more"]:
        nxt = (await client.get(f"{BASE}?status=completed&limit=5&cursor={page['pagination']['next_cursor']}", headers=h)).json()
        assert {s["id"] for s in page["data"]}.isdisjoint({s["id"] for s in nxt["data"]})
    _err(await client.get(f"{BASE}?limit=0", headers=h), 422, "validation_error")
    _err(await client.get(BASE, headers=await auth_headers("editor")), 403, "permission_denied")


async def test_start_session_conflict_and_created(client: AsyncClient, auth_headers):
    _err(await client.post(BASE, json={}, headers=await auth_headers("inprogress")), 409, "session_already_in_progress")
    res = await client.post(BASE, json={"name": "Buổi đầu tiên"}, headers=await auth_headers("newbie"))
    assert res.status_code == 201, res.text
    body = res.json()
    assert res.headers["Location"] == f"{BASE}/{body['id']}"
    assert body["status"] == "in_progress" and body["ended_at"] is None and body["exercises"] == []


async def test_ai_set_with_rep_events_computes_reps_and_tempo(client: AsyncClient, auth_headers, db):
    h = await auth_headers("newbie")
    session_id, se_id = await _start_with_exercise(client, db, h)
    res = await client.post(
        f"{BASE}/{session_id}/exercises/{se_id}/sets",
        json={"weight_kg": 20, "source": "ai_realtime", "rep_events": REP_EVENTS},
        headers=h,
    )
    assert res.status_code == 201, res.text
    created = res.json()
    assert res.headers["Location"].endswith(f"/sets/{created['id']}")
    assert created["reps"] == 2 and created["set_no"] == 1 and created["volume_kg"] == 40.0
    tempo = created["tempo"]
    assert tempo["rep_count"] == 2
    assert tempo["avg_eccentric_ms"] == 2950 and tempo["avg_concentric_ms"] == 1100
    assert tempo["time_under_tension_ms"] == 3000 + 200 + 1000 + 300 + 2900 + 100 + 1200 + 300
    assert tempo["full_rom_pct"] == 50.0
    assert [e["rep_no"] for e in created["rep_events"]] == [1, 2]

    detail = (await client.get(f"{BASE}/{session_id}", headers=h)).json()
    assert detail["exercises"][0]["sets"][0]["tempo"]["rep_count"] == 2
    assert detail["total_reps"] == 2


async def test_manual_set_update_delete_and_finish(client: AsyncClient, auth_headers, db):
    h = await auth_headers("newbie")
    session_id, se_id = await _start_with_exercise(client, db, h)
    sets = f"{BASE}/{session_id}/exercises/{se_id}/sets"
    created = (await client.post(sets, json={"reps": 10, "weight_kg": 22.5, "rpe": 8}, headers=h)).json()
    assert created["tempo"] is None and created["est_1rm_kg"] is not None

    updated = await client.patch(f"{sets}/{created['id']}", json={"reps": 9, "rpe": 8.5}, headers=h)
    assert updated.status_code == 200 and updated.json()["reps"] == 9
    _err(await client.patch(f"{sets}/{created['id']}", json={"rpe": 8.3}, headers=h), 422, "validation_error")

    second = (await client.post(sets, json={"reps": 8, "weight_kg": 22.5}, headers=h)).json()
    assert second["set_no"] == 2
    assert (await client.delete(f"{sets}/{second['id']}", headers=h)).status_code == 204
    _err(await client.get(f"{sets}/{second['id']}", headers=h), 404, "exercise_set_not_found")

    finished = await client.post(f"{BASE}/{session_id}/finish", json={"session_rpe": 7.5}, headers=h)
    assert finished.status_code == 200, finished.text
    assert finished.json()["status"] == "completed" and finished.json()["ended_at"] is not None
    _err(await client.post(f"{BASE}/{session_id}/finish", json={}, headers=h), 409, "session_not_in_progress")
    _err(await client.post(sets, json={"reps": 5}, headers=h), 409, "session_not_in_progress")
    _err(await client.delete(f"{sets}/{created['id']}", headers=h), 409, "session_not_in_progress")


async def test_set_validation_errors(client: AsyncClient, auth_headers, db):
    h = await auth_headers("newbie")
    session_id, se_id = await _start_with_exercise(client, db, h)
    sets = f"{BASE}/{session_id}/exercises/{se_id}/sets"
    _err(await client.post(sets, json={"weight_kg": 20}, headers=h), 422, "validation_error")
    _err(await client.post(sets, json={"source": "manual", "rep_events": REP_EVENTS}, headers=h), 422, "validation_error")
    _err(await client.post(sets, json={"source": "ai_realtime", "rep_events": [REP_EVENTS[1]]}, headers=h), 422, "validation_error")
    bad_angle = {**REP_EVENTS[0], "min_joint_angle_deg": 120, "max_joint_angle_deg": 90}
    _err(await client.post(sets, json={"source": "ai_realtime", "rep_events": [bad_angle]}, headers=h), 422, "validation_error")


async def test_add_exercise_not_found_cases(client: AsyncClient, auth_headers, db):
    h = await auth_headers("newbie")
    session = (await client.post(BASE, json={}, headers=h)).json()
    url = f"{BASE}/{session['id']}/exercises"
    _err(await client.post(url, json={"exercise_id": 999999}, headers=h), 404, "exercise_not_found")
    draft_id = await _exercise_id(db, "test-draft-exercise")
    _err(await client.post(url, json={"exercise_id": draft_id}, headers=h), 404, "exercise_not_found")
    _err(await client.post(url, json={"exercise_id": 10, "added_via": "plan"}, headers=h), 422, "validation_error")


async def test_not_found_and_ownership(client: AsyncClient, auth_headers, db):
    demo_session = await db.scalar(
        text("SELECT s.id FROM training.workout_sessions s JOIN auth.users u ON u.id = s.user_id "
             "WHERE u.email = 'demo@smartworkout.local' AND s.deleted_at IS NULL LIMIT 1")
    )
    power = await auth_headers("power")
    _err(await client.get(f"{BASE}/{demo_session}", headers=power), 404, "workout_session_not_found")
    _err(await client.get(f"{BASE}/{MISSING_ID}", headers=power), 404, "workout_session_not_found")

    h = await auth_headers("inprogress")
    current = (await client.get(f"{BASE}?status=in_progress", headers=h)).json()["data"][0]
    _err(await client.post(f"{BASE}/{current['id']}/exercises/{MISSING_ID}/sets", json={"reps": 5}, headers=h),
         404, "session_exercise_not_found")
    detail = (await client.get(f"{BASE}/{current['id']}", headers=h)).json()
    se_id = detail["exercises"][0]["id"]
    _err(await client.get(f"{BASE}/{current['id']}/exercises/{se_id}/sets/999999999", headers=h), 404, "exercise_set_not_found")
