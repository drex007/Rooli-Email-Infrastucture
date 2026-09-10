# main.py
from html import escape
from math import ceil
from celery_task import EMAIL_SENDERS, dispatch_due_sequence_emails, send_bulk_emails
from config import SENDERS
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi import UploadFile
from fastapi.responses import HTMLResponse
import file_extractor
from redis_service.redis_service import RedisService
from serializers import (
    BulkEmailResponse,
    CampaignPayload,
    EmailMessageListPayload,
    EmailMessageListSerializer,
    EmailMessagePayload,
    EmailMessageSample,
    ExtractedFileSerializer,
    MailBodySerializer,
    SendersPayload,
    SendersSerializer,
    StartSequencePayload,
    StartSequenceResponse,
    TemplateVariablesResponse,
)
import uuid
import time

from sequence_store import SequenceStore
from template_renderer import build_recipient_context, discover_template_variables
from campaign_store import CampaignStore, DEFAULT_CAMPAIGN_ID
from email_identity import get_business_identity
from suppression_store import SuppressionStore


app = FastAPI(
    title="Code Emailing Infrastructure",
    description="A basic code emailing infrastructure API built with FastAPI.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


redis_service = RedisService()
sequence_store = SequenceStore(redis_service)
campaign_store = CampaignStore(redis_service)
suppression_store = SuppressionStore(redis_service)


def _get_campaign_or_404(campaign_id: str):
    if campaign_id == DEFAULT_CAMPAIGN_ID:
        campaign_store.ensure_default_campaign()
    campaign = campaign_store.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found.")
    return campaign


@app.get("/")
async def root():
    return {"message": "Welcome to FastAPI", "docs": "/docs", "redoc": "/redoc"}


def _unsubscribe_page(title: str, message: str, token: str = "") -> str:
    identity = get_business_identity()
    safe_title = escape(title)
    safe_message = escape(message)
    safe_business_name = escape(identity["business_name"])
    safe_business_email = escape(identity["business_contact_email"])
    action = f'/unsubscribe/{escape(token)}' if token else ""
    button = (
        f'<form method="post" action="{action}"><button type="submit">Unsubscribe</button></form>'
        if token
        else ""
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{safe_title}</title><style>
body{{margin:0;background:#f5f5f7;color:#27272a;font-family:Arial,sans-serif}}main{{max-width:520px;margin:10vh auto;padding:32px;background:#fff;border-radius:20px;box-shadow:0 20px 60px rgba(0,0,0,.1)}}
h1{{font-size:24px}}p{{color:#62626b;line-height:1.6}}button{{border:0;border-radius:10px;background:#dc2626;color:#fff;padding:12px 18px;font-weight:700;cursor:pointer}}small{{display:block;margin-top:28px;color:#8b8b94}}
</style></head><body><main><h1>{safe_title}</h1><p>{safe_message}</p>{button}<small>{safe_business_name} · {safe_business_email}</small></main></body></html>"""


@app.get("/unsubscribe/{token}", response_class=HTMLResponse)
def confirm_unsubscribe(token: str):
    if not suppression_store.resolve_unsubscribe_token(token):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid unsubscribe link.")
    return HTMLResponse(_unsubscribe_page(
        "Unsubscribe from emails?",
        "Confirm that you no longer want to receive marketing emails from us.",
        token,
    ))


@app.post("/unsubscribe/{token}", response_class=HTMLResponse)
def unsubscribe(token: str):
    token_data = suppression_store.resolve_unsubscribe_token(token)
    if not token_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid unsubscribe link.")
    suppression_store.suppress(
        token_data["email"],
        reason="unsubscribe",
        campaign_id=token_data.get("campaign_id", DEFAULT_CAMPAIGN_ID),
    )
    return HTMLResponse(_unsubscribe_page(
        "You are unsubscribed",
        "Your address has been added to our suppression list and will not receive future marketing emails.",
    ))


@app.post("/campaigns")
def create_campaign(payload: CampaignPayload):
    return {"campaign": campaign_store.create_campaign(payload.name, payload.description)}


@app.get("/campaigns")
def get_campaigns():
    return {"campaigns": campaign_store.list_campaigns()}


@app.delete("/campaigns/{campaign_id}")
def delete_campaign(campaign_id: str):
    if campaign_id == DEFAULT_CAMPAIGN_ID:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The General Campaign cannot be deleted.",
        )
    campaign = _get_campaign_or_404(campaign_id)
    deleted_automation = sequence_store.delete_campaign_sequences(campaign_id)
    campaign_store.delete_campaign(campaign_id)
    return {
        "message": f"{campaign.get('name', 'Campaign')} deleted successfully.",
        "campaign_id": campaign_id,
        "deleted": deleted_automation,
    }


@app.get("/campaigns/{campaign_id}/summary")
def get_campaign_summary(campaign_id: str):
    campaign = _get_campaign_or_404(campaign_id)
    delivery_summary = sequence_store.get_delivery_summary(campaign_id)
    return {
        "campaign": campaign,
        "contact_count": len(campaign_store.get_contacts(campaign_id)),
        "message_count": len(campaign_store.get_messages(campaign_id)),
        **delivery_summary,
    }


@app.post("/extract-emails", response_model=dict)
def extract_emails_from_csv(file: UploadFile, campaign_id: str = DEFAULT_CAMPAIGN_ID):
    try:
        _get_campaign_or_404(campaign_id)
        extracted_records = file_extractor.file_extractor.extract_from_bytes(file.file.read(), file.content_type)
        campaign_store.set_contacts(campaign_id, extracted_records)
        return {"message": "Emails extracted successfully", "total": len(extracted_records)}
    except HTTPException:
        raise
    except Exception as e:
        print("ERROR", str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Error!! Check the file format and try again."
        )


@app.post("/message", description="This route is used to add messages that can be used later")
def save_message(payload: EmailMessagePayload, campaign_id: str = DEFAULT_CAMPAIGN_ID):
    """
    Docstring for save_message

    :param payload: Description
    :type payload: EmailMessageListPayload
    :Returns a dictionary of {"message":""}
    """
    payload = payload.model_dump()

    try:
        _get_campaign_or_404(campaign_id)
        messages_from_redis = campaign_store.get_messages(campaign_id)
        payload['message_id'] = str(uuid.uuid4())
        messages_from_redis.append(payload)
        campaign_store.set_messages(campaign_id, messages_from_redis)
        return {"message": "Email added successfully", "email_message": payload}
    except HTTPException:
        raise
    except Exception as e:
        print("ERROR", str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Error occured when trying to add messages")


@app.get("/messages", response_model=EmailMessageListSerializer)
def get_messages(campaign_id: str = DEFAULT_CAMPAIGN_ID):
    try:
        _get_campaign_or_404(campaign_id)
        messages = campaign_store.get_messages(campaign_id)
        return EmailMessageListSerializer(messages=messages)
    except HTTPException:
        raise
    except Exception as e:
        print("ERROR", str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Error fetching messages")


@app.put("/messages/{message_id}", response_model=EmailMessageSample)
def update_message(
    message_id: str,
    payload: EmailMessagePayload,
    campaign_id: str = DEFAULT_CAMPAIGN_ID,
):
    if not payload.subject.strip() or not payload.body.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Subject and message body are required.",
        )

    _get_campaign_or_404(campaign_id)
    messages = campaign_store.get_messages(campaign_id)
    for index, message in enumerate(messages):
        if message.get("message_id") == message_id:
            updated_message = {
                "message_id": message_id,
                "subject": payload.subject.strip(),
                "body": payload.body.strip(),
            }
            messages[index] = updated_message
            campaign_store.set_messages(campaign_id, messages)
            return EmailMessageSample(**updated_message)

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found.")


@app.delete("/messages/{message_id}")
def remove_message(message_id: str, campaign_id: str = DEFAULT_CAMPAIGN_ID):
    try:
        _get_campaign_or_404(campaign_id)
        messages = campaign_store.get_messages(campaign_id)
        for message in messages:
            if message['message_id'] == message_id:
                messages.remove(message)

        campaign_store.set_messages(campaign_id, messages)

        return {"message": "Message deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        print("ERROR", str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Error occured deleting message")


@app.get("/get-emails", response_model=ExtractedFileSerializer)
def fetch_emails(page: int = 1, page_size: int = 70, campaign_id: str = DEFAULT_CAMPAIGN_ID):
    try:
        _get_campaign_or_404(campaign_id)
        extracted_data = campaign_store.get_contacts(campaign_id)
        total = len(extracted_data)

        start = (page - 1) * page_size
        end = start + page_size

        paginated_data = extracted_data[start:end]

        return ExtractedFileSerializer(
            filename="from_redis",
            extracted_records=paginated_data,
            page=page,
            page_size=page_size,
            total=total,
            total_pages=ceil(total / page_size),
        )

    except HTTPException:
        raise
    except Exception as e:
        print("ERROR", str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Error!!.")


@app.get("/template-variables", response_model=TemplateVariablesResponse)
def get_template_variables(campaign_id: str = DEFAULT_CAMPAIGN_ID):
    _get_campaign_or_404(campaign_id)
    recipients = campaign_store.get_contacts(campaign_id)
    return TemplateVariablesResponse(variables=discover_template_variables(recipients))


@app.post("/sequences/start", response_model=StartSequenceResponse)
def start_sequence(payload: StartSequencePayload):
    _get_campaign_or_404(payload.campaign_id)
    recipients = (
        payload.email_list
        if payload.email_list is not None
        else campaign_store.get_contacts(payload.campaign_id)
    )
    valid_recipients = []
    seen_emails = set()
    for recipient in recipients:
        email = build_recipient_context(recipient).get("email", "").strip().lower()
        if email and email not in seen_emails and not suppression_store.is_suppressed(email):
            seen_emails.add(email)
            valid_recipients.append(recipient)

    if not valid_recipients:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No eligible recipients were supplied. Addresses may be invalid or suppressed.",
        )

    senders = list(dict.fromkeys(sender.strip() for sender in payload.senders if sender.strip()))
    if not senders:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Choose at least one sender.")

    now = time.time()
    sequence_id = str(uuid.uuid4())
    sequence = {
        "sequence_id": sequence_id,
        "campaign_id": payload.campaign_id,
        "name": payload.name or payload.steps[0].subject,
        "steps": [step.model_dump() for step in payload.steps],
        "status": "preparing",
        "created_at": now,
        "enrolled": len(valid_recipients),
        "enrollment_ids": [],
    }
    sequence_store.save_sequence(sequence)

    for index, recipient in enumerate(valid_recipients):
        enrollment_id = str(uuid.uuid4())
        enrollment = {
            "enrollment_id": enrollment_id,
            "sequence_id": sequence_id,
            "recipient": recipient,
            "sender": senders[index % len(senders)],
            "next_step_index": 0,
            "next_run_at": now,
            "status": "scheduled",
            "attempts": 0,
            "sent_message_ids": [],
            "history": [],
            "created_at": now,
        }
        sequence["enrollment_ids"].append(enrollment_id)
        sequence_store.schedule_enrollment(enrollment, now)

    sequence["status"] = "active"
    sequence_store.save_sequence(sequence)
    dispatch_due_sequence_emails.delay()
    return StartSequenceResponse(
        sequence_id=sequence_id,
        enrolled=len(valid_recipients),
        message=f"Sequence started for {len(valid_recipients)} recipients.",
    )


@app.get("/sequences")
def get_sequences(campaign_id: str = None):
    return {"sequences": sequence_store.list_sequences(campaign_id)}


@app.get("/sequences/{sequence_id}")
def get_sequence(sequence_id: str):
    sequence = sequence_store.get_sequence(sequence_id)
    if not sequence:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sequence not found.")

    status_counts = {}
    for enrollment_id in sequence.get("enrollment_ids", []):
        enrollment = sequence_store.get_enrollment(enrollment_id)
        if enrollment:
            enrollment_status = enrollment.get("status", "unknown")
            status_counts[enrollment_status] = status_counts.get(enrollment_status, 0) + 1
    return {"sequence": sequence, "status_counts": status_counts}


def _set_sequence_status(sequence_id: str, next_status: str):
    sequence = sequence_store.get_sequence(sequence_id)
    if not sequence:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sequence not found.")
    sequence["status"] = next_status
    sequence_store.save_sequence(sequence)
    return sequence


@app.post("/sequences/{sequence_id}/pause")
def pause_sequence(sequence_id: str):
    return {"sequence": _set_sequence_status(sequence_id, "paused")}


@app.post("/sequences/{sequence_id}/resume")
def resume_sequence(sequence_id: str):
    sequence = _set_sequence_status(sequence_id, "active")
    dispatch_due_sequence_emails.delay()
    return {"sequence": sequence}


@app.post("/sequences/{sequence_id}/cancel")
def cancel_sequence(sequence_id: str):
    sequence = _set_sequence_status(sequence_id, "cancelled")
    for enrollment_id in sequence.get("enrollment_ids", []):
        sequence_store.remove_from_schedule(enrollment_id)
        enrollment = sequence_store.get_enrollment(enrollment_id)
        if enrollment and enrollment.get("status") not in {"completed", "failed"}:
            enrollment["status"] = "cancelled"
            sequence_store.save_enrollment(enrollment)
    return {"sequence": sequence}


@app.post("/send-bulk-emails", response_model=BulkEmailResponse)
def send_bulk_messages(payload: MailBodySerializer):
    try:
        _get_campaign_or_404(payload.campaign_id)
        extracted_data = campaign_store.get_contacts(payload.campaign_id)
        send_bulk_emails.delay(
            email_list=extracted_data,
            messages=payload.bodies,
            subjects=payload.subjects,
            email_senders=payload.senders,
            campaign_id=payload.campaign_id,
        )
        return BulkEmailResponse(message=f"Bulk email sending initiated to {len(extracted_data)} recipients.")
    except Exception as e:
        print("ERROR", str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Error!! Check the file format and try again."
        )


@app.post("/send-selected-emails", response_model=BulkEmailResponse)
def send_selected_bulk_messages(payload: MailBodySerializer):
    try:
        if not payload.email_list or len(payload.email_list) == 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email list cannot be empty.")

        payload = payload.model_dump()

        send_bulk_emails.delay(
            email_list=payload["email_list"],
            messages=payload["bodies"],
            subjects=payload["subjects"],
            email_senders=payload['senders'],
            campaign_id=payload["campaign_id"],
        )
        return BulkEmailResponse(message=f"Bulk email sending initiated to {len(payload['email_list'])} recipients.")
    except Exception as e:
        print(e, "ERROR")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Error!!Occurred try again")


@app.get("/email-senders", response_model=SendersSerializer)
def get_email_senders():
    try:
        senders = redis_service.get_data(SENDERS)
        # Seed Redis with the default senders on first read
        if not senders:
            senders = [item.email for item in EMAIL_SENDERS]
            redis_service.set_data(SENDERS, senders)
        return SendersSerializer(senders=senders)
    except Exception as e:
        print("ERROR", str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Error fetching email_senders")


@app.post("/email-senders", response_model=SendersSerializer)
def set_email_senders(payload: SendersPayload):
    """Replace the list of sender addresses. Persisted in Redis, so changing
    senders no longer requires a code change or redeploy."""
    try:
        # De-duplicate while preserving order and dropping blanks
        senders = list(dict.fromkeys(s.strip() for s in payload.senders if s and s.strip()))
        redis_service.set_data(SENDERS, senders)
        return SendersSerializer(senders=senders)
    except Exception as e:
        print("ERROR", str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Error saving email_senders")


@app.delete("/email-senders/{sender}", response_model=SendersSerializer)
def remove_email_sender(sender: str):
    try:
        senders = redis_service.get_data(SENDERS) or [item.email for item in EMAIL_SENDERS]
        senders = [s for s in senders if s != sender]
        redis_service.set_data(SENDERS, senders)
        return SendersSerializer(senders=senders)
    except Exception as e:
        print("ERROR", str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Error deleting email_sender")
