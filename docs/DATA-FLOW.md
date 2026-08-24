# Data flow (Phase 1)

```
Browser -> Caddy -> Next.js (UI)
                 -> FastAPI /v1
                        -> Postgres (accounts, jobs, ledger, audit)
                        -> Redis (queue when Celery enabled)
                        -> MinIO / local disk (private originals + thumbs)
                        -> Mail (verification)
                        -> Age-assurance provider adapter (sandbox in MVP)
                        -> worker-control -> MockWorker or ComfyUI (gpu_net)
```

Personal data categories:

- Account: email, password hash, role, status
- Age assurance: outcome, assurance level, encrypted provider reference
- Generation: encrypted prompts, parameters, private images
- Billing: credit ledger events (no card data in MVP)
- Security: hashed IPs on sessions, audit events

Prompts and outputs are not copied to development or used for training.
