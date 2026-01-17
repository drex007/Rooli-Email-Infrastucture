import boto3 as boto3

from adapters.email_adapters.email_adapter import EmailAdapter
from botocore.exceptions import ClientError
from jinja2 import Environment, FileSystemLoader



class AmazonEmailAdapter(EmailAdapter):
    def _init_(self, client: boto3.client):
        self.client = client

    async def send_html_email(self, from_: str, to: str, subject: str, html: str):
        try:
            response = self.client.send_email(
                Destination={
                    'ToAddresses': [
                        to,
                    ],
                },
                Message={
                    'Body': {
                        'Html': {
                            'Charset': "UTF-8",
                            'Data': html,
                        }
                    },
                    'Subject': {
                        'Charset': "UTF-8",
                        'Data': subject,
                    },
                },
                Source=from_,
            )
        except ClientError as e:
            print(e.response['Error']['Message'])

        else:
            print("Email sent! Message ID:"),
            print(response['MessageId'])


class EmailTemplateEditor:
    def _init_(self, template_dir: str = "./templates"):
        self.env = Environment(loader=FileSystemLoader(template_dir))

    def edit_template_and_return_body(self, template_name: str, context: dict) -> str:
        template = self.env.get_template(template_name)
        return template.render(context)