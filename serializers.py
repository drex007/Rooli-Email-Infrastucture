from typing import Any, List, Optional
from pydantic import BaseModel


class ExtractedFileSerializer(BaseModel):
    filename: str
    extracted_records: List[Any]
    page: int
    page_size: int
    total: int
    total_pages: int


class BulkEmailResponse(BaseModel):
    message: str


class EmailAddress(BaseModel):
    Emails: str


class MailBodySerializer(BaseModel):
    subjects: List[str]
    bodies: List[str]
    email_list: Optional[List[EmailAddress]] = None
    senders: Optional[List[str]] =  None #List of emails to used to send 


class EmailMessagePayload(BaseModel):
    subject: str
    body: str


class EmailMessageSample(BaseModel):
    message_id: Optional[str] = None
    subject: str
    body: str


class EmailMessageListPayload(BaseModel):
    messages: list[EmailMessagePayload] = None


class EmailMessageListSerializer(BaseModel):
    messages: Optional[List[EmailMessageSample]] = []
