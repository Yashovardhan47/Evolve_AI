from datetime import date, timedelta
from fastapi.testclient import TestClient
from app.main import app


def test_auth_and_static(client):
    assert client.get("/").status_code == 200
    assert "Evolve AI" in client.get("/").text
    assert client.get("/api/state").status_code == 401
    assert client.get("/assets/app.js").status_code == 200
    assert client.get("/api/health").json()["status"] == "ok"


def test_register_login_logout_and_private_cache(account):
    response = account.get("/api/state")
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["checkins"] == []
    assert account.cookies.get("evolve_session")
    account.post("/api/auth/logout", json={})
    assert account.get("/api/auth/me").status_code == 401
    assert (
        account.post(
            "/api/auth/login",
            json={"email": "learner@example.com", "password": "wrong"},
        ).status_code
        == 401
    )
    response = account.post(
        "/api/auth/login",
        json={"email": "LEARNER@example.com", "password": "a-long-test-password"},
    )
    assert response.status_code == 200
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "SameSite=strict" in response.headers["set-cookie"]


def test_csrf_and_origin(account):
    assert (
        account.post("/api/plan", headers={"X-Evolve-Request": ""}, json={}).status_code
        == 403
    )
    assert (
        account.post(
            "/api/plan", headers={"Origin": "https://evil.example"}, json={}
        ).status_code
        == 403
    )
    assert (
        account.post(
            "/api/plan", headers={"Sec-Fetch-Site": "cross-site"}, json={}
        ).status_code
        == 403
    )
    assert (
        account.post(
            "/api/plan", headers={"Origin": "http://testserver"}, json={}
        ).status_code
        == 200
    )


def test_rate_limit_persisted(client):
    for i in range(10):
        assert (
            client.post(
                "/api/auth/login",
                json={"email": "missing@example.com", "password": "wrong"},
            ).status_code
            == 401
        )
    assert (
        client.post(
            "/api/auth/login",
            json={"email": "missing@example.com", "password": "wrong"},
        ).status_code
        == 429
    )


def test_validation_missing_values_and_future(account):
    assert (
        account.put(
            "/api/checkins", json={"completed_tasks": 4, "planned_tasks": 3}
        ).status_code
        == 422
    )
    assert account.put("/api/checkins", json={"mood": 6}).status_code == 422
    assert (
        account.put("/api/checkins", json={"reflection": "no values"}).status_code
        == 422
    )
    future = (date.today() + timedelta(days=2)).isoformat()
    assert (
        account.put("/api/checkins", json={"day": future, "mood": 4}).status_code == 422
    )
    assert account.put("/api/checkins", json={"mood": 3}).status_code == 200
    s = account.get("/api/state").json()
    assert "sleep_hours" not in s["today_checkin"]
    assert s["baselines"]["sleep_hours"]["mean"] is None
    assert not s["associations"]


def test_goals_habits_are_isolated(account):
    goal = account.post(
        "/api/goals",
        json={
            "title": "Learn Python",
            "domain": "learning",
            "target_date": date.today().isoformat(),
            "next_step": "Practice a loop",
        },
    ).json()
    habit = account.post(
        "/api/habits", json={"title": "Read", "domain": "learning"}
    ).json()
    assert (
        account.put(
            f"/api/habits/{habit['id']}/log", json={"complete": True}
        ).status_code
        == 200
    )
    with TestClient(app, headers={"X-Evolve-Request": "1"}) as other:
        other.post(
            "/api/auth/register",
            json={
                "name": "Other",
                "email": "other@example.com",
                "password": "another-long-password",
            },
        )
        for method, path, payload in [
            ("patch", f"/api/goals/{goal['id']}", {"progress": 50}),
            ("put", f"/api/habits/{habit['id']}/log", {"complete": False}),
            ("delete", f"/api/goals/{goal['id']}", None),
        ]:
            assert (
                getattr(other, method)(
                    path, **({"json": payload} if payload else {})
                ).status_code
                == 404
            )
        assert other.get("/api/state").json()["goals"] == []
    s = account.get("/api/state").json()
    assert s["habits"][0]["streak"] == 1
    assert (
        account.patch(f"/api/goals/{goal['id']}", json={"progress": 100}).status_code
        == 200
    )


def test_plan_respects_time_and_preserves_completions(account):
    p = account.get("/api/auth/me").json()["profile"]
    p["daily_minutes"] = 15
    account.put("/api/profile", json=p)
    account.put(
        "/api/checkins",
        json={"mood": 1, "stress": 5, "movement_minutes": 0, "focus": 1},
    )
    plan = account.get("/api/state").json()["actions"]
    assert sum(a["minutes"] for a in plan) <= 15
    assert plan[0]["key"] == "reset"
    first = plan[0]
    account.patch(
        f"/api/actions/{first['id']}", json={"status": "done", "helpful": True}
    )
    for _ in range(2):
        account.post("/api/plan", json={})
    new = account.get("/api/state").json()["actions"]
    assert sum(a["minutes"] for a in new if a["status"] != "skipped") <= 15
    assert sum(a["key"] == first["key"] for a in new) == 1
    assert next(a for a in new if a["key"] == first["key"])["status"] == "done"
    assert (
        account.patch(
            f"/api/actions/{first['id']}", json={"status": "skipped", "helpful": True}
        ).status_code
        == 422
    )


def test_money_precision_budget_and_currency(account):
    day = account.get("/api/state").json()["day"]
    for kind, amount, category in [
        ("income", 100001, "Income"),
        ("expense", 1001, "Food"),
    ]:
        assert (
            account.post(
                "/api/finance/transactions",
                json={
                    "day": day,
                    "kind": kind,
                    "amount_cents": amount,
                    "category": category,
                },
            ).status_code
            == 201
        )
    account.put("/api/finance/budgets", json={"category": "Food", "amount_cents": 1000})
    s = account.get("/api/state").json()
    assert s["finance"]["net_cents"] == 99000
    assert s["finance"]["budgets"][0]["remaining_cents"] == -1
    account.post("/api/plan", json={})
    assert any(
        a["key"] == "budget" for a in account.get("/api/state").json()["actions"]
    )
    p = s["profile"]
    p["currency"] = "USD"
    assert account.put("/api/profile", json=p).status_code == 409
    assert (
        account.post(
            "/api/scenario", json={"expense_reduction_cents": 1002}
        ).status_code
        == 422
    )
    scenario = account.post(
        "/api/scenario",
        json={
            "focus_sessions": 3,
            "minutes_per_session": 25,
            "expense_reduction_cents": 1000,
        },
    ).json()
    assert scenario["added_focus_minutes"] == 75
    assert scenario["scenario_net_cents"] == 100000
    assert (
        account.post(
            "/api/finance/transactions",
            json={"day": day, "kind": "expense", "amount_cents": 0, "category": "Food"},
        ).status_code
        == 422
    )


def test_experiment_balance_idempotency_and_isolation(account):
    exp = account.post(
        "/api/experiments",
        json={
            "title": "Study timing",
            "option_a": "Morning",
            "option_b": "Evening",
            "days": 14,
        },
    ).json()
    assert len(exp["schedule"]) == 14
    assert sum(s["arm"] == "A" for s in exp["schedule"]) == 7
    assert exp["confidence"] == "Exploratory only"
    path = f"/api/experiments/{exp['id']}/log"
    for focus in [3, 4]:
        assert (
            account.put(
                path, json={"focus": focus, "completed": True, "minutes": 25}
            ).status_code
            == 200
        )
    result = account.get("/api/experiments").json()[0]
    assert len(result["logs"]) == 1
    assert result["logs"][0]["focus"] == 4
    with TestClient(app, headers={"X-Evolve-Request": "1"}) as other:
        other.post(
            "/api/auth/register",
            json={
                "name": "Other",
                "email": "other@example.com",
                "password": "another-long-password",
            },
        )
        assert (
            other.put(
                path, json={"focus": 4, "completed": True, "minutes": 25}
            ).status_code
            == 404
        )


def test_notification_dedup_and_preferences(account):
    account.post(
        "/api/goals",
        json={
            "title": "Finish review",
            "domain": "learning",
            "target_date": date.today().isoformat(),
            "next_step": "Write notes",
        },
    )
    first = account.get("/api/notifications").json()
    again = account.get("/api/notifications").json()
    assert len(first) == len(again)
    assert any(n["title"] == "A goal needs your attention" for n in first)
    nid = first[0]["id"]
    assert account.patch(f"/api/notifications/{nid}/read", json={}).status_code == 200
    assert (
        next(n for n in account.get("/api/notifications").json() if n["id"] == nid)[
            "read"
        ]
        == 1
    )
    p = account.get("/api/state").json()["profile"]
    p["reminders"] = False
    account.put("/api/profile", json=p)
    account.post(
        "/api/goals",
        json={
            "title": "Another review",
            "domain": "learning",
            "target_date": date.today().isoformat(),
            "next_step": "Write notes",
        },
    )
    assert len(account.get("/api/notifications").json()) == len(first)


def test_export_and_cascade_delete(account):
    h = account.post(
        "/api/habits", json={"title": "Reflect", "domain": "mental"}
    ).json()
    account.put(f"/api/habits/{h['id']}/log", json={"complete": True})
    account.post("/api/feedback", json={"rating": 4, "message": "Useful next steps"})
    exported = account.get("/api/export").json()
    assert exported["records"]["habit_logs"]
    assert exported["records"]["feedback"][0]["rating"] == 4
    assert "password_hash" not in str(exported)
    assert "token_hash" not in str(exported)
    assert (
        account.request(
            "DELETE", "/api/account", json={"password": "wrong"}
        ).status_code
        == 401
    )
    assert (
        account.request(
            "DELETE", "/api/account", json={"password": "a-long-test-password"}
        ).status_code
        == 200
    )
    assert account.get("/api/state").status_code == 401
    from app.db import connect

    with connect() as con:
        for table in ["users", "sessions", "habits", "habit_logs", "feedback"]:
            assert con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0


def test_demo_isolated_and_marked(client):
    first = client.post("/api/auth/demo", json={}).json()
    assert first["demo"] is True
    assert len(client.get("/api/state").json()["checkins"]) == 14
    with TestClient(app, headers={"X-Evolve-Request": "1"}) as other:
        second = other.post("/api/auth/demo", json={}).json()
        assert second["id"] != first["id"]


def test_personal_timezone_and_no_today_self_comparison(account):
    p = account.get("/api/state").json()["profile"]
    p["timezone"] = "Pacific/Kiritimati"
    assert account.put("/api/profile", json=p).status_code == 200
    s = account.get("/api/state").json()
    from datetime import datetime
    from zoneinfo import ZoneInfo

    assert s["day"] == datetime.now(ZoneInfo(p["timezone"])).date().isoformat()
    yesterday = (date.fromisoformat(s["day"]) - timedelta(days=1)).isoformat()
    account.put("/api/checkins", json={"day": yesterday, "sleep_hours": 7})
    account.put("/api/checkins", json={"sleep_hours": 5})
    s = account.get("/api/state").json()
    assert s["baselines"]["sleep_hours"] == {"mean": 7.0, "observations": 1}
    p["timezone"] = "Fake/Zone"
    assert account.put("/api/profile", json=p).status_code == 422


def test_adaptive_rank_changes_with_actual_usefulness_feedback():
    from app.engine import candidates

    base = {
        "today_checkin": {"focus": 1, "movement_minutes": 0},
        "evidence_days": 10,
        "profile": {"priorities": ["productivity"]},
        "action_history": [],
        "baselines": {},
        "goals": [],
        "habits": [],
        "finance": {"budgets": []},
        "day": date.today().isoformat(),
    }
    original = next(a["rank"] for a in candidates(base) if a["key"] == "focus")
    base["action_history"] = [
        {"key": "focus", "status": "done", "helpful": 0} for _ in range(5)
    ]
    lower = next(a["rank"] for a in candidates(base) if a["key"] == "focus")
    base["action_history"] = [
        {"key": "focus", "status": "done", "helpful": 1} for _ in range(5)
    ]
    higher = next(a["rank"] for a in candidates(base) if a["key"] == "focus")
    assert lower < original < higher


def test_secure_cookie_configuration(client, monkeypatch):
    monkeypatch.setenv("EVOLVE_SECURE_COOKIES", "true")
    response = client.post(
        "/api/auth/register",
        json={
            "name": "Secure",
            "email": "secure@example.com",
            "password": "secure-long-password",
        },
    )
    assert "; Secure" in response.headers["set-cookie"]
    assert response.headers["strict-transport-security"] == "max-age=31536000"


def test_private_financial_and_notification_records(account):
    day = account.get("/api/state").json()["day"]
    transaction = account.post(
        "/api/finance/transactions",
        json={"day": day, "kind": "expense", "amount_cents": 12345, "category": "Food"},
    ).json()
    account.put("/api/finance/budgets", json={"category": "Food", "amount_cents": 1000})
    notices = account.get("/api/notifications").json()
    with TestClient(app, headers={"X-Evolve-Request": "1"}) as other:
        other.post(
            "/api/auth/register",
            json={
                "name": "Other",
                "email": "other@example.com",
                "password": "another-long-password",
            },
        )
        assert (
            other.delete(f"/api/finance/transactions/{transaction['id']}").status_code
            == 404
        )
        assert (
            other.patch(
                f"/api/notifications/{notices[0]['id']}/read", json={}
            ).status_code
            == 404
        )
        assert other.get("/api/export").json()["records"]["ledger"] == []
        assert other.get("/api/state").json()["finance"]["budgets"] == []
