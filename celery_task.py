from typing import List, Dict, Optional
from dataclasses import dataclass
from celery import Celery
import time
from enum import Enum

from config import BROKER_URL
from email_providers.aws_ses_provider import EmailTemplateEditor
from email_providers.email_client import email_client
from email_providers.zepto_mail_client import ZeptoMailClient


@dataclass
class EmailConfig:
    """Configuration for email sending"""

    email: str


class VariantValue (str, Enum):
    first = 49
    second = 99
    third = 149
    fourth = 199



@dataclass
class BatchConfig:
    """Configuration for batch processing"""

    batch_size: int = 25 #200
    batch_delay_seconds: int = 900 #15 minutes for the next batch
    email_delay_seconds: int = 60
    rotation_delay_seconds: int = 180
    rotation_intervals: List[int] = None

    def __post_init__(self):
        if self.rotation_intervals is None:
            self.rotation_intervals = [VariantValue.first, VariantValue.second, VariantValue.third, VariantValue.fourth]




class RotationType(Enum):
    """Types of content rotation"""

    FIRST_VARIANT = 0
    SECOND_VARIANT = 1
    THIRD_VARIANT = 2
    FOURTH_VARIANT = 3


app = Celery('tasks', broker=BROKER_URL, backend=BROKER_URL)

# Configure email senders
EMAIL_SENDERS = [
    EmailConfig(email="marketing@roolimarketing.xyz"),
    EmailConfig(email="lucia@roolimarketing.xyz"),
    EmailConfig(email="richard@roolimarketing.xyz"),
    EmailConfig(email="mariam@roolimarketing.xyz"),
      
]


# Configuration
config = BatchConfig()


class EmailBatchProcessor:
    """Handles batch processing of emails with rotation logic"""

    def __init__(
        self,
        senders: List[EmailConfig],
        config: BatchConfig,
        template_editor: EmailTemplateEditor = EmailTemplateEditor(),
        zepto_mail_client: ZeptoMailClient = ZeptoMailClient()
    ):
        self.senders = senders
        self.config = config
        self.sender_index = 0
        self.message_index = 0
        self.subject_index = 0
        self._template_editor = template_editor
        self._zepto_mail_client = zepto_mail_client


    def get_rotation_type(self, count: int) -> Optional[RotationType]:
        """Determine if rotation is needed and which type"""
        if count not in self.config.rotation_intervals:
            return None

        if count < VariantValue.first:
            return RotationType.FIRST_VARIANT
        elif count > VariantValue.first and count < VariantValue.second:
            return RotationType.SECOND_VARIANT

        elif count > VariantValue.third and count < VariantValue.fourth:
            return RotationType.THIRD_VARIANT
        else:
            return RotationType.FOURTH_VARIANT

    def rotate_content(self, rotation_type: RotationType, message_count: int, subject_count: int):
        """Rotate message and subject indices based on rotation type"""
        mapping = {
            RotationType.FIRST_VARIANT: 0,
            RotationType.SECOND_VARIANT: 1,
            RotationType.THIRD_VARIANT: 2,
            RotationType.FOURTH_VARIANT: 3,
        }

        idx = mapping.get(rotation_type, 0)

        self.message_index = min(idx, message_count - 1)
        self.subject_index = min(idx, subject_count - 1)

    def rotate_sender(self):
        """Move to next sender in rotation"""
        self.sender_index = (self.sender_index + 1) % len(self.senders)

    def get_current_sender(self) -> EmailConfig:
        """Get current sender configuration"""
        return self.senders[self.sender_index]

    def process_batch(self, emails: List[dict], messages: List[str], subjects: List[str]) -> Dict:
        """Process a batch of emails with rotation"""
        stats = {'successful': 0, 'failed': 0, 'errors': []}

        for count, email_data in enumerate(emails):
            try:
                # Get current configuration
                sender = self.get_current_sender()
                message = messages[self.message_index]
                subject = subjects[self.subject_index]
                message = message.replace("\n", "<br>")  # Added line breaks for emails
                body = self._template_editor.edit_template_and_return_body(
                    "email_test.html", {"subject": subject, "message": f"{message}"}
                )

                to_email = email_data.get('Emails', email_data.get('email'))
                # result = email_client.send_html_email(from_=sender.email, to=to_email, subject=subject, html=body)

                #Moved from AWS client to zeptoMail
                result = self._zepto_mail_client.send_email(from_address=sender.email, to_emails=[to_email], subject=subject, html_body=body)

                if result.get('status') == 'success':
                    stats['successful'] += 1
                else:
                    stats['failed'] += 1
                    stats['errors'].append({'email': email_data, 'error': result.get('message', 'Unknown error')})

                # Rotate sender for next email
                self.rotate_sender()
                # Check for content rotation
                rotation_type = self.get_rotation_type(count)
                if rotation_type:
                    self.rotate_content(rotation_type, len(messages), len(subjects))
                    time.sleep(self.config.rotation_delay_seconds)
                else:
                    time.sleep(self.config.email_delay_seconds)

            except Exception as e:
                stats['failed'] += 1
                stats['errors'].append({'email': email_data, 'error': str(e)})
                print(f"Error sending to {email_data}: {e}")

        return stats


def split_into_batches(items: List, batch_size: int) -> List[List]:
    """Split a list into batches of specified size"""
    return [items[i : i + batch_size] for i in range(0, len(items), batch_size)]


@app.task(bind=True, name='tasks.send_bulk_emails')
def send_bulk_emails(
    self, email_list: List[dict], messages: List[str], subjects: List[str], email_senders: List[str]
) -> Dict:
    """
    Send bulk emails with rotation of senders, messages, and subjects

    Args:
        email_list: List of email recipient dictionaries
        messages: List of message variants to rotate
        subjects: List of subject variants to rotate

    Returns:
        Dictionary with total statistics
    """
    if not email_list:
        return {'error': 'Empty email list'}

    if not messages or not subjects:
        return {'error': 'Messages and subjects cannot be empty'}

    # Split emails into batches
    batches = split_into_batches(email_list, config.batch_size)

    # Initialize processor
    processor = EmailBatchProcessor([EmailConfig(email=email) for email in email_senders], config)

    # Track overall statistics
    total_stats = {'total_emails': len(email_list), 'batches_processed': 0, 'successful': 0, 'failed': 0, 'errors': []}

    # Process each batch
    for batch_num, batch in enumerate(batches):
        print(f"Processing batch {batch_num + 1}/{len(batches)} " f"({len(batch)} emails)")

        batch_stats = processor.process_batch(batch, messages, subjects)

        # Update total statistics
        total_stats['batches_processed'] += 1
        total_stats['successful'] += batch_stats['successful']
        total_stats['failed'] += batch_stats['failed']
        total_stats['errors'].extend(batch_stats['errors'])

        # Wait between batches (except after last batch)
        if batch_num < len(batches) - 1:
            print(f"Waiting {config.batch_delay_seconds}s before next batch...")
            time.sleep(config.batch_delay_seconds)

    print(f"Completed: {total_stats['successful']} successful, " f"{total_stats['failed']} failed")

    return total_stats


# Optional: Add a task to get sending statistics
@app.task(name='tasks.get_sending_stats')
def get_sending_stats(task_id: str) -> Optional[Dict]:
    """Retrieve statistics for a bulk email task"""
    result = app.AsyncResult(task_id)

    if result.ready():
        return {'status': 'completed', 'result': result.result}
    else:
        return {'status': 'pending', 'state': result.state}
