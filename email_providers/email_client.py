# This where binding for the adapters take place
import boto3

from config import CONFIG
from providers.aws_ses_provider import AmazonEmailAdapter, EmailTemplateEditor


def get_email_client():
    ses_client = boto3.client(
        'ses',
        region_name=CONFIG.auth.aws_region_name,
        aws_access_key_id=CONFIG.auth.aws_access_key_id,
        aws_secret_access_key=CONFIG.auth.aws_secret_access_key,
    )
    return ses_client


#   redirection_url = f"{config.client.auth_page_url}/auth/new-password?token={token}"

#     body = template_editor.edit_template_and_return_body(
#         "stripe_password_reset.html", {"subject": subject, "redirect_url": f"{redirection_url}"}
#     )

#     return await email_client.send_html_email(config.client.sender_email_address, email, subject, body)


email_client = AmazonEmailAdapter(client=get_email_client())
template_editor = EmailTemplateEditor()
