# Architecture

## Product loop

Record a personal state → select a feasible action → do or skip it → rate usefulness → adjust future plans.

The stack is Python 3.12, FastAPI/Pydantic, SQLite, and a modular JavaScript browser interface. Authentication is a random opaque session cookie; the server stores only its SHA-256 digest. Password hashes use a random salt and scrypt. Session cookies are HttpOnly and SameSite=Strict; deployments must enable Secure cookies. Every mutating API request requires a custom header and is checked for cross-site origins. SQL values are parameterized, and every account-specific record mutation checks ownership.

## Data model

Users own check-ins, goals, habits, ledger entries, category budgets, recommended actions, experiments, reminders and feedback. Habit logs belong to habits; experiment logs belong to experiments. All relations use foreign keys with cascading deletion. The schema is recorded as version 1. New migrations must be explicit, tested upgrades; do not edit the version-1 schema as a substitute for migrating existing data.

One database connection is opened and closed per transaction. SQLite WAL mode supports this small-deployment setup. This is not a distributed, multi-writer architecture. Currency is fixed once financial records exist so amounts cannot silently acquire a new currency label. Amounts are integer cents/paisa.

## Personal state and recommendation algorithm

`engine.snapshot` composes actual user records and computes individual baselines from previous check-ins in the last 14 calendar days, excluding today's entry. It never fills missing mood, sleep or task values with zero. Pearson correlations require at least seven paired observations and nonzero variance. They are explicitly labeled associations.

`engine.candidates` creates small optional interventions from current reported context, unfinished goal next steps, chosen habits, budget overruns and selected priorities. Each recommendation contains a reason and a description of the evidence available, rather than an invented probability of benefit.

Candidate ranking:

1. Base contextual priority (for example, reported high stress makes a small pause more relevant).
2. Add 6 points for a user-selected priority area.
3. For the same recommendation key, add `8 × ((helpful + 1) / (rated + 2) − 0.5)`. This Beta(1,1)-smoothed estimate changes priority modestly while early feedback is sparse.
4. Sort candidates and fit at most five pending actions within the remaining daily development-time allowance.
5. Preserve completed and skipped actions on regeneration, subtracting completed-action time from the allowance.

This is feedback-based adaptive ranking. It does not establish that following a suggestion caused a later mood or health change. Goal progress is manually updated; completing an action does not inflate a goal score.

## Personal experiments

Each experiment shuffles a balanced sequence of A/B assignments across its days. For odd durations, A receives one extra day. There is at most one log per experiment/day, and logging again replaces that day's result. Only today's assigned active session can be logged. Outcomes summarize self-reported focus, completion and duration. Conclusions remain exploratory or preliminary; there are no fabricated significance values or causal certainty claims.

## Privacy and notifications

There is no third-party model request, analytics tracker or bank/wearable connection. Export excludes password and session hashes. Users can delete their records and account. SQLite files still contain sensitive plaintext records and require host-level encryption and restricted access in a real deployment.

Notification generation is idempotent per user, event and day. The browser polls when visible; optional browser notifications need explicit user permission. There is no closed-tab push, SMS or email delivery, and no emergency monitoring.

References: [FastAPI response cookies](https://fastapi.tiangolo.com/advanced/response-cookies/), [FastAPI testing](https://fastapi.tiangolo.com/tutorial/testing/), [Python sqlite3](https://docs.python.org/3.12/library/sqlite3.html).
