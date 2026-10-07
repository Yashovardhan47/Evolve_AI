"""Transparent baseline recommender. No diagnostic or causal claims."""

import json
import math
from datetime import datetime, timedelta
from statistics import mean
from zoneinfo import ZoneInfo
from .db import connect
from .models import PersonalDetails
from .tasks import task_summary


def profile(user):
    data = json.loads(user["profile"])
    data["personal"] = PersonalDetails(**data.get("personal", {})).model_dump()
    if not data["personal"]["display_name"]:
        data["personal"]["display_name"] = user["name"]
    return data


def local_now(user):
    return datetime.now(ZoneInfo(profile(user)["timezone"]))


def today(user):
    return local_now(user).date().isoformat()


def rows(con, table, user_id):
    # Table names originate in application code, never in request parameters.
    return [
        dict(r)
        for r in con.execute(f"SELECT * FROM {table} WHERE user_id=?", (user_id,))
    ]


def financial_summary(con, user_id, month):
    ledger = rows(con, "ledger", user_id)
    current = [r for r in ledger if r["day"].startswith(month)]
    income = sum(r["amount_cents"] for r in current if r["kind"] == "income")
    expenses = sum(r["amount_cents"] for r in current if r["kind"] == "expense")
    budgets = rows(con, "budgets", user_id)
    for b in budgets:
        b["spent_cents"] = sum(
            r["amount_cents"]
            for r in current
            if r["kind"] == "expense" and r["category"] == b["category"]
        )
        b["remaining_cents"] = b["amount_cents"] - b["spent_cents"]
    return {
        "month": month,
        "income_cents": income,
        "expense_cents": expenses,
        "net_cents": income - expenses,
        "budgets": budgets,
        "transactions": sorted(ledger, key=lambda r: (r["day"], r["id"]), reverse=True),
    }


def snapshot(user):
    day = today(user)
    with connect() as con:
        checkins = sorted(rows(con, "checkins", user["id"]), key=lambda r: r["day"])
        for row in checkins:
            row["data"] = json.loads(row["data"])
        goals = rows(con, "goals", user["id"])
        habits = rows(con, "habits", user["id"])
        for h in habits:
            h["days"] = [
                r[0]
                for r in con.execute(
                    "SELECT day FROM habit_logs WHERE habit_id=? ORDER BY day",
                    (h["id"],),
                )
            ]
            h["done_today"] = day in h["days"]
            # Streak can end yesterday if today's habit has not been completed yet.
            cursor = datetime.fromisoformat(day).date()
            if not h["done_today"]:
                cursor -= timedelta(days=1)
            streak = 0
            while cursor.isoformat() in h["days"]:
                streak += 1
                cursor -= timedelta(days=1)
            h["streak"] = streak
        finance = financial_summary(con, user["id"], day[:7])
        actions = [r for r in rows(con, "actions", user["id"]) if r["day"] == day]
        history = rows(con, "actions", user["id"])
        tasks, task_progress = task_summary(con, user["id"], day)
    current = next((r["data"] for r in checkins if r["day"] == day), None)
    recent = [
        r
        for r in checkins
        if r["day"]
        >= (datetime.fromisoformat(day).date() - timedelta(days=13)).isoformat()
    ]
    baselines = {}
    for key in ("sleep_hours", "movement_minutes", "mood", "energy", "stress", "focus"):
        values = [
            r["data"][key]
            for r in recent
            if r["day"] != day and r["data"].get(key) is not None
        ]
        baselines[key] = {
            "mean": round(mean(values), 1) if values else None,
            "observations": len(values),
        }
    return {
        "day": day,
        "profile": profile(user),
        "checkins": checkins,
        "today_checkin": current,
        "baselines": baselines,
        "goals": goals,
        "tasks": tasks,
        "task_summary": task_progress,
        "habits": habits,
        "finance": finance,
        "actions": actions,
        "action_history": history,
        "evidence_days": len(recent),
        "associations": associations(recent),
    }


def associations(checkins):
    findings = []
    for x, y in [
        ("sleep_hours", "focus"),
        ("movement_minutes", "mood"),
        ("stress", "focus"),
    ]:
        pairs = [(r["data"].get(x), r["data"].get(y)) for r in checkins]
        pairs = [(a, b) for a, b in pairs if a is not None and b is not None]
        if len(pairs) < 7:
            continue
        mx, my = mean(a for a, b in pairs), mean(b for a, b in pairs)
        denominator = math.sqrt(
            sum((a - mx) ** 2 for a, b in pairs) * sum((b - my) ** 2 for a, b in pairs)
        )
        if not denominator:
            continue
        coefficient = sum((a - mx) * (b - my) for a, b in pairs) / denominator
        findings.append(
            {
                "x": x,
                "y": y,
                "correlation": round(coefficient, 2),
                "observations": len(pairs),
                "note": "Association in your logged days; does not establish cause or predict a health outcome.",
            }
        )
    return findings


def candidates(state):
    c = state["today_checkin"] or {}
    items = []
    confidence = (
        "Early signal" if state["evidence_days"] < 7 else "Based on recent logs"
    )

    def add(key, domain, title, reason, minutes, priority):
        rated = [
            a
            for a in state["action_history"]
            if a["key"] == key and a["helpful"] is not None and a["status"] == "done"
        ]
        helpful = sum(bool(a["helpful"]) for a in rated)
        score = priority + (6 if domain in state["profile"]["priorities"] else 0)
        # Smoothed feedback changes ranking, never claims to predict health benefits.
        score += 8 * ((helpful + 1) / (len(rated) + 2) - 0.5)
        items.append(
            {
                "key": key,
                "domain": domain,
                "title": title,
                "reason": reason,
                "minutes": minutes,
                "confidence": confidence,
                "rank": score,
                "feedback_observations": len(rated),
            }
        )

    if not c:
        add(
            "checkin",
            "productivity",
            "Make a two-minute check-in",
            "A plan needs your current context. You have not checked in today.",
            2,
            100,
        )
    if c.get("stress", 0) >= 4 or (c.get("mood") is not None and c["mood"] <= 2):
        add(
            "reset",
            "mental",
            "Take a quiet pause and name one support you need",
            "You reported high stress or a difficult mood. Keep the next step small; reach out to someone you trust if useful.",
            5,
            95,
        )
    if c.get("movement_minutes") is not None and c["movement_minutes"] < 15:
        add(
            "movement",
            "physical",
            "Choose a comfortable movement break",
            "You logged little movement today. Pick a walk or stretch that fits your ability and comfort.",
            10,
            64,
        )
    if c.get("sleep_hours") is not None:
        base = state["baselines"]["sleep_hours"]
        if base["observations"] >= 3 and c["sleep_hours"] < base["mean"] - 1:
            add(
                "winddown",
                "physical",
                "Make room for your usual wind-down routine",
                f"Last night's sleep was below your recent average ({base['mean']} h). Avoid adding unnecessary commitments today.",
                10,
                80,
            )
    overdue = sorted(
        [g for g in state["goals"] if g["progress"] < 100],
        key=lambda g: g["target_date"],
    )
    for g in overdue[:3]:
        days_left = (
            datetime.fromisoformat(g["target_date"]).date()
            - datetime.fromisoformat(state["day"]).date()
        ).days
        add(
            f"goal-{g['id']}",
            g["domain"],
            g["next_step"],
            f"Next step for ‘{g['title']}’, currently {g['progress']}% complete. "
            + (
                "Target date has passed; review or reduce the step."
                if days_left < 0
                else f"Target date is in {days_left} days."
            ),
            15,
            75 if days_left <= 3 else 55,
        )
    if c.get("focus") is not None and c["focus"] <= 2:
        add(
            "focus",
            "productivity",
            "Work on one task with distractions paused",
            "Your focus check-in was low. Try a short single-task session and rate whether it helped.",
            10,
            66,
        )
    over = [
        b for b in state["finance"]["budgets"] if b["spent_cents"] > b["amount_cents"]
    ]
    if over:
        add(
            "budget",
            "financial",
            "Review one category that exceeded its budget",
            "Logged spending exceeded the budget for "
            + ", ".join(b["category"] for b in over)
            + ". Choose an adjustment you can actually maintain.",
            5,
            78,
        )
    elif "financial" in state["profile"]["priorities"]:
        add(
            "money-check",
            "financial",
            "Check your recent spending and upcoming costs",
            "Financial awareness is one of your chosen priorities. Your ledger only includes amounts you recorded.",
            5,
            48,
        )
    for h in state["habits"]:
        if not h["done_today"]:
            add(
                f"habit-{h['id']}",
                h["domain"],
                f"Start small: {h['title']}",
                "This is a habit you chose. A short start is enough; mark the habit complete only after doing it.",
                5,
                45,
            )
    if "social" in state["profile"]["priorities"]:
        add(
            "connection",
            "social",
            "Check in with someone you care about",
            "Connection is one of your selected priorities. Choose a low-pressure conversation.",
            5,
            40,
        )
    if "learning" in state["profile"]["priorities"]:
        add(
            "learning",
            "learning",
            "Practice one small skill and record what you learned",
            "Learning is one of your selected priorities. Pick a skill connected to your longer-term goal.",
            10,
            42,
        )
    return sorted(items, key=lambda x: (-x["rank"], x["key"]))


def make_plan(user):
    state = snapshot(user)
    remaining = (
        state["profile"]["daily_minutes"]
        - state["task_summary"]["committed_minutes"]
        - sum(a["minutes"] for a in state["actions"] if a["status"] == "done")
    )
    preserved = {a["key"] for a in state["actions"] if a["status"] != "pending"}
    selected = []
    for item in candidates(state):
        if item["key"] not in preserved and item["minutes"] <= remaining:
            remaining -= item["minutes"]
            selected.append(item)
        if len(selected) >= 5:
            break
    with connect() as con:
        con.execute(
            "DELETE FROM actions WHERE user_id=? AND day=? AND status='pending'",
            (user["id"], state["day"]),
        )
        for a in selected:
            con.execute(
                "INSERT INTO actions(user_id,day,key,domain,title,reason,minutes,confidence) VALUES(?,?,?,?,?,?,?,?)",
                (
                    user["id"],
                    state["day"],
                    a["key"],
                    a["domain"],
                    a["title"],
                    a["reason"],
                    a["minutes"],
                    a["confidence"],
                ),
            )
    return snapshot(user)["actions"]
