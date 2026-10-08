# Authentication setup and verification

The Python application supports email/password authentication and Google OpenID Connect. Both issue the same Evolve JWT session. The separate hosted inspection demo remains browser-only and performs neither real authentication method.

## JWT sessions

- A 15-minute HS256 access JWT has a fixed issuer/audience, issued-at, expiry, user subject and random session identifier. Requests also check that the corresponding server session is live; logout and refresh invalidate the old JWT immediately.
- A distinct random refresh credential rotates on each successful refresh. Its digest is stored in SQLite, its lifetime is limited to the original seven-day session (one day for demos), and replay of an old credential is rejected.
- Browser credentials use HttpOnly, SameSite=Strict cookies. Refresh cookies are scoped to `/api/auth`; production enables Secure. Tokens are not placed in localStorage or returned in URL fragments. The browser retries protected requests once after a successful refresh, including restoration on reload.
- Protected API routes accept `Authorization: Bearer <access JWT>` as well. Every mutation, including refresh/logout, retains the request protection header/origin checks. Google ID tokens are never accepted as Evolve access tokens.
- Set `EVOLVE_JWT_SECRET` to a private random value containing at least 32 bytes. HTTPS mode refuses to start without it. Local HTTP development generates a persistent random key in the private database if the variable is empty. Back up/protect that database and its signing key; changing the key invalidates existing access tokens.
- Existing opaque cookies from earlier releases require a new sign-in. Existing accounts and development records are retained.

## Enable Google in the Python application

Create a Google Cloud OAuth **Web application** client and configure its consent screen/audience. If the project is in testing mode, add the intended test accounts. Register this exact local callback URI:

`http://localhost:8000/api/auth/google/callback`

Set these process environment variables through your local shell or hosting secret store:

| Variable | Value |
| --- | --- |
| `EVOLVE_GOOGLE_CLIENT_ID` | Your Google web-client ID |
| `EVOLVE_GOOGLE_CLIENT_SECRET` | Its private client secret |
| `EVOLVE_GOOGLE_REDIRECT_URI` | Exact registered callback URI |
| `EVOLVE_JWT_SECRET` | Private random signing key, required with HTTPS |

Restart the Python server and open **http://localhost:8000**. The hostname must match your callback: `localhost` and `127.0.0.1` are different cookie origins. Use your public HTTPS origin and the same callback path for a deployed Python service. Non-localhost HTTP callbacks are refused. The app does not load `.env` automatically; Docker Compose passes these variables from its environment or root `.env`.

`GET /api/auth/config` reports whether the server has usable configuration; it never returns client secrets, signing keys or credentials. “Enabled” means configured, not that Google has approved or a real login has been observed. Missing settings keep the Google button disabled with an explanation.

## Sign-in and account linking

Choose **Continue with Google** to create an account or return to an existing Google identity. The backend exchanges the code, checks RS256 against Google's signing keys, and validates issuer, audience, authorized party, expiry, issued-at, nonce and verified email. State is single-use with a ten-minute expiry, and code exchange includes S256 PKCE. Only basic identity scopes are requested; Google access/refresh tokens are discarded.

If your email already belongs to a password account, sign in with that password. In **Your preferences → Account sign-in**, choose **Connect my Google account**, confirm your password, then select Google with the matching email. No account is silently linked just because its email matches. Linking is bound to the existing live session; logout invalidates pending link attempts.

Google-only accounts have no fabricated local password. Their deletion flow asks for the same connected Google identity again before removing account records. Password-based accounts retain password-confirmed deletion.

Cancellation and provider failures return a clear sign-in message without replacing the current account. Invalid, missing, expired or replayed state is rejected before exchanging the code. Restrict logs so OAuth callback query strings, cookies and tokens are not captured.

## Verification boundary

Automated integration tests exercise real JWT signing/validation, rotation, expiry, request protection, revoked sessions, cryptographic RS256 identity validation and the full callback/link/delete flow against an intercepted test provider. Tests supply generated RSA keys and test-only identity claims; they do not log into a real Google account.

A live Google test requires configured credentials, consent/test-user settings, internet access from the Python host to Google's token/JWKS endpoints and a registered callback. No real Google credential has been supplied in this session, so live provider verification remains pending.

Provider references: [Google OpenID Connect](https://developers.google.com/identity/openid-connect/openid-connect), [PyJWT 2.10.1 validation](https://pyjwt.readthedocs.io/en/2.10.1/usage.html).
