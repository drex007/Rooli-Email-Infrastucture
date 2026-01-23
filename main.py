# main.py
from math import ceil
from celery_task import send_bulk_emails
from config import MESSAGES, REDIS_EMAIL_KEY_PREFIX
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, UploadFile, File
import file_extractor
from redis_service.redis_service import RedisService
from serializers import (
    BulkEmailResponse,
    EmailMessageListPayload,
    EmailMessageListSerializer,
    EmailMessagePayload,
    ExtractedFileSerializer,
    MailBodySerializer,
)
import uuid


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


@app.get("/")
async def root():
    return {"message": "Welcome to FastAPI", "docs": "/docs", "redoc": "/redoc"}


@app.post("/extract-emails", response_model=dict)
def extract_emails_from_csv(file: UploadFile):
    try:
        extracted_records = file_extractor.file_extractor.extract_from_bytes(file.file.read(), file.content_type)
        redis_service.set_data(REDIS_EMAIL_KEY_PREFIX, extracted_records)
        return {"message": "Emails extracted successfully"}
    except Exception as e:
        print("ERROR", str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Error!! Check the file format and try again."
        )


@app.post("/message", description="This route is used to add messages that can be used later")
def save_message(payload: EmailMessagePayload):
    """
    Docstring for save_message

    :param payload: Description
    :type payload: EmailMessageListPayload
    :Returns a dictionary of {"message":""}
    """
    payload = payload.model_dump()

    try:
        messages_from_redis = redis_service.get_data(MESSAGES) or []
        payload['message_id'] = str(uuid.uuid4())
        messages_from_redis.append(payload)
        redis_service.set_data(MESSAGES, messages_from_redis)
        return {"message": "Emails added successfully"}
    except Exception as e:
        print("ERROR", str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Error occured when trying to add messages")


@app.get("/messages", response_model=EmailMessageListSerializer)
def get_messages():
    try:
        messages = redis_service.get_data(MESSAGES) or []
        return EmailMessageListSerializer(messages=messages)
    except Exception as e:
        print("ERROR", str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Error fetching messages")


@app.delete("/messages/{message_id}")
def remove_message(message_id: str):
    try:
        messages = redis_service.get_data(MESSAGES)
        for message in messages:
            if message['message_id'] == message_id:
                messages.remove(message)

        redis_service.set_data(MESSAGES, messages)

        return {"message": "Message deleted successfully"}
    except Exception as e:
        print("ERROR", str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Error occured deleting message")


@app.get("/get-emails", response_model=ExtractedFileSerializer)
def fetch_emails(page: int = 1, page_size: int = 70):
    try:
        extracted_data = redis_service.get_data(REDIS_EMAIL_KEY_PREFIX)
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

    except Exception as e:
        print("ERROR", str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Error!!.")


@app.post("/send-bulk-emails", response_model=BulkEmailResponse)
def send_bulk_messages(payload: MailBodySerializer):
    try:
        extracted_data = redis_service.get_data(REDIS_EMAIL_KEY_PREFIX)  # This returns the list of emails
        send_bulk_emails.delay(email_list=extracted_data, messages=payload.bodies, subjects=payload.subjects)
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
        print(payload, "PAYLOAD")
        send_bulk_emails.delay(
            email_list=payload["email_list"], messages=payload["bodies"], subjects=payload["subjects"]
        )
        return BulkEmailResponse(message=f"Bulk email sending initiated to {len(payload['email_list'])} recipients.")
    except Exception as e:
        print(e, "ERROR")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Error!!Occurred try again")
