# Emailing Infrastructure

A bulk email-sending service built with **FastAPI** + **Celery** + **Redis**, using **ZeptoMail** as the delivery provider. It accepts a contact list (CSV/Excel), stores it in Redis, and sends personalized bulk emails in the background with sender rotation and built-in rate-limiting delays.

## Architecture

```
                ┌──────────────┐        enqueue task        ┌────────────────┐
 CSV/Excel ───▶ │  FastAPI API │ ─────────────────────────▶ │ Celery worker  │
 + messages     │  (main.py)   │                            │ (celery_task)  │
                └──────┬───────┘                            └───────┬────────┘
                       │  store / read contacts                     │ send via
                       ▼                                            ▼
                ┌──────────────┐                            ┌────────────────┐
                │    Redis     │ ◀── broker + data store ──▶ │   ZeptoMail    │
                └──────────────┘                            └────────────────┘
```

| Service | Role |
|---|---|
| `api` | FastAPI app ([main.py](main.py)) — upload contacts, manage messages, trigger sends |
| `celery_worker` | Runs the background `send_bulk_emails` task ([celery_task.py](celery_task.py)) |
| `celery_beat` | Celery scheduler (currently no periodic tasks defined) |
| `redis` | Celery broker/backend **and** the data store for contacts + saved messages |

## Tech stack

- **FastAPI** + **Gunicorn/Uvicorn** workers (API)
- **Celery** (background task processing)
- **Redis** (broker, result backend, and key/value data store)
- **ZeptoMail** via REST ([email_providers/zepto_mail_client.py](email_providers/zepto_mail_client.py)) — active provider
- **AWS SES** ([email_providers/aws_ses_provider.py](email_providers/aws_ses_provider.py)) — legacy, still used for HTML template rendering
- **pandas** (CSV/Excel parsing)
- **Docker / Docker Compose**

## Project layout

```
main.py                         FastAPI app and HTTP endpoints
celery_task.py                  Celery app, EmailBatchProcessor, send_bulk_emails task
config.py                       Env-driven configuration (Redis, AWS, ZeptoMail keys)
file_extractor.py               CSV/Excel -> list[dict] extraction (pandas)
serializers.py                  Pydantic request/response models
redis_service/redis_service.py  Thin Redis JSON get/set wrapper
email_providers/
  zepto_mail_client.py          ZeptoMail REST client (active sender)
  aws_ses_provider.py           AWS SES client + HTML template editor
  email_client.py               Email client adapter
templates/email_test.html       HTML email template
docker-compose.yml              api + celery_worker + celery_beat + redis
Dockerfile                      Python 3.10-alpine image
.github/workflows/deploy.yml    SSH-based deployment workflow
```

## Configuration

Environment variables (loaded from `.env`, see [config.py](config.py)):

| Variable | Purpose | Default |
|---|---|---|
| `REDIS_HOST` | Redis hostname (`redis` in Docker) | `localhost` |
| `ZEPTO_API_KEY` | ZeptoMail send-mail token | — |
| `AWS_REGION_NAME` | AWS region (legacy SES path) | — |
| `AWS_ACCESS_KEY_ID` | AWS access key (legacy SES path) | — |
| `AWS_SECRET_KEY` | AWS secret key (legacy SES path) | — |

> `.env` is git-ignored. Never commit real credentials.

### Sending behaviour ([BatchConfig](celery_task.py#L28-L40))

```python
batch_size = 25               # emails per batch
batch_delay_seconds = 900     # 15 min pause between batches
email_delay_seconds = 60      # 1 min between individual emails
rotation_delay_seconds = 180  # 3 min when content rotation triggers
rotation_intervals = [49, 99, 149, 199]
```

**Effective rate: one email every 60 seconds** during a batch (25 emails ≈ 25 min), then a 15-minute gap before the next batch. The number of selected senders does **not** change timing — it only changes which "from" address each email uses (senders rotate one-per-email).

> Note: because `batch_size` (25) is smaller than the first rotation interval (49), the per-batch index never reaches a rotation trigger, so content rotation / the 180s delay does not currently fire.

### Default senders ([celery_task.py](celery_task.py#L55-L60))

```python
EMAIL_SENDERS = [
    "marketing@roolimarketing.xyz",
    "lucia@roolimarketing.xyz",
    "richard@roolimarketing.xyz",
    "mariam@roolimarketing.xyz",
]
```

## Personalization

Message bodies and subjects support these placeholders, replaced per-recipient at send time ([celery_task.py](celery_task.py#L149-L160)):

- `{{first_name}}`
- `{{last_name}}`

The recipient's name comes from the **`Name`** column of the uploaded contact file, split on whitespace (first token → first name, second token → last name). Matching is done against the **`Emails`** column. Placeholder names are exact and case-sensitive — `{{Name}}`, `{Name}`, or `{{ first_name }}` will **not** be replaced.

**Required contact file columns:**

```csv
Name,Emails
John Doe,john@example.com
Mary Jane,mary@example.com
```

## API endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Health/welcome message |
| `POST` | `/extract-emails` | Upload a CSV/Excel file; stores contacts in Redis under key `email` |
| `GET` | `/get-emails` | Paginated list of stored contacts (`page`, `page_size`) |
| `POST` | `/message` | Save a reusable message (subject + body) |
| `GET` | `/messages` | List saved messages |
| `DELETE` | `/messages/{message_id}` | Delete a saved message |
| `POST` | `/send-bulk-emails` | Send to **all** stored contacts |
| `POST` | `/send-selected-emails` | Send to a provided `email_list` only |
| `GET` | `/email-senders` | List configured sender addresses |

Interactive docs are available at `/docs` (Swagger) and `/redoc`.

### Example: trigger a personalized bulk send

```bash
# 1) Upload contacts (CSV with Name,Emails columns)
curl -F "file=@contacts.csv" http://localhost:8000/extract-emails

# 2) Send to everyone
curl -X POST http://localhost:8000/send-bulk-emails \
  -H "Content-Type: application/json" \
  -d '{
        "subjects": ["Hey {{first_name}}, a special offer for you"],
        "bodies": ["Hi {{first_name}} {{last_name}},\n\nWe have something great..."],
        "senders": ["marketing@roolimarketing.xyz"]
      }'
```

`/send-selected-emails` takes the same payload plus an `email_list`:

```json
{
  "subjects": ["..."],
  "bodies": ["..."],
  "senders": ["marketing@roolimarketing.xyz"],
  "email_list": [{ "Emails": "john@example.com" }]
}
```

> Personalization for selected sends still looks names up from the **previously uploaded** contact list in Redis, matched by email.

## Running locally (Docker Compose)

```bash
# 1. Create .env (see Configuration above)
# 2. Build and start everything
docker compose up -d --build

# API:        http://localhost:8000
# Swagger UI: http://localhost:8000/docs
```

This starts the API, a Celery worker, Celery beat, and Redis. Redis is configured with AOF persistence (`--appendonly yes`) and a named volume (`redis_data`) so contacts survive restarts.

> **Data persistence:** stored contacts live in Redis. Set `COMPOSE_PROJECT_NAME` consistently so Compose always reuses the same `*_redis_data` volume across deploys — otherwise a fresh empty volume is created and contacts appear to "disappear."

## Running without Docker

```bash
python -m venv env && source env/bin/activate
pip install -r requirements.txt

# Start Redis (e.g. via Docker) and set REDIS_HOST accordingly, then:
# Terminal 1 - API
gunicorn main:app -k uvicorn.workers.UvicornWorker --workers 4 --bind 0.0.0.0:8000
# Terminal 2 - Celery worker
celery -A celery_task worker --loglevel=info
```

## Deployment

A GitHub Actions workflow ([.github/workflows/deploy.yml](.github/workflows/deploy.yml)) deploys on push to `main` (or manually). It SSHes into the target server, syncs the repo to `origin/main`, and rebuilds the Compose stack.

Required repository secrets: `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_SSH_KEY`, `DEPLOY_PORT`, `DEPLOY_PATH`, `DEPLOY_REPO_URL`. The server must already have a valid `.env`.

## Task statistics

`send_bulk_emails` returns a summary, and `get_sending_stats(task_id)` can be used to query a task's status:

```python
{
    "total_emails": 500,
    "batches_processed": 3,
    "successful": 487,
    "failed": 13,
    "errors": [ { "email": {...}, "error": "..." } ]
}
```
