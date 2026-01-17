# This where binding for the adapters take place
import boto3

from config import AWS_ACCESS_KEY_ID, AWS_REGION, AWS_SECRET_KEY
from email_providers.aws_ses_provider import AmazonEmailAdapter, EmailTemplateEditor


def get_ses_email_client():
    ses_client = boto3.client(
        'ses',
        region_name=AWS_REGION,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_KEY,
    )
    return ses_client


email_client = AmazonEmailAdapter(client=get_ses_email_client())
template_editor = EmailTemplateEditor()
