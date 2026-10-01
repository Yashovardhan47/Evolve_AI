# Validation — release 1

## Verified

- **16 API integration/algorithm tests pass** with Python 3.12. The tests use isolated temporary databases.
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
