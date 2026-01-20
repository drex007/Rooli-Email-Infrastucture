from typing import List, Optional
from pydantic import BaseModel


class ExtractedFileSerializer(BaseModel):
    filename: str
    extracted_records: List[dict]


class BulkEmailResponse(BaseModel):
    message: str


class EmailAddress(BaseModel):
    Emails: str


class MailBodySerializer(BaseModel):
    subjects: List[str]
    bodies: List[str]
    email_list: Optional[List[EmailAddress]] = None

class EmailMessagePayload(BaseModel):
    subject: str
    body: str

class EmailMessageSample(BaseModel):
    message_id: Optional[str] = None
    subject: str
    body: str



class EmailMessageListPayload(BaseModel):
    messages: Optional[List[EmailMessagePayload]] = None


class EmailMessageListSerializer(BaseModel):
    messages: Optional[List[EmailMessageSample]] = []
