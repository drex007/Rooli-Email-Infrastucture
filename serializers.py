from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


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
    senders: Optional[List[str]] = None  # List of emails to used to send
    campaign_id: str = "default"


class EmailMessagePayload(BaseModel):
    subject: str
    body: str


class CampaignPayload(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=500)


class EmailMessageSample(BaseModel):
    message_id: Optional[str] = None
    subject: str
    body: str


class EmailMessageListPayload(BaseModel):
    messages: list[EmailMessagePayload] = None


class EmailMessageListSerializer(BaseModel):
    messages: Optional[List[EmailMessageSample]] = []


class SendersPayload(BaseModel):
    senders: List[str]


class SendersSerializer(BaseModel):
    senders: List[str] = []


class SequenceStepPayload(BaseModel):
    subject: str
    body: str
    delay_seconds: int = Field(default=0, ge=0)


class StartSequencePayload(BaseModel):
    name: Optional[str] = None
    campaign_id: str = "default"
    steps: List[SequenceStepPayload] = Field(min_length=1)
    email_list: Optional[List[Dict[str, Any]]] = None
    senders: List[str] = Field(min_length=1)

    @field_validator("steps")
    @classmethod
    def validate_steps(cls, steps: List[SequenceStepPayload]):
        for step in steps:
            if not step.subject.strip() or not step.body.strip():
                raise ValueError("Every sequence step needs a subject and body")
        steps[0].delay_seconds = 0
        return steps


class StartSequenceResponse(BaseModel):
    sequence_id: str
    message: str
    enrolled: int


class TemplateVariable(BaseModel):
    key: str
    label: str
    token: str


class TemplateVariablesResponse(BaseModel):
    variables: List[TemplateVariable]
