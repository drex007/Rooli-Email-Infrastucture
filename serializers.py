from typing import List, Optional
from pydantic import BaseModel

class ExtractedFileSerializer(BaseModel):
    filename: str
    extracted_records: List[dict]


class BulkEmailResponse(BaseModel):
    message: str


class MailBodySerializer(BaseModel):
    subjects: List[str]
    bodies: List[str]
    email_list: Optional[List[dict]] = [] # {"Emails":  ""}
