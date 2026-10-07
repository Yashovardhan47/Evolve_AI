from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from app import engine, main
from app.db import connect, initialize
from app.main import app


@pytest.fixture
def clock(monkeypatch):
    current = [datetime(2026, 10, 9, 20, tzinfo=ZoneInfo("Asia/Kolkata"))]
    monkeypatch.setattr(engine, "local_now", lambda user: current[0])
    monkeypatch.setattr(main, "local_now", lambda user: current[0])
    return current


def task(account, **values):
    data = {
        "title": "Practice Python",
        "domain": "learning",
        "minutes": 10,
        "priority": "normal",
        "interest": "Python",
        "notes": "Build a small program",
        "due_date": account.get("/api/state").json()["day"],
        "recurrence": "none",
        "active": True,
    }
    data.update(values)
    response = account.post("/api/tasks", json=data)
    assert response.status_code == 201, response.text
    return response.json(), data


def test_tasks_crud_completion_and_export(account, clock):
    record, data = task(account)
    for _ in range(2):
        assert (
            account.put(
                f"/api/tasks/{record['id']}/completion", json={"complete": True}
            ).status_code
            == 200
        )
    state = account.get("/api/state").json()
    assert state["task_summary"]["completed_today"] == 1
    assert state["task_summary"]["week_by_domain"]["learning"] == 1
    assert state["task_summary"]["committed_minutes"] == 10
    assert state["task_summary"]["remaining_minutes"] == 0
    assert (
        state["today_checkin"] is None
    )  # Task tracking does not overwrite self-reports.
    exported = account.get("/api/export").json()["records"]
    assert exported["tasks"][0]["interest"] == "Python"
    assert exported["tasks"][0]["completed_day"] == "2026-10-09"
    account.put(f"/api/tasks/{record['id']}/completion", json={"complete": False})
    tomorrow = {
        **data,
        "due_date": "2026-10-10",
        "title": "Read a chapter",
        "domain": "mental",
    }
    assert account.put(f"/api/tasks/{record['id']}", json=tomorrow).status_code == 200
    state = account.get("/api/state").json()
    assert state["task_summary"]["planned_today"] == 0
    assert state["tasks"][0]["next_due"] == "2026-10-10"
    assert (
        account.put(
            f"/api/tasks/{record['id']}/completion", json={"complete": True}
        ).status_code
        == 409
    )
    assert account.delete(f"/api/tasks/{record['id']}").status_code == 200
    assert account.get("/api/state").json()["tasks"] == []


def test_repeat_weekends_daily_weekly_and_pause(account, clock):
    weekday, _ = task(account, recurrence="weekdays")
    daily, daily_data = task(account, recurrence="daily", domain="physical")
    weekly, _ = task(account, recurrence="weekly", domain="financial")
    for r in (weekday, daily, weekly):
        account.put(f"/api/tasks/{r['id']}/completion", json={"complete": True})
    assert account.get("/api/state").json()["task_summary"]["week_completions"] == 3
    clock[0] = clock[0].replace(day=10)  # Saturday
    state = account.get("/api/state").json()
    assert state["task_summary"]["planned_today"] == 1
    assert state["task_summary"]["completed_today"] == 0
    dates = {t["id"]: t["next_due"] for t in state["tasks"]}
    assert dates[weekday["id"]] == "2026-10-12"
    assert dates[weekly["id"]] == "2026-10-16"
    assert (
        account.put(
            f"/api/tasks/{weekday['id']}/completion", json={"complete": True}
        ).status_code
        == 409
    )
    account.put(f"/api/tasks/{daily['id']}", json={**daily_data, "active": False})
    assert account.get("/api/state").json()["task_summary"]["planned_today"] == 0
    assert len(account.get("/api/export").json()["records"]["task_logs"]) == 3
    clock[0] = clock[0].replace(day=12)
    assert account.get("/api/state").json()["task_summary"]["planned_today"] == 1
    account.put(f"/api/tasks/{weekday['id']}/completion", json={"complete": True})
    assert account.get("/api/state").json()["task_summary"]["week_completions"] == 4


def test_task_validation_and_all_life_areas(account, clock):
    for domain in (
        "physical",
        "mental",
        "financial",
        "productivity",
        "social",
        "learning",
    ):
        task(account, domain=domain, due_date=None)
    assert len(account.get("/api/state").json()["tasks"]) == 6
    assert account.get("/api/state").json()["task_summary"]["planned_today"] == 0
    for override in (
        {"recurrence": "daily", "due_date": None},
        {"minutes": 0},
        {"minutes": 481},
        {"domain": "invalid"},
        {"priority": "urgent"},
        {"title": " "},
        {"interest": "x" * 81},
        {"due_date": "2026-02-30"},
    ):
        assert (
            account.post(
                "/api/tasks",
                json={"title": "Try a task", "domain": "mental", **override},
            ).status_code
            == 422
        )


def test_task_ownership_and_delete_cascade(account, clock):
    record, data = task(account, recurrence="daily")
    account.put(f"/api/tasks/{record['id']}/completion", json={"complete": True})
    with TestClient(app, headers={"X-Evolve-Request": "1"}) as other:
        other.post(
            "/api/auth/register",
            json={
                "name": "Other",
                "email": "other@example.com",
                "password": "another-long-password",
            },
        )
        assert other.get("/api/state").json()["tasks"] == []
        assert other.put(f"/api/tasks/{record['id']}", json=data).status_code == 404
        assert (
            other.put(
                f"/api/tasks/{record['id']}/completion", json={"complete": True}
            ).status_code
            == 404
        )
        assert other.delete(f"/api/tasks/{record['id']}").status_code == 404
        assert other.get("/api/export").json()["records"]["task_logs"] == []
    assert (
        account.request(
            "DELETE", "/api/account", json={"password": "a-long-test-password"}
        ).status_code
        == 200
    )
    with connect() as con:
        assert con.execute("SELECT COUNT(*) FROM task_logs").fetchone()[0] == 0
        assert con.execute("SELECT COUNT(*) FROM tasks").fetchone()[0] == 0


def test_task_time_reservation_and_overdue(account, clock):
    record, data = task(account, minutes=45, due_date="2026-10-08")
    state = account.get("/api/state").json()
    assert state["tasks"][0]["overdue"]
    assert state["task_summary"]["overdue"] == 1
    assert state["actions"] == []
    account.put(f"/api/tasks/{record['id']}", json={**data, "minutes": 30})
    state = account.get("/api/state").json()
    assert sum(a["minutes"] for a in state["actions"]) <= 15
    account.put(f"/api/tasks/{record['id']}/completion", json={"complete": True})
    state = account.get("/api/state").json()
    assert sum(a["minutes"] for a in state["actions"]) <= 15
    assert not state["tasks"][0]["overdue"]
    initialize()  # Reopening an upgraded database preserves existing records.
    assert len(account.get("/api/state").json()["tasks"]) == 1


def test_task_reminders_respect_preferences(account, clock):
    task(account)
    first = account.get("/api/notifications").json()
    second = account.get("/api/notifications").json()
    assert len(first) == len(second)
    assert len([n for n in first if n["key"] == "tasks-2026-10-09"]) == 1
    p = account.get("/api/state").json()["profile"]
    account.put("/api/profile", json={**p, "reminders": False})
    clock[0] = clock[0].replace(day=10)
    assert len(account.get("/api/notifications").json()) == len(first)


def test_converting_task_to_routine_retains_completion(account, clock):
    record, data = task(account)
    account.put(f"/api/tasks/{record['id']}/completion", json={"complete": True})
    account.put(f"/api/tasks/{record['id']}", json={**data, "recurrence": "daily"})
    state = account.get("/api/state").json()
    assert state["tasks"][0]["done_today"]
    assert state["task_summary"]["week_completions"] == 1
    assert len(account.get("/api/export").json()["records"]["task_logs"]) == 1
