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
| `PUBLIC_API_URL` | Public HTTPS API origin used in unsubscribe links | `http://localhost:8000` |
| `UNSUBSCRIBE_SECRET` | Long random secret used for stable unsubscribe tokens | Redis-generated if omitted |
| `BUSINESS_NAME` | Legal or trading name shown in every email footer | `Rooli` |
| `BUSINESS_COPYRIGHT` | Copyright identity shown in every email footer | `© 2026 Rooli — A Cresthub Media Limited Company. All rights reserved.` |
| `BUSINESS_ADDRESS` | Optional postal address shown in every email footer | — |
| `BUSINESS_CONTACT_EMAIL` | Contact address shown in every email footer | `marketing@roolimarketing.xyz` |
| `BUSINESS_WEBSITE_URL` | Website linked from every email footer | `https://rooli.co/` |
| `AWS_REGION_NAME` | AWS region (legacy SES path) | — |
| `AWS_ACCESS_KEY_ID` | AWS access key (legacy SES path) | — |
| `AWS_SECRET_KEY` | AWS secret key (legacy SES path) | — |

> `.env` is git-ignored. Never commit real credentials.

For production, set `PUBLIC_API_URL` to the public HTTPS address of this API. `UNSUBSCRIBE_SECRET` is optional because a durable value is generated and stored in Redis when it is blank. Identity and contact settings use the defaults above when they are missing or blank; set `BUSINESS_ADDRESS` only when you have the real postal address.

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

The recipient's name comes from the **`Name`** column of the uploaded contact file. The first token becomes the first name and the remainder becomes the last name. Matching is done against the **`Emails`** column.

The message composer exposes a Variables menu, which can also be opened by typing `/`. In addition to `first_name`, `last_name`, `full_name`, and `email`, every uploaded CSV heading is available after normalization. For example, `Name of Gp` becomes `{{name_of_gp}}` and `Company` becomes `{{company}}`. Unknown variables remain visible so template mistakes are not silently hidden.

**Required contact file columns:**

```csv
Name,Emails
John Doe,john@example.com
Mary Jane,mary@example.com
```

## Follow-up sequences

Selected message templates can be ordered into a sequence. The first step sends immediately; each later step stores its own wait duration. Sequence definitions, recipient enrolments, delivery history, retry state, and due times are persisted in Redis. Celery Beat checks the Redis schedule every 30 seconds and the worker preserves a one-email-per-minute send rate.

Each recipient is pinned to the same sender for the entire sequence. Follow-ups use the initial subject with a `Re:` prefix and include `Message-ID`, `In-Reply-To`, and `References` headers so compatible email clients display the messages in one thread. Provider failures are retried twice at five-minute intervals.

## Campaign workspaces and delivery tracking

Contacts, message templates, variables, and sequences are scoped by campaign. Existing global data is migrated automatically into the `General Campaign` the first time campaigns are loaded. New campaigns use separate Redis keys, so importing contacts in one campaign does not replace another campaign's audience.

The campaign summary reports planned, sent, not-sent, and failed message counts. `Sent` means ZeptoMail accepted the request; `not sent` includes future scheduled steps and failed steps. Recipient-level status, sender, last activity, next run time, and provider error information are retained in the Redis sequence enrolment records.

Every outgoing message includes a visible unsubscribe link plus RFC 8058 `List-Unsubscribe` and `List-Unsubscribe-Post` headers. Unsubscribe tokens are opaque and stored in Redis. A confirmed unsubscribe adds the normalized address to the global Redis suppression list, and both new enrolments and individual send tasks check that list before contacting the provider. This also prevents later follow-ups from being sent after a recipient opts out.

## API endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Health/welcome message |
| `GET` | `/unsubscribe/{token}` | Show the recipient unsubscribe confirmation page |
| `POST` | `/unsubscribe/{token}` | One-click unsubscribe and add the address to suppression |
| `POST` | `/campaigns` | Create a campaign workspace |
| `GET` | `/campaigns` | List campaign workspaces and their contact/message counts |
| `GET` | `/campaigns/{campaign_id}/summary` | Get delivery totals, sequence summaries, and recipient tracking |
| `POST` | `/extract-emails` | Upload contacts for a campaign (`campaign_id` query parameter) |
| `GET` | `/get-emails` | Paginated campaign contacts (`campaign_id`, `page`, `page_size`) |
| `POST` | `/message` | Save a reusable campaign message (`campaign_id`) |
| `GET` | `/messages` | List messages for a campaign (`campaign_id`) |
| `PUT` | `/messages/{message_id}` | Update a saved message's subject and body |
| `DELETE` | `/messages/{message_id}` | Delete a saved message |
| `POST` | `/send-bulk-emails` | Send to **all** stored contacts |
| `POST` | `/send-selected-emails` | Send to a provided `email_list` only |
| `GET` | `/email-senders` | List configured sender addresses |
| `GET` | `/template-variables` | List computed and CSV-derived template variables |
| `POST` | `/sequences/start` | Persist and start a follow-up sequence |
| `GET` | `/sequences` | List sequences |
| `GET` | `/sequences/{sequence_id}` | Get sequence configuration and recipient status counts |
| `POST` | `/sequences/{sequence_id}/pause` | Pause pending sequence steps |
| `POST` | `/sequences/{sequence_id}/resume` | Resume a paused sequence |
| `POST` | `/sequences/{sequence_id}/cancel` | Cancel pending sequence steps |

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
