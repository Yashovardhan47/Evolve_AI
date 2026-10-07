# Validation — release 1 with daily task planner

## Verified

- **26 API integration/algorithm tests pass** with Python 3.12. The tests use isolated temporary databases.
- JavaScript syntax checks pass for the browser application and helper modules.
- A headless Chromium walkthrough exercises all nine views at desktop (1440 × 1050) and mobile (390 × 844) sizes, with no uncaught JavaScript errors or unintended body overflow.
- Browser flows verified: isolated demo account, real account creation, preferences, goal creation, a transaction with decimal precision, randomized experiment creation and result logging, check-in update and plan refresh, and arithmetic scenario comparison.
- Desktop and mobile screenshots were visually inspected. A desktop-only navigation visibility issue and excessive side-card stretching were corrected.

## Backend coverage

Authentication and logout, HttpOnly/SameSite/Secure cookie configuration, private API cache headers, origin/request protection, persisted authentication throttling, cross-user goal/habit/financial/notification/experiment isolation, missing-value handling, date validation, individual timezones, exclusion of today's values from its baseline, daily plan feasibility, preservation of completed actions, usefulness-based rank changes, integer-money arithmetic, currency locking, budget alerts, reminder deduplication, randomized balanced assignments, log upserts, export secret exclusion, and cascading account deletion.

## Limits of verification

- Docker configuration is provided; Docker is not installed in the build workspace, so a container build was not run.
- No public Python deployment, email/push provider, external integration or wearable device was available to verify.
- Browser checks and a visual review do not replace an accessibility audit across assistive technologies.
- No pilot-user study, model-calibration study, clinical validation or financial-outcome study has been performed. The application stores feedback; it does not claim positive feedback already exists.
- The installed Starlette test client emits an upstream deprecation warning for the HTTPX testing adapter; the tests pass.

## Personal profile update

The new Profile route and name/context dashboard summary are implemented in both the Python application and the hosted inspection demo. Additional tests verify validation, legacy profile compatibility, account isolation, preference preservation, name persistence through login and inclusion in export.

A Chromium profile walkthrough verifies saving personal fields, reflecting the name/context on the dashboard, reload persistence, and a 390-pixel mobile layout without body overflow.

## Daily task planner update

Seven added tests cover six life areas, validation, private CRUD, completion/undo idempotence, overdue handling, rescheduling, recurring weekdays/weekends/weekly dates, pausing, retained history when converting a task into a routine, time reservation, notification preferences/deduplication, export and cascading deletion. Reinitializing a populated database preserves tasks.

A Chromium walkthrough at 1440 × 1050 and 390 × 844 verifies adding a task, completing/undoing it, automatic dashboard counts, interest search, moving to tomorrow, editing, reload persistence, creating/pausing a recurring routine and deleting it. No uncaught JavaScript errors or body overflow were observed. Desktop/mobile task screenshots were inspected. Syntax, Ruff E9/F, formatting and whitespace checks pass.

The hosted demo's browser adapter is checked with Node for task CRUD, completion, validation, history, time reservation, export and reload from local storage. It remains an inspection demo; these checks do not establish a deployed Python backend or closed-tab reminder delivery.
