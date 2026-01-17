
# from typing import List
# from celery import Celery
# import time


# from config import BROKER_URL
# from providers.mx_routes_provider import MXRouteEmailSender

# app = Celery(
#     'tasks',
#     broker=BROKER_URL,      
#     backend=BROKER_URL      
# )

# email_senders_list =  [
#     {
#         "email": "your-email@yourdomain.com",
#         "password": "your-password"
#     }
# ]


# mx_provider = MXRouteEmailSender(

# )

# @app.task(bind=True)
# def send_bulk_emails(email_list: List[dict], message: List[str], subject: List[str]):
#     """
#     Send bulk emails with rotation of senders, messages, and subjects
#     """


#     total_emails = len(email_list)

#     if total_emails > 200:
#         email_list = email_list[:200]
#         send_email_func(email_list = email_list, message=message, subject=subject)

#     time.sleep(50000)
    
#     if total_emails > 200:
#         email_list = email_list[200:400] 
#         send_email_func(email_list = email_list, message=message, subject=subject)
    
#     if total_emails > 400:
#         time.sleep(50000)
#         email_list = email_list[400:600] 
#         send_email_func(email_list = email_list, message=message, subject=subject)

#     if total_emails > 600:
#         time.sleep(50000)
#         email_list = email_list[600:800] 
#         send_email_func(email_list = email_list, message=message, subject=subject)


#     if total_emails > 800:
#         time.sleep(50000)
#         email_list = email_list[800:1000] 
#         send_email_func(email_list = email_list, message=message, subject=subject)


    


# def send_email_func(email_list: List[dict], message: List[str], subject: List[str]):
#     count = 0
#     successful = 0
#     failed = 0
#     errors = []
    
#     email_list_length = len(email_senders_list)
#     email_senders_index = 0

#     message_length = len(message)
#     message_index = 0
#     subject_length = len(subject)
#     subject_index = 0
#     for idx, email in enumerate(email_list):
#         try:
#             # Get current sender
#             current_sender = email_senders_list[email_senders_index]
            
#             # Create new sender instance for this email
#             # Send email
#             result = mx_provider.send_email(
#                 to_email=email['Emails'], 
#                 subject=subject[subject_index], 
#                 body=message[message_index],
#                 from_email=current_sender['email'],
#                 from_email_password=current_sender['password']
#             )
            
#             if result['status'] == 'success':
#                 successful += 1
#             else:
#                 failed += 1
#                 errors.append({'email': email, 'error': result['message']})
            
    
#             # Wait 60 seconds between emails
#             time.sleep(60) 

#             # Rotate messages and subjects at intervals
#             if count in [14, 29, 44, 59]:  # Changed to 0-indexed (15th, 30th, etc.)
#                 if count == 29 or count == 59:  # Use second variant
#                     if message_length > 1:
#                         message_index = 1
#                     if subject_length > 1:
#                         subject_index = 1
#                 else:  # Use first variant
#                     message_index = 0
#                     subject_index = 0

#                 # Wait 3 minutes after rotation
#                 time.sleep(180)
            
#             count += 1
            
#             # Rotate email sender (fixed logic)
#             email_senders_index = (email_senders_index + 1) % email_list_length

#         except Exception as e:
#             failed += 1
#             errors.append({'email': email, 'error': str(e)})
#             print(f"Error sending to {email}: {e}")
#             continue


from typing import List, Dict, Optional
from dataclasses import dataclass
from celery import Celery
import time
from enum import Enum

from config import BROKER_URL
from providers.mx_routes_provider import MXRouteEmailSender


@dataclass
class EmailConfig:
    """Configuration for email sending"""
    email: str
    password: str


@dataclass
class BatchConfig:
    """Configuration for batch processing"""
    batch_size: int = 200
    batch_delay_seconds: int = 50000  # ~13.9 hours
    email_delay_seconds: int = 60
    rotation_delay_seconds: int = 180
    rotation_intervals: List[int] = None
    
    def __post_init__(self):
        if self.rotation_intervals is None:
            self.rotation_intervals = [14, 29, 44, 59]


class RotationType(Enum):
    """Types of content rotation"""
    FIRST_VARIANT = 0
    SECOND_VARIANT = 1


app = Celery(
    'tasks',
    broker=BROKER_URL,
    backend=BROKER_URL
)

# Configure email senders
EMAIL_SENDERS = [
    EmailConfig(
        email="your-email@yourdomain.com",
        password="your-password"
    )
]

# Initialize provider
mx_provider = MXRouteEmailSender()

# Configuration
config = BatchConfig()


class EmailBatchProcessor:
    """Handles batch processing of emails with rotation logic"""
    
    def __init__(self, senders: List[EmailConfig], config: BatchConfig):
        self.senders = senders
        self.config = config
        self.sender_index = 0
        self.message_index = 0
        self.subject_index = 0
        
    def get_rotation_type(self, count: int) -> Optional[RotationType]:
        """Determine if rotation is needed and which type"""
        if count not in self.config.rotation_intervals:
            return None
        
        if count in [29, 59]:
            return RotationType.SECOND_VARIANT
        return RotationType.FIRST_VARIANT
    
    def rotate_content(self, rotation_type: RotationType, 
                      message_count: int, subject_count: int):
        """Rotate message and subject indices based on rotation type"""
        if rotation_type == RotationType.SECOND_VARIANT:
            self.message_index = min(1, message_count - 1)
            self.subject_index = min(1, subject_count - 1)
        else:
            self.message_index = 0
            self.subject_index = 0
    
    def rotate_sender(self):
        """Move to next sender in rotation"""
        self.sender_index = (self.sender_index + 1) % len(self.senders)
    
    def get_current_sender(self) -> EmailConfig:
        """Get current sender configuration"""
        return self.senders[self.sender_index]
    
    def process_batch(self, emails: List[dict], messages: List[str], 
                     subjects: List[str]) -> Dict:
        """Process a batch of emails with rotation"""
        stats = {
            'successful': 0,
            'failed': 0,
            'errors': []
        }
        
        for count, email_data in enumerate(emails):
            try:
                # Get current configuration
                sender = self.get_current_sender()
                message = messages[self.message_index]
                subject = subjects[self.subject_index]
                
                # Send email
                result = mx_provider.send_email(
                    to_email=email_data.get('Emails', email_data.get('email')),
                    subject=subject,
                    body=message,
                    from_email=sender.email,
                    from_email_password=sender.password
                )
                
                # Track results
                if result.get('status') == 'success':
                    stats['successful'] += 1
                else:
                    stats['failed'] += 1
                    stats['errors'].append({
                        'email': email_data,
                        'error': result.get('message', 'Unknown error')
                    })
                
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
                stats['errors'].append({
                    'email': email_data,
                    'error': str(e)
                })
                print(f"Error sending to {email_data}: {e}")
        
        return stats


def split_into_batches(items: List, batch_size: int) -> List[List]:
    """Split a list into batches of specified size"""
    return [items[i:i + batch_size] 
            for i in range(0, len(items), batch_size)]


@app.task(bind=True, name='tasks.send_bulk_emails')
def send_bulk_emails(self, email_list: List[dict], messages: List[str], 
                     subjects: List[str]) -> Dict:
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
    processor = EmailBatchProcessor(EMAIL_SENDERS, config)
    
    # Track overall statistics
    total_stats = {
        'total_emails': len(email_list),
        'batches_processed': 0,
        'successful': 0,
        'failed': 0,
        'errors': []
    }
    
    # Process each batch
    for batch_num, batch in enumerate(batches):
        print(f"Processing batch {batch_num + 1}/{len(batches)} "
              f"({len(batch)} emails)")
        
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
    
    print(f"Completed: {total_stats['successful']} successful, "
          f"{total_stats['failed']} failed")
    
    return total_stats


# Optional: Add a task to get sending statistics
@app.task(name='tasks.get_sending_stats')
def get_sending_stats(task_id: str) -> Optional[Dict]:
    """Retrieve statistics for a bulk email task"""
    result = app.AsyncResult(task_id)
    
    if result.ready():
        return {
            'status': 'completed',
            'result': result.result
        }
    else:
        return {
            'status': 'pending',
            'state': result.state
        }