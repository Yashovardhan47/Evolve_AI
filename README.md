# Evolve AI

**AI Personal Development OS** — a Python full-stack workspace for turning personal intentions into practical, repeatable actions.

Evolve combines daily self-reflection, physical and mental wellbeing observations, financial awareness, goals, learning, communication and habits. Its recommendation engine uses the context a user actually records and learns from their usefulness feedback. It does not infer personality or health from face photos.

## What works

- Account creation, sign-in and sign-out with salted scrypt password hashes and expiring HttpOnly sessions.
- A responsive dashboard, ten functional views, accessible forms, data charts and reduced-motion support.
- A separate personal Profile page with optional contact/location, education, occupation, interests, strengths, challenges, routine and development direction. The dashboard reflects saved names and profile context.
- Optional daily mood, energy, stress, focus, sleep, movement and task check-ins. Missing entries stay missing.
- Goals with editable next steps, target dates and user-reported progress; habits with daily completion and streaks.
- A personal state model with recent individual baselines and explicitly noncausal associations.
- Explainable, time-constrained action plans with completion, skipping and usefulness feedback. Smoothed feedback adjusts the ranking of future suggestions.
- Income/expense records, reusable monthly category budgets and overspending alerts. Money uses integer minor units, not floating-point totals.
- Balanced, randomized personal experiments comparing everyday routines, with session logs and descriptive outcomes.
- A what-if calculator for time commitments and recorded spending. Its output is arithmetic, not a predicted health or financial outcome.
- In-app reminders for daily check-ins, goal dates and budget reviews; optional browser notifications while the tab is open.
- Editable priorities, timezone, currency, daily time budget and reminder preferences.
- User feedback, complete JSON data export, deletion of individual records, and password-confirmed account deletion with cascading data removal.
- Separate demo accounts populated with fictional records; 24-hour expiry and cleanup at startup and on demo creation.

## Hosted inspection demo

[Open the interactive demo](https://evolve-ai-demo.kummarayashovardhan.chatgpt.site). This separate hosted demo uses fictional browser-local records; it includes the Profile page and dashboard summary but does not run the Python API.

## Run locally — Windows PowerShell

From the repository root:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.lock
cd backend
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

Open **http://localhost:8000**. FastAPI serves the HTML/CSS/JavaScript frontend and the Python API together, so there is no separate Node server. The database defaults to `backend/data/evolve.db` when started from `backend`.

## Run locally — Linux / macOS

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.lock
cd backend
../.venv/bin/python -m uvicorn app.main:app --reload --port 8000
```

Create an account for an empty personal workspace, or choose **Try an interactive demo**. No API key is required. The attached face image is not needed and is not included in the repository.

## Docker

```bash
docker compose up --build
```

The named volume preserves SQLite records across container restarts. This runs on localhost HTTP by default. Before using a real HTTPS domain, set `EVOLVE_SECURE_COOKIES=true`, terminate TLS at a trusted reverse proxy and configure `EVOLVE_ORIGINS` only if needed. See [deployment](docs/deployment.md).

## Verify

```bash
pip install -r backend/requirements.lock -r backend/requirements-dev.txt
cd backend
python -m pytest -q
```

From the root, `node --check frontend/app.js` checks JavaScript syntax. The API integration tests cover account boundaries, authentication, request protection, validation, money precision, planner feasibility, experiments, notifications, timezone behavior, export and deletion. CI repeats these checks on pushes and pull requests. Browser walkthrough results are recorded in [validation](docs/validation.md).

## Architecture and scope

The frontend calls same-origin `/api` routes; FastAPI validates requests; SQLite stores account-owned data; the recommendation engine computes context and prioritizes feasible actions. [Architecture](docs/architecture.md) describes the model and algorithm. OpenAPI is available at `/openapi.json`, and readiness at `/api/health`.

This is a working first release, not evidence of clinically validated wellbeing improvement or guaranteed user outcomes. The recommendation engine is an interpretable adaptive baseline, not an LLM or a medically validated digital twin. Causal counterfactual prediction, wearable/bank connections, Google OAuth, verified email/password recovery, push delivery with the app closed, encryption-at-rest infrastructure and large-scale database deployment are not implemented. These boundaries are visible in the interface and [roadmap](docs/roadmap.md).

MIT licensed. Built for Yashovardhan's AI Personal Development OS project.
