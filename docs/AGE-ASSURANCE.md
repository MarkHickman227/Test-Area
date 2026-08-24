# Age assurance

Self-declared date of birth is never collected or stored. Generation and checkout stay blocked until the provider outcome is `PASSED`.

## Providers

| `AGE_VERIFICATION_PROVIDER` | Behaviour |
| --- | --- |
| `sandbox` (default in development/test) | Local handoff. `POST /v1/age-verification/sandbox-complete` is allowed only when `APP_ENV` is `development` or `test` |
| `http` | `POST {AGE_VERIFICATION_API_URL}/v1/sessions` then HMAC webhook |

Production (`APP_ENV=production`) never accepts sandbox completion, even if `ALLOW_SANDBOX_AGE_VERIFY=true`.

## HTTP vendor contract

Create session:

```http
POST /v1/sessions
Authorization: Bearer $AGE_VERIFICATION_API_KEY
```

```json
{ "user_id": "...", "return_url": "...", "webhook_url": "https://api.example/v1/webhooks/age-verification" }
```

Expected response: `{ "session_id": "...", "handoff_url": "https://..." }`.

Webhook `POST /v1/webhooks/age-verification` with `X-Signature: sha256=...` over the raw body using `AGE_VERIFICATION_WEBHOOK_SECRET`:

```json
{ "session_id": "...", "user_id": "...", "outcome": "PASSED|FAILED|INCONCLUSIVE", "assurance_level": "high" }
```

Identity fields (`date_of_birth`, `document`, `selfie`, …) are dropped and never written. Provider references are stored encrypted plus a SHA-256 lookup hash. Raw webhook payloads are not retained. Welcome credits are idempotent (`welcome:{user_id}`). A later `FAILED` webhook does not downgrade an account that already `PASSED`.
