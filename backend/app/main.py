import json
import os
import random
import sqlite3
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path
from statistics import mean
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from . import models as m
from .db import connect, initialize
from .demo import create_demo
from .engine import (
    financial_summary,
    local_now,
    make_plan,
    profile,
    rows,
    snapshot,
    today,
)
from .security import (
    COOKIE,
    current_user,
    digest,
    now,
    password_hash,
    session,
    throttle,
    verify,
)

ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend"


@asynccontextmanager
async def lifespan(app):
    initialize()
    with connect() as con:
        con.execute("DELETE FROM users WHERE demo=1 AND demo_expires<?", (now(),))
    yield


app = FastAPI(
    title="Evolve AI — Personal Development OS",
    version="1.0.0",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
)


@app.middleware("http")
async def protection(request: Request, call_next):
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        if request.headers.get("x-evolve-request") != "1":
            return JSONResponse(
                {"detail": "Missing request protection header"}, status_code=403
            )
        origin = request.headers.get("origin")
        allowed = {
            value.rstrip("/")
            for value in os.getenv("EVOLVE_ORIGINS", "").split(",")
            if value
        }
        allowed.add(str(request.base_url).rstrip("/"))
        if origin and origin.rstrip("/") not in allowed:
            return JSONResponse(
                {"detail": "Cross-origin request rejected"}, status_code=403
            )
        # Browser requests use same-origin fetch; no CORS grants cross-site access.
        if request.headers.get("sec-fetch-site") == "cross-site":
            return JSONResponse(
                {"detail": "Cross-site request rejected"}, status_code=403
            )
        size = request.headers.get("content-length", "0")
        if size.isdigit() and int(size) > 32768:
            return JSONResponse({"detail": "Request too large"}, status_code=413)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    )
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    if os.getenv("EVOLVE_SECURE_COOKIES", "false").lower() == "true":
        response.headers["Strict-Transport-Security"] = "max-age=31536000"
    return response


def public_user(user):
    return {
        "id": user["id"],
        "name": user["name"],
        "email": user["email"] if not user["demo"] else "",
        "profile": profile(user),
        "demo": bool(user["demo"]),
    }


def owned(con, table, item_id, user):
    row = con.execute(
        f"SELECT * FROM {table} WHERE id=? AND user_id=?", (item_id, user["id"])
    ).fetchone()
    if not row:
        raise HTTPException(404, "Record not found")
    return dict(row)


def past_day(day, user):
    if day.isoformat() > today(user):
        raise HTTPException(422, "Future records cannot be logged")


@app.get("/api/health")
def health():
    with connect() as con:
        con.execute("SELECT 1").fetchone()
    return {"status": "ok", "version": "1.0.0"}


@app.post("/api/auth/register", status_code=201)
def register(data: m.Register, request: Request, response: Response):
    throttle(request, data.email)
    with connect() as con:
        try:
            uid = con.execute(
                "INSERT INTO users(email,name,password_hash,profile,created_at) VALUES(?,?,?,?,?)",
                (
                    data.email,
                    data.name,
                    password_hash(data.password),
                    m.Profile().model_dump_json(),
                    now(),
                ),
            ).lastrowid
        except sqlite3.IntegrityError:
            raise HTTPException(
                409,
                "Unable to create this account. Try signing in or use another email.",
            )
        user = dict(con.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone())
    session(response, uid)
    return public_user(user)


@app.post("/api/auth/login")
def login(data: m.Login, request: Request, response: Response):
    throttle(request, data.email)
    with connect() as con:
        user = con.execute(
            "SELECT * FROM users WHERE email=? AND demo=0", (data.email.lower(),)
        ).fetchone()
    # Also spend password hashing time when the email is absent.
    stored = user["password_hash"] if user else "00" * 16 + ":" + "00" * 64
    if not verify(data.password, stored) or not user:
        raise HTTPException(401, "Email or password is incorrect")
    session(response, user["id"])
    return public_user(dict(user))


@app.post("/api/auth/demo", status_code=201)
def demo(request: Request, response: Response):
    throttle(request, "demo")
    user = create_demo()
    session(response, user["id"], True)
    return public_user(user)


@app.get("/api/auth/me")
def me(user=Depends(current_user)):
    return public_user(user)


@app.post("/api/auth/logout")
def logout(request: Request, response: Response):
    with connect() as con:
        con.execute(
            "DELETE FROM sessions WHERE token_hash=?",
            (digest(request.cookies.get(COOKIE, "")),),
        )
    response.delete_cookie(COOKIE, path="/")
    return {"ok": True}


@app.put("/api/profile")
def update_profile(data: m.Profile, user=Depends(current_user)):
    if data.currency != profile(user)["currency"]:
        with connect() as con:
            count = con.execute(
                "SELECT COUNT(*) FROM ledger WHERE user_id=?", (user["id"],)
            ).fetchone()[0]
            budget_count = con.execute(
                "SELECT COUNT(*) FROM budgets WHERE user_id=?", (user["id"],)
            ).fetchone()[0]
        if count or budget_count:
            raise HTTPException(
                409,
                "Currency is locked while financial records exist. Export and remove them before changing currency.",
            )
    with connect() as con:
        updated = data.model_dump()
        updated["personal"] = profile(user)["personal"]
        con.execute(
            "UPDATE users SET profile=? WHERE id=?",
            (json.dumps(updated), user["id"]),
        )
    return updated


@app.put("/api/personal-details")
def personal_details(data: m.PersonalUpdate, user=Depends(current_user)):
    updated = profile(user)
    personal = data.personal.model_dump()
    name = personal["display_name"] or user["name"]
    personal["display_name"] = name
    updated["personal"] = personal
    updated["aspiration"] = data.aspiration
    with connect() as con:
        con.execute(
            "UPDATE users SET profile=?, name=? WHERE id=?",
            (json.dumps(updated), name, user["id"]),
        )
        current = dict(
            con.execute("SELECT * FROM users WHERE id=?", (user["id"],)).fetchone()
        )
    return public_user(current)


@app.get("/api/state")
def state(user=Depends(current_user)):
    return snapshot(user)


@app.put("/api/checkins")
def checkin(data: m.Checkin, user=Depends(current_user)):
    day = data.day or datetime.fromisoformat(today(user)).date()
    past_day(day, user)
    if data.completed_tasks is not None and (
        data.planned_tasks is None or data.completed_tasks > data.planned_tasks
    ):
        raise HTTPException(
            422, "Completed tasks cannot exceed planned tasks; enter both counts"
        )
    values = data.model_dump(exclude={"day"}, exclude_none=True)
    if not any(k != "reflection" for k in values):
        raise HTTPException(422, "Record at least one check-in value")
    with connect() as con:
        con.execute(
            "INSERT INTO checkins(user_id,day,data) VALUES(?,?,?) ON CONFLICT(user_id,day) DO UPDATE SET data=excluded.data",
            (user["id"], day.isoformat(), json.dumps(values)),
        )
    make_plan(user)
    return {"day": day, "data": values}


@app.delete("/api/checkins/{day}")
def delete_checkin(day: str, user=Depends(current_user)):
    with connect() as con:
        con.execute("DELETE FROM checkins WHERE user_id=? AND day=?", (user["id"], day))
    return {"ok": True}


@app.post("/api/goals", status_code=201)
def goal(data: m.Goal, user=Depends(current_user)):
    with connect() as con:
        gid = con.execute(
            "INSERT INTO goals(user_id,title,domain,target_date,next_step,progress) VALUES(?,?,?,?,?,?)",
            (
                user["id"],
                data.title,
                data.domain,
                data.target_date.isoformat(),
                data.next_step,
                data.progress,
            ),
        ).lastrowid
        return owned(con, "goals", gid, user)


@app.put("/api/goals/{gid}")
def edit_goal(gid: int, data: m.Goal, user=Depends(current_user)):
    with connect() as con:
        owned(con, "goals", gid, user)
        con.execute(
            "UPDATE goals SET title=?,domain=?,target_date=?,next_step=?,progress=? WHERE id=?",
            (
                data.title,
                data.domain,
                data.target_date.isoformat(),
                data.next_step,
                data.progress,
                gid,
            ),
        )
        return owned(con, "goals", gid, user)


@app.patch("/api/goals/{gid}")
def progress(gid: int, data: m.Progress, user=Depends(current_user)):
    with connect() as con:
        owned(con, "goals", gid, user)
        con.execute("UPDATE goals SET progress=? WHERE id=?", (data.progress, gid))
        return owned(con, "goals", gid, user)


@app.delete("/api/goals/{gid}")
def delete_goal(gid: int, user=Depends(current_user)):
    with connect() as con:
        owned(con, "goals", gid, user)
        con.execute("DELETE FROM goals WHERE id=?", (gid,))
        con.execute(
            "DELETE FROM actions WHERE user_id=? AND key=? AND status='pending'",
            (user["id"], f"goal-{gid}"),
        )
    return {"ok": True}


@app.post("/api/habits", status_code=201)
def habit(data: m.Habit, user=Depends(current_user)):
    with connect() as con:
        hid = con.execute(
            "INSERT INTO habits(user_id,title,domain) VALUES(?,?,?)",
            (user["id"], data.title, data.domain),
        ).lastrowid
        return owned(con, "habits", hid, user)


@app.put("/api/habits/{hid}/log")
def habit_log(hid: int, data: m.HabitLog, user=Depends(current_user)):
    with connect() as con:
        owned(con, "habits", hid, user)
        if data.complete:
            con.execute(
                "INSERT OR IGNORE INTO habit_logs VALUES(?,?)", (hid, today(user))
            )
        else:
            con.execute(
                "DELETE FROM habit_logs WHERE habit_id=? AND day=?", (hid, today(user))
            )
    return {"ok": True}


@app.delete("/api/habits/{hid}")
def delete_habit(hid: int, user=Depends(current_user)):
    with connect() as con:
        owned(con, "habits", hid, user)
        con.execute("DELETE FROM habits WHERE id=?", (hid,))
        con.execute(
            "DELETE FROM actions WHERE user_id=? AND key=? AND status='pending'",
            (user["id"], f"habit-{hid}"),
        )
    return {"ok": True}


@app.post("/api/finance/transactions", status_code=201)
def transaction(data: m.Transaction, user=Depends(current_user)):
    past_day(data.day, user)
    with connect() as con:
        tid = con.execute(
            "INSERT INTO ledger(user_id,day,kind,amount_cents,category,note) VALUES(?,?,?,?,?,?)",
            (
                user["id"],
                data.day.isoformat(),
                data.kind,
                data.amount_cents,
                data.category,
                data.note,
            ),
        ).lastrowid
        return owned(con, "ledger", tid, user)


@app.delete("/api/finance/transactions/{tid}")
def delete_transaction(tid: int, user=Depends(current_user)):
    with connect() as con:
        owned(con, "ledger", tid, user)
        con.execute("DELETE FROM ledger WHERE id=?", (tid,))
    return {"ok": True}


@app.put("/api/finance/budgets")
def budget(data: m.Budget, user=Depends(current_user)):
    with connect() as con:
        con.execute(
            "INSERT INTO budgets VALUES(?,?,?) ON CONFLICT(user_id,category) DO UPDATE SET amount_cents=excluded.amount_cents",
            (user["id"], data.category, data.amount_cents),
        )
    return data


@app.delete("/api/finance/budgets/{category:path}")
def delete_budget(category: str, user=Depends(current_user)):
    with connect() as con:
        con.execute(
            "DELETE FROM budgets WHERE user_id=? AND category=?", (user["id"], category)
        )
    return {"ok": True}


@app.post("/api/plan")
def plan(user=Depends(current_user)):
    return make_plan(user)


@app.patch("/api/actions/{aid}")
def action_update(aid: int, data: m.ActionUpdate, user=Depends(current_user)):
    if data.helpful is not None and data.status != "done":
        raise HTTPException(422, "Rate usefulness only after completing an action")
    with connect() as con:
        action = owned(con, "actions", aid, user)
        if action["day"] != today(user):
            raise HTTPException(409, "Only today’s plan can be changed")
        helpful = (
            int(data.helpful)
            if data.helpful is not None
            else (action["helpful"] if data.status == "done" else None)
        )
        con.execute(
            "UPDATE actions SET status=?,helpful=? WHERE id=?",
            (data.status, helpful, aid),
        )
        return owned(con, "actions", aid, user)


def experiment_report(con, exp, user):
    schedule = json.loads(exp["schedule"])
    logs = [
        dict(r)
        for r in con.execute(
            "SELECT * FROM experiment_logs WHERE experiment_id=? ORDER BY day",
            (exp["id"],),
        )
    ]
    grouped = {"A": [], "B": []}
    for log in logs:
        assignment = next((s["arm"] for s in schedule if s["day"] == log["day"]), None)
        if assignment:
            grouped[assignment].append(log)
    stats = {}
    for arm, values in grouped.items():
        stats[arm] = {
            "sessions": len(values),
            "mean_focus": round(mean(v["focus"] for v in values), 2)
            if values
            else None,
            "completion_rate": round(100 * mean(v["completed"] for v in values))
            if values
            else None,
            "mean_minutes": round(mean(v["minutes"] for v in values), 1)
            if values
            else None,
        }
    diff = (
        round(stats["A"]["mean_focus"] - stats["B"]["mean_focus"], 2)
        if all(stats[a]["sessions"] for a in stats)
        else None
    )
    return {
        **exp,
        "schedule": schedule,
        "logs": logs,
        "stats": stats,
        "focus_difference_a_minus_b": diff,
        "today_assignment": next(
            (s["arm"] for s in schedule if s["day"] == today(user)), None
        ),
        "confidence": "Exploratory only"
        if min(stats[a]["sessions"] for a in stats) < 5
        else "Preliminary personal evidence",
        "note": "Randomized daily assignments reduce order bias. Small samples, missed sessions and changing tasks still limit conclusions.",
    }


@app.get("/api/experiments")
def experiments(user=Depends(current_user)):
    with connect() as con:
        return [
            experiment_report(con, r, user)
            for r in rows(con, "experiments", user["id"])
        ]


@app.post("/api/experiments", status_code=201)
def experiment(data: m.Experiment, user=Depends(current_user)):
    if data.option_a.casefold() == data.option_b.casefold():
        raise HTTPException(422, "Choose two different routines")
    start = datetime.fromisoformat(today(user)).date()
    assignments = ["A", "B"] * (data.days // 2) + (["A"] if data.days % 2 else [])
    random.SystemRandom().shuffle(assignments)
    schedule = [
        {"day": (start + timedelta(days=i)).isoformat(), "arm": arm}
        for i, arm in enumerate(assignments)
    ]
    with connect() as con:
        eid = con.execute(
            "INSERT INTO experiments(user_id,title,option_a,option_b,start_date,days,schedule) VALUES(?,?,?,?,?,?,?)",
            (
                user["id"],
                data.title,
                data.option_a,
                data.option_b,
                start.isoformat(),
                data.days,
                json.dumps(schedule),
            ),
        ).lastrowid
        return experiment_report(con, owned(con, "experiments", eid, user), user)


@app.put("/api/experiments/{eid}/log")
def experiment_log(eid: int, data: m.ExperimentLog, user=Depends(current_user)):
    with connect() as con:
        exp = owned(con, "experiments", eid, user)
        if exp["status"] != "active" or today(user) not in [
            s["day"] for s in json.loads(exp["schedule"])
        ]:
            raise HTTPException(409, "This experiment is not active today")
        con.execute(
            "INSERT INTO experiment_logs VALUES(?,?,?,?,?,?) ON CONFLICT(experiment_id,day) DO UPDATE SET focus=excluded.focus,completed=excluded.completed,minutes=excluded.minutes,note=excluded.note",
            (
                eid,
                today(user),
                data.focus,
                int(data.completed),
                data.minutes,
                data.note,
            ),
        )
        return experiment_report(con, exp, user)


@app.delete("/api/experiments/{eid}")
def delete_experiment(eid: int, user=Depends(current_user)):
    with connect() as con:
        owned(con, "experiments", eid, user)
        con.execute("DELETE FROM experiments WHERE id=?", (eid,))
    return {"ok": True}


@app.post("/api/scenario")
def scenario(data: m.Scenario, user=Depends(current_user)):
    with connect() as con:
        fin = financial_summary(con, user["id"], today(user)[:7])
    if data.expense_reduction_cents > fin["expense_cents"]:
        raise HTTPException(
            422, "Expense reduction cannot exceed this month’s logged spending"
        )
    return {
        "added_focus_minutes": data.focus_sessions * data.minutes_per_session,
        "current_net_cents": fin["net_cents"],
        "scenario_net_cents": fin["net_cents"] + data.expense_reduction_cents,
        "note": "Arithmetic scenario using your inputs, not a prediction of wellbeing, earnings or future performance.",
    }


@app.get("/api/notifications")
def notifications(user=Depends(current_user)):
    day = today(user)
    p = profile(user)
    with connect() as con:
        if p["reminders"]:
            pending_checkin = not con.execute(
                "SELECT 1 FROM checkins WHERE user_id=? AND day=?", (user["id"], day)
            ).fetchone()
            alerts = []
            if pending_checkin and local_now(user).hour >= p["reminder_hour"]:
                alerts.append(
                    (
                        f"checkin-{day}",
                        "A moment for your check-in",
                        "Record how today went, then choose tomorrow’s next step.",
                    )
                )
            for g in rows(con, "goals", user["id"]):
                if (
                    g["progress"] < 100
                    and (
                        datetime.fromisoformat(g["target_date"]).date()
                        - datetime.fromisoformat(day).date()
                    ).days
                    <= 3
                ):
                    alerts.append(
                        (
                            f"goal-{g['id']}-{day}",
                            "A goal needs your attention",
                            f"{g['title']} · target {g['target_date']}. Review the next step or adjust the date.",
                        )
                    )
            for b in financial_summary(con, user["id"], day[:7])["budgets"]:
                if b["spent_cents"] > b["amount_cents"]:
                    alerts.append(
                        (
                            f"budget-{b['category']}-{day}",
                            "A budget needs a review",
                            f"Logged {b['category']} spending exceeded your monthly budget.",
                        )
                    )
            for key, title, body in alerts:
                con.execute(
                    "INSERT OR IGNORE INTO notifications(user_id,key,title,body,created_at) VALUES(?,?,?,?,?)",
                    (user["id"], key, title, body, now()),
                )
        return sorted(
            rows(con, "notifications", user["id"]),
            key=lambda r: r["created_at"],
            reverse=True,
        )


@app.patch("/api/notifications/{nid}/read")
def read_notification(nid: int, user=Depends(current_user)):
    with connect() as con:
        owned(con, "notifications", nid, user)
        con.execute("UPDATE notifications SET read=1 WHERE id=?", (nid,))
    return {"ok": True}


@app.post("/api/feedback", status_code=201)
def feedback(data: m.Feedback, user=Depends(current_user)):
    with connect() as con:
        con.execute(
            "INSERT INTO feedback(user_id,rating,message,created_at) VALUES(?,?,?,?)",
            (user["id"], data.rating, data.message, now()),
        )
    return {"ok": True}


@app.get("/api/export")
def export(user=Depends(current_user)):
    with connect() as con:
        data = {
            table: rows(con, table, user["id"])
            for table in [
                "checkins",
                "goals",
                "habits",
                "ledger",
                "budgets",
                "actions",
                "experiments",
                "notifications",
                "feedback",
            ]
        }
        data["habit_logs"] = [
            dict(r)
            for r in con.execute(
                "SELECT l.* FROM habit_logs l JOIN habits h ON h.id=l.habit_id WHERE h.user_id=?",
                (user["id"],),
            )
        ]
        data["experiment_logs"] = [
            dict(r)
            for r in con.execute(
                "SELECT l.* FROM experiment_logs l JOIN experiments e ON e.id=l.experiment_id WHERE e.user_id=?",
                (user["id"],),
            )
        ]
    return JSONResponse(
        {"user": public_user(user), "exported_at": now(), "records": data},
        headers={"Content-Disposition": 'attachment; filename="evolve-data.json"'},
    )


@app.delete("/api/account")
def delete_account(
    data: m.DeleteAccount, response: Response, user=Depends(current_user)
):
    if not user["demo"] and not verify(data.password, user["password_hash"]):
        raise HTTPException(401, "Password is incorrect")
    with connect() as con:
        con.execute("DELETE FROM users WHERE id=?", (user["id"],))
    response.delete_cookie(COOKIE, path="/")
    return {"ok": True}


@app.get("/")
def index():
    return FileResponse(FRONTEND / "index.html")


app.mount("/assets", StaticFiles(directory=FRONTEND), name="assets")
