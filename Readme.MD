# Email Batch Processor

A robust bulk email sending system with intelligent rotation of senders, content, and subjects to optimize deliverability and avoid spam filters.

## Features

- **Smart Content Rotation**: Automatically rotates through 4 message and subject variants at predetermined intervals
- **Multi-Sender Support**: Distributes emails across multiple sender addresses
- **Batch Processing**: Handles large email lists in configurable batches
- **Built-in Delays**: Prevents rate limiting with customizable delays between emails and batches
- **Error Tracking**: Comprehensive logging of successful and failed sends
- **Asynchronous Processing**: Powered by Celery for background task execution

## Configuration

### Default Settings

```python
batch_size = 25             # Emails per batch
batch_delay_seconds = 900    # 15 minutes between batches
email_delay_seconds = 60      # 1 minute between emails
rotation_delay_seconds = 180  # 3 minutes when rotating content
rotation_intervals = [49, 99, 149, 199]  # Content rotation triggers
```

### Email Senders

Configure sender addresses in `EMAIL_SENDERS`:

```python
EMAIL_SENDERS = [
    EmailConfig(email="marketing@example.com"),
    EmailConfig(email="lucia@example.com"),
    EmailConfig(email="richard@example.com"),
    EmailConfig(email="mariam@example.com"),
]
```

## Usage

### Basic Example

```python
from tasks import send_bulk_emails

# Prepare your data
email_list = [
    {'email': 'user1@example.com'},
    {'email': 'user2@example.com'},
    # ... more emails
]

messages = [
    "Hello! This is our first message variant.",
    "Hi there! This is our second message variant.",
    "Greetings! This is our third message variant.",
    "Hey! This is our fourth message variant."
]

subjects = [
    "Special Offer - Variant 1",
    "Special Offer - Variant 2",
    "Special Offer - Variant 3",
    "Special Offer - Variant 4"
]

email_senders = [
    "marketing@example.com",
    "sales@example.com"
]

# Send emails asynchronously
task = send_bulk_emails.delay(email_list, messages, subjects, email_senders)

# Check task status
print(f"Task ID: {task.id}")
```

### Checking Task Status

```python
from tasks import get_sending_stats

# Get statistics for a task
stats = get_sending_stats(task_id)
print(stats)
```

## How It Works

### Rotation Logic

The system rotates content at specific intervals to maintain deliverability:

- **Emails 0-48**: Uses variant 1
- **Emails 50-98**: Uses variant 2  
- **Emails 100-148**: Uses variant 3
- **Emails 150-199**: Uses variant 4

At each rotation point, the system pauses for 3 minutes before continuing.

### Sender Rotation

Senders rotate cyclically with each email:
1. marketing@example.com
2. lucia@example.com
3. richard@example.com
4. mariam@example.com
5. Back to marketing@example.com...

### Processing Flow

1. Email list is split into batches of 200
2. For each email in a batch:
   - Select current sender (rotates with each email)
   - Select current message/subject variant
   - Convert message to HTML format
   - Send via ZeptoMail
   - Wait 60 seconds
   - Check if content rotation is needed
3. Wait 1 hour between batches
4. Return comprehensive statistics

## Response Format

```python
{
    'total_emails': 500,
    'batches_processed': 3,
    'successful': 487,
    'failed': 13,
    'errors': [
        {'email': {'email': 'invalid@example.com'}, 'error': 'Invalid email address'},
        # ... more errors
    ]
}
```

## Requirements

- Celery
- ZeptoMail client
- Email template editor
- Redis/RabbitMQ (for Celery broker)

## Setup

1. Install dependencies:
   ```bash
   pip install celery
   ```

2. Configure broker URL in `config.py`:
   ```python
   BROKER_URL = 'redis://localhost:6379/0'
   ```

3. Start Celery worker:
   ```bash
   celery -A tasks worker --loglevel=info
   ```

4. Submit email tasks through your application

## Best Practices

- **Content Variants**: Provide 4 distinct message and subject variants for optimal rotation
- **Email Lists**: Ensure email addresses are valid and properly formatted
- **Monitoring**: Check task statistics regularly to identify delivery issues
- **Rate Limits**: Adjust delays if you encounter rate limiting from your email provider
- **Templates**: Use the `email_test.html` template for consistent formatting

## Notes

- The system uses ZeptoMail as the email provider (previously AWS SES)
- Line breaks in messages are automatically converted to HTML `<br>` tags
- All emails are sent as HTML using the configured template
- Failed sends are logged with detailed error messages for troubleshooting