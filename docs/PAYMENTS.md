# Payments

Default: `PAYMENTS_ENABLED=false`. Do not turn on live card charging unless a processor confirms this adult service in writing. Having Stripe keys in the environment is not approval.

## Providers

| `PAYMENT_PROVIDER` | Behaviour |
| --- | --- |
| `none` (default) | Checkout and webhooks return `PAYMENTS_NOT_ENABLED` / `PAYMENTS_NOT_CONFIGURED` |
| `sandbox` | Local checkout + `POST /v1/billing/sandbox-complete` or HMAC webhook |
| `stripe` | Checkout Sessions via HTTPS. Webhooks require `Stripe-Signature`. Off unless enabled |

Credit grants use append-only `PURCHASED_CREDITS` rows keyed by `purchase:{payment_id}` so retries are idempotent. Age assurance must be `PASSED` before checkout.

Sandbox HMAC (`X-Signature: sha256=...`) uses `PAYMENT_WEBHOOK_SECRET`. Stripe uses `STRIPE_WEBHOOK_SECRET`. Card numbers are never stored.

Paid Creator plan changes are sandbox-only until a processor is approved.
