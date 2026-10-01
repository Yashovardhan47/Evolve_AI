"""An isolated account with clearly fictional demonstration records."""

import json
import secrets
from datetime import timedelta
from .db import connect
from .engine import today, make_plan
from .models import Profile
from .security import now, password_hash


def create_demo():
    from datetime import datetime, timezone

    with connect() as con:
        con.execute("DELETE FROM users WHERE demo=1 AND demo_expires<?", (now(),))
        p = Profile(aspiration="Build a calmer, more consistent life").model_dump()
        uid = con.execute(
            "INSERT INTO users(email,name,password_hash,profile,created_at,demo,demo_expires) VALUES(?,?,?,?,?,1,?)",
            (
                f"demo-{secrets.token_hex(12)}@example.invalid",
                "Alex",
                password_hash(secrets.token_urlsafe(32)),
                json.dumps(p),
                now(),
                (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
            ),
        ).lastrowid
        user = dict(con.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone())
        day = datetime.fromisoformat(today(user)).date()
        for i in range(14):
            record_day = (day - timedelta(days=13 - i)).isoformat()
            data = {
                "sleep_hours": round(6.4 + (i % 5) * 0.3, 1),
                "movement_minutes": 10 + (i % 4) * 10,
                "mood": 3 + (i % 3 == 0),
                "energy": 3 + (i % 4 == 0),
                "stress": 2 + (i % 4 == 0),
                "focus": 3 + (i % 3 == 0),
                "planned_tasks": 5,
                "completed_tasks": 2 + i % 4,
                "reflection": "Fictional demo check-in.",
            }
            con.execute(
                "INSERT INTO checkins(user_id,day,data) VALUES(?,?,?)",
                (uid, record_day, json.dumps(data)),
            )
        for title, domain, step, progress, days in [
            (
                "Build a consistent movement routine",
                "physical",
                "Take a comfortable 15-minute walk",
                45,
                21,
            ),
            (
                "Complete my learning portfolio",
                "learning",
                "Outline one project case study",
                60,
                10,
            ),
            (
                "Understand my monthly spending",
                "financial",
                "Review this week’s recorded expenses",
                30,
                7,
            ),
        ]:
            con.execute(
                "INSERT INTO goals(user_id,title,domain,target_date,next_step,progress) VALUES(?,?,?,?,?,?)",
                (
                    uid,
                    title,
                    domain,
                    (day + timedelta(days=days)).isoformat(),
                    step,
                    progress,
                ),
            )
        for title, domain in [
            ("Read a few pages", "learning"),
            ("Pause and reflect", "mental"),
            ("Move comfortably", "physical"),
        ]:
            hid = con.execute(
                "INSERT INTO habits(user_id,title,domain) VALUES(?,?,?)",
                (uid, title, domain),
            ).lastrowid
            for i in (1, 2, 3, 5, 6):
                con.execute(
                    "INSERT INTO habit_logs VALUES(?,?)",
                    (hid, (day - timedelta(days=i)).isoformat()),
                )
        for kind, amount, category, note in [
            ("income", 4500000, "Income", "Fictional monthly income"),
            ("expense", 1200000, "Housing", "Fictional rent"),
            ("expense", 320000, "Food", "Fictional groceries"),
            ("expense", 150000, "Transport", "Fictional travel"),
            ("expense", 180000, "Learning", "Fictional course"),
        ]:
            con.execute(
                "INSERT INTO ledger(user_id,day,kind,amount_cents,category,note) VALUES(?,?,?,?,?,?)",
                (uid, day.isoformat(), kind, amount, category, note),
            )
        for category, amount in [
            ("Food", 600000),
            ("Learning", 150000),
            ("Transport", 300000),
        ]:
            con.execute("INSERT INTO budgets VALUES(?,?,?)", (uid, category, amount))
    make_plan(user)
    return user
