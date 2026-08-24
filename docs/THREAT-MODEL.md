# Threat model (Phase 1 draft)

Scope: PrivateCanvas control plane, web UI, MockWorker/ComfyUI worker, Postgres, Redis, object storage.

## Assets

- Account credentials and sessions
- Age-assurance outcomes
- Encrypted prompts
- Private generated images
- Credit ledger
- Admin/moderator tools

## Key threats and controls

1. Child access to adult generation — email verification plus external age assurance; generation and checkout blocked until PASSED.
2. Prohibited prompt reaching GPU — deterministic policy gate before queue; held jobs skip workers.
3. Public exposure of outputs — private buckets, owner-scoped queries, short-lived or proxied downloads, no public gallery.
4. Direct ComfyUI abuse — GPU network isolated; users cannot submit workflow JSON.
5. Credit theft / double spend — append-only ledger, idempotent reservations, reconciliation view.
6. Privileged snooping — RBAC, MFA for privileged roles, audited access, break-glass with reason and TTL.
7. Webhook forgery — HMAC verification for age-assurance and payment callbacks; identity documents and dates of birth are never stored.
8. CSRF / session theft — HttpOnly session cookie, CSRF header on mutations, SameSite=Lax.

This document is a working draft for engineering, not a completed security sign-off.
