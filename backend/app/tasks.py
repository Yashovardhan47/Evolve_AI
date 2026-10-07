"""Date-based personal tasks; recurrence is evaluated in the account's timezone."""

from datetime import date, timedelta

DOMAINS = ("physical", "mental", "financial", "productivity", "social", "learning")


def scheduled(task, day):
    start = task["due_date"]
    if not task["active"] or not start or day < start:
        return False
    current = date.fromisoformat(day)
    if task["recurrence"] == "daily":
        return True
    if task["recurrence"] == "weekdays":
        return current.weekday() < 5
    if task["recurrence"] == "weekly":
        return current.weekday() == date.fromisoformat(start).weekday()
    return day == start


def task_summary(con, user_id, day):
    tasks = [
        dict(r) for r in con.execute("SELECT * FROM tasks WHERE user_id=?", (user_id,))
    ]
    logs = [
        dict(r)
        for r in con.execute(
            "SELECT l.* FROM task_logs l JOIN tasks t ON t.id=l.task_id WHERE t.user_id=?",
            (user_id,),
        )
    ]
    completed = {(r["task_id"], r["day"]) for r in logs}
    for t in tasks:
        repeating = t["recurrence"] != "none"
        t["done_today"] = (
            (t["id"], day) in completed if repeating else t["completed_day"] == day
        )
        t["done"] = t["done_today"] if repeating else bool(t["completed_at"])
        t["due_today"] = (
            scheduled(t, day)
            if repeating
            else bool(
                t["active"]
                and (
                    (t["due_date"] and t["due_date"] <= day and not t["done"])
                    or t["done_today"]
                )
            )
        )
        t["overdue"] = bool(
            not repeating
            and t["active"]
            and not t["done"]
            and t["due_date"]
            and t["due_date"] < day
        )
        t["next_due"] = None
        if t["active"] and not (not repeating and t["done"]):
            if not repeating:
                t["next_due"] = t["due_date"]
            else:
                cursor = max(date.fromisoformat(day), date.fromisoformat(t["due_date"]))
                if t["done_today"] and cursor.isoformat() == day:
                    cursor += timedelta(days=1)
                for i in range(8):
                    try:
                        candidate = (cursor + timedelta(days=i)).isoformat()
                    except OverflowError:
                        break
                    if scheduled(t, candidate):
                        t["next_due"] = candidate
                        break
    priority = {"high": 0, "normal": 1, "low": 2}
    tasks.sort(
        key=lambda t: (
            t["done"],
            not t["active"],
            not t["overdue"],
            priority[t["priority"]],
            t["due_date"] or "9999",
            t["id"],
        )
    )
    due = [t for t in tasks if t["due_today"]]
    week_start = (date.fromisoformat(day) - timedelta(days=6)).isoformat()
    completions = completed | {
        (t["id"], t["completed_day"]) for t in tasks if t["completed_day"]
    }
    balance = {d: 0 for d in DOMAINS}
    lookup = {t["id"]: t for t in tasks}
    for tid, completed_day in completions:
        if week_start <= completed_day <= day:
            balance[lookup[tid]["domain"]] += 1
    summary = {
        "planned_today": len(due),
        "completed_today": sum(t["done_today"] for t in due),
        "remaining_minutes": sum(t["minutes"] for t in due if not t["done"]),
        "committed_minutes": sum(t["minutes"] for t in due),
        "overdue": sum(t["overdue"] for t in tasks),
        "week_completions": sum(balance.values()),
        "week_by_domain": balance,
    }
    return tasks, summary
