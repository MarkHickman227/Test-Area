# LinkedIn Standalone Agent

A standalone LinkedIn post scheduling agent built with FastAPI, SQLAlchemy,
Celery, Redis, and a small web dashboard.

The agent lets you:

- Sign in with LinkedIn OAuth 2.0.
- Store the connected LinkedIn profile server-side.
- Schedule LinkedIn text posts for future publishing.
- Publish posts through a Celery worker with retry/backoff.
- Cancel pending posts before they publish.
- Track pending, retrying, published, failed, and cancelled states.
- Run locally or deploy with Docker Compose.

The app never hardcodes credentials. LinkedIn credentials and deployment
settings are loaded from `.env`.

## Requirements

- Docker and Docker Compose for deployment.
- A LinkedIn Developer application with the redirect URI configured.
- LinkedIn API access for `w_member_social`.

## LinkedIn setup

In the LinkedIn Developer Portal:

1. Create or open your app.
2. Add the product/API access that allows posting with `w_member_social`.
3. Add this OAuth redirect URL for local Docker using the default port:

   ```text
   http://localhost/auth/callback
   ```

   If you set `HOST_PORT=8000`, use:

   ```text
   http://localhost:8000/auth/callback
   ```

   For a VPS or production domain, use:

   ```text
   https://your-domain.com/auth/callback
   ```

4. Copy the Client ID and Client Secret into `.env`.

## Configuration

Copy the example environment file:

```bash
cp .env.example .env
```

Edit `.env`:

```env
APP_ENV=production
DEBUG=False
LOG_LEVEL=INFO
HOST_PORT=80

LINKEDIN_CLIENT_ID=your-client-id
LINKEDIN_CLIENT_SECRET=your-client-secret
LINKEDIN_REDIRECT_URI=http://localhost/auth/callback
LINKEDIN_SCOPES=openid profile w_member_social

SESSION_COOKIE_SECURE=False
```

Set `SESSION_COOKIE_SECURE=True` when serving the app over HTTPS.
Set `HOST_PORT=8000` if port 80 is already used on your machine.

By default, standalone Docker deployment uses SQLite in a Docker volume:

```env
DATABASE_URL=sqlite:///./data/linkedin_agent.db
```

You can use PostgreSQL instead by setting `DATABASE_URL` to a PostgreSQL
connection string.

## Deploy with Docker Compose

```bash
docker compose up --build -d
```

Open:

```text
http://localhost
```

Check status:

```bash
docker compose ps
docker compose logs web
docker compose logs worker
```

If the site is not reachable:

```bash
docker compose ps
docker compose logs web
curl -I http://localhost
```

On a VPS, confirm port 80 is allowed by the server firewall/security group. If
you use a non-default port, set `HOST_PORT=8000`, redeploy, and open
`http://your-server-ip:8000`.

The Compose stack includes:

- `web` - FastAPI dashboard and API.
- `worker` - Celery worker that publishes scheduled posts.
- `redis` - Celery broker/result backend.
- `linkedin-agent-data` - persisted SQLite data volume.

## Local development

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
uvicorn app.main:app --reload
```

Run Redis locally before scheduling posts:

```bash
docker run --rm -p 6379:6379 redis:7-alpine
```

Run the worker:

```bash
celery -A app.core.celery_app.celery_app worker --loglevel=INFO
```

## Tests

```bash
pytest
python -m compileall app
```

## Security notes

- Keep `.env` private and out of source control.
- Use HTTPS in production and set `SESSION_COOKIE_SECURE=True`.
- The browser receives an HTTP-only session cookie only; it does not receive
  LinkedIn access tokens.
- LinkedIn tokens are stored server-side for scheduled publishing.
- Review LinkedIn platform rules and rate limits before increasing volume.
