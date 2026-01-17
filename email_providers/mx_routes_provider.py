import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from celery import Celery
import os


MXROUTE_SMTP_HOST = "mail.mxroute.com"  # or your specific server
MXROUTE_SMTP_PORT = 587  # Use 587 for TLS or 465 for SSL
MXROUTE_EMAIL = "your-email@yourdomain.com"  # Your MXRoute email
MXROUTE_PASSWORD = "your-password"  # Your email password
MXROUTE_USE_TLS = True



class MXRouteEmailSender:
    """Email sender using MXRoute SMTP"""
    
    def __init__(self, smtp_host=MXROUTE_SMTP_HOST, smtp_port=MXROUTE_SMTP_PORT,
                 email=MXROUTE_EMAIL, password=MXROUTE_PASSWORD, use_tls=MXROUTE_USE_TLS):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.email = email
        self.password = password
        self.use_tls = use_tls
    
    def send_email(self, to_email, subject, body, html=False, from_email=None, from_email_password=None):
  
        try:
            msg = MIMEMultipart()
            msg['From'] = self.email
            msg['To'] = to_email if isinstance(to_email, str) else ', '.join(to_email)
            msg['Subject'] = subject
            
            if html:
                msg.attach(MIMEText(body, 'html'))
            else:
                msg.attach(MIMEText(body, 'plain'))
    
       
            if self.use_tls:
              
                server = smtplib.SMTP(self.smtp_host, self.smtp_port)
                server.starttls()
            else:
                server = smtplib.SMTP_SSL(self.smtp_host, self.smtp_port)
            
            server.login(from_email, from_email_password)
        
            recipients = [to_email] if isinstance(to_email, str) else to_email
            server.send_message(msg)
            server.quit()
            
            return {
                'status': 'success',
                'message': f'Email sent successfully to {msg["To"]}'
            }
            
        except Exception as e:
            print(f"Error sending email: {e}")
            return {
                'status': 'error',
                'message': str(e)
            }
    