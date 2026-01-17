# main.py
from celery_task import send_bulk_emails
from config import REDIS_EMAIL_KEY_PREFIX
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, UploadFile, File
import file_extractor
from redis_service.redis_service import RedisService
from serializers import BulkEmailResponse, ExtractedFileSerializer, MailBodySerializer


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


@app.post("/extract-emails", response_model=ExtractedFileSerializer)
def extract_emails_from_csv(file: UploadFile):
    try:
        extracted_records = file_extractor.file_extractor.extract_from_bytes(file.file.read(), file.content_type)
        redis_service.set_data(REDIS_EMAIL_KEY_PREFIX, extracted_records)
        return ExtractedFileSerializer(filename=file.filename, extracted_records=extracted_records)
    except Exception as e:
        print("ERROR", str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Error!! Check the file format and try again."
        )


@app.get("/get-emails", response_model=ExtractedFileSerializer)
def fetch_emails():
    try:
        extracted_data = redis_service.get_data(REDIS_EMAIL_KEY_PREFIX)
        return ExtractedFileSerializer(filename="from_redis", extracted_records=extracted_data)
    except Exception as e:
        print("ERROR", str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Error!!.")


@app.post("/send-bulk-emails", response_model=BulkEmailResponse)
def send_bulk_messages(payload: MailBodySerializer):
    try:
        extracted_data = redis_service.get_data(REDIS_EMAIL_KEY_PREFIX)  # This returns the list of emails
        send_bulk_emails.delay(email_list=extracted_data, message=payload.bodies, subject=payload.subjects)
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
        send_bulk_emails.delay(email_list=payload.email_list, message=payload.bodies, subject=payload.subjects)
        return BulkEmailResponse(message=f"Bulk email sending initiated to {len(payload.email_list)} recipients.")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Error!! Check the file format and try again."
        )
