# Architecture

## Product loop

Record a personal state → select a feasible action → do or skip it → rate usefulness → adjust future plans.

The stack is Python 3.12, FastAPI/Pydantic, SQLite, and a modular JavaScript browser interface. Authentication is a random opaque session cookie; the server stores only its SHA-256 digest. Password hashes use a random salt and scrypt. Session cookies are HttpOnly and SameSite=Strict; deployments must enable Secure cookies. Every mutating API request requires a custom header and is checked for cross-site origins. SQL values are parameterized, and every account-specific record mutation checks ownership.

## Data model

Users own check-ins, goals, tasks, habits, ledger entries, category budgets, recommended actions, experiments, reminders and feedback. Task logs belong to tasks; habit logs belong to habits; experiment logs belong to experiments. All relations use foreign keys with cascading deletion. Schema version 2 adds tasks, task_logs and an account/due-date index with additive CREATE IF NOT EXISTS statements. Existing version-1 tables and records are preserved; the upgrade is idempotent.

One database connection is opened and closed per transaction. SQLite WAL mode supports this small-deployment setup. This is not a distributed, multi-writer architecture. Currency is fixed once financial records exist so amounts cannot silently acquire a new currency label. Amounts are integer cents/paisa.

## Personal state and recommendation algorithm

`engine.snapshot` composes actual user records and computes individual baselines from previous check-ins in the last 14 calendar days, excluding today's entry. It never fills missing mood, sleep or task values with zero. Pearson correlations require at least seven paired observations and nonzero variance. They are explicitly labeled associations.

`engine.candidates` creates small optional interventions from current reported context, unfinished goal next steps, chosen habits, budget overruns and selected priorities. Each recommendation contains a reason and a description of the evidence available, rather than an invented probability of benefit.

Candidate ranking:

1. Base contextual priority (for example, reported high stress makes a small pause more relevant).
2. Add 6 points for a user-selected priority area.
3. For the same recommendation key, add `8 × ((helpful + 1) / (rated + 2) − 0.5)`. This Beta(1,1)-smoothed estimate changes priority modestly while early feedback is sparse.
4. Sort candidates and fit at most five pending actions within the remaining daily development-time allowance.
5. Preserve completed and skipped actions on regeneration, subtracting completed-action time and all of today's scheduled task estimates from the allowance. Task time remains reserved after completion to avoid using the same time twice. If the user schedules more than their allowance, no further pending suggestions are added; the dashboard shows the excess. Previously completed actions remain recorded.

This is feedback-based adaptive ranking. It does not establish that following a suggestion caused a later mood or health change. Goal progress is manually updated; completing an action does not inflate a goal score.

## Personal tasks and routines

Each task has an account owner, one of six life areas, a custom interest, notes, priority, estimated minutes, optional date, recurrence and active state. An undated one-time task is an inbox item. Dated unfinished one-time tasks carry into Today when overdue; they can be rescheduled explicitly. Daily, Monday–Friday and weekly tasks evaluate the account's local date on each request, so a scheduler is not required to create recurring occurrences. Repeating tasks require a start date; weekly tasks use its weekday.

One-time completions have a completion timestamp and local completion day. Repeating completions use a unique task/day log; repeated completion requests are idempotent. Future and unscheduled recurring tasks cannot be completed. Editing a repeat rule retains previous completion logs, including when converting a completed one-time task into a routine. Pausing excludes future commitments; deletion cascades to its logs. Undo removes the applicable completion. Historical counts use the task's current life-area classification.

`PUT /api/tasks/{id}/completion` changes today's occurrence; POST/PUT/DELETE task routes validate and check ownership. State includes derived done/due/overdue/next-date fields, automatic daily counts and seven-day completions by area. Tasks and occurrence logs are included in export and account deletion. Mutations rebuild the optional suggestion plan after saving the task. Manual check-in counts are retained separately and are never replaced with task counters.

## Personal experiments

Each experiment shuffles a balanced sequence of A/B assignments across its days. For odd durations, A receives one extra day. There is at most one log per experiment/day, and logging again replaces that day's result. Only today's assigned active session can be logged. Outcomes summarize self-reported focus, completion and duration. Conclusions remain exploratory or preliminary; there are no fabricated significance values or causal certainty claims.

## Privacy and notifications

There is no third-party model request, analytics tracker or bank/wearable connection. Export excludes password and session hashes. Users can delete their records and account. SQLite files still contain sensitive plaintext records and require host-level encryption and restricted access in a real deployment.

Notification generation is idempotent per user, event and day. The browser polls when visible; optional browser notifications need explicit user permission. There is no closed-tab push, SMS or email delivery, and no emergency monitoring.

References: [FastAPI response cookies](https://fastapi.tiangolo.com/advanced/response-cookies/), [FastAPI testing](https://fastapi.tiangolo.com/tutorial/testing/), [Python sqlite3](https://docs.python.org/3.12/library/sqlite3.html).
