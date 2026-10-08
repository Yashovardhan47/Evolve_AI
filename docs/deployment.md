# Deployment

## Working deployment target

Use a Python 3.12 web-service host or Docker host with a persistent disk. The frontend and backend share one origin and one service. This Python backend is not a static site or a Cloudflare JavaScript Worker.

Build: `pip install -r backend/requirements.lock`.

Start from repository root:

```bash
python -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000
```

Set `EVOLVE_DB` to a path on the persistent disk. Set `EVOLVE_SECURE_COOKIES=true` and a private random `EVOLVE_JWT_SECRET` of at least 32 bytes for HTTPS. If a reverse proxy changes the internal origin, set `EVOLVE_ORIGINS=https://your-domain.example`. Do not enable wildcard origins or trust forwarded headers from arbitrary clients. Adjust the port to the host's required port. `/api/health` exercises database connectivity.

Run a single application process for the SQLite release. Keep the database and WAL files out of the public web directory and restrict disk access. The frontend directory alone is mounted as static assets. Use HTTPS, host-level encryption, a defined retention policy and off-host backups before inviting real users.

## Backup and restore

Use SQLite's backup API to create a consistent snapshot rather than copying a live database's primary file without its WAL. Test restoring a backup to a separate path before relying on it. Store backup files securely; they contain personal records. Deleting an account removes live records, but backups require their own retention and deletion policy.

## Not configured here

The hosted inspection demo is browser-only. No Python backend URL has been deployed. A real deployment needs an authorized Python hosting service, a persistent disk and a configured HTTPS origin. Email verification/password reset, account recovery, background push/email delivery, monitoring, scalable rate limiting, external consented integrations, encrypted backups and PostgreSQL migrations are follow-up work. These are not silently simulated.

## Authentication deployment

Configure Google web-client credentials and the exact callback URI as described in [authentication setup](authentication.md). JWT signing keys and Google client secrets belong in the host secret store. Missing Google settings leave its sign-in button disabled; they never create a fake Google identity. Startup rejects missing/short production JWT secrets. All instances must share the same key and database; the current SQLite deployment uses a single process. Do not log OAuth callback query strings, authorization headers, cookies, ID tokens or secrets. Use `--no-access-log` or a proxy/application logging policy that redacts callback queries.
