from email.message import EmailMessage
import smtplib
import ssl
import os
import re
from flask.cli import load_dotenv

load_dotenv()
smtp_host = os.getenv('SMTP_HOST')
smtp_port = int(os.getenv('SMTP_PORT'))
sender_email = os.getenv('SMTP_EMAIL')
sender_password = os.getenv('SMTP_PASSWORD')


def send_email(receiver_email, subject, html_body):
    try:
        msg = EmailMessage()
        msg["From"] = sender_email
        msg["To"] = receiver_email
        msg["Subject"] = subject

        text_fallback = re.sub("<[^<]+>", "", html_body)
        msg.set_content(text_fallback)
        msg.add_alternative(html_body, subtype="html")

        context = ssl.create_default_context()

        with smtplib.SMTP(smtp_host, 587) as server:
            server.starttls(context=context)
            server.login(sender_email, sender_password)
            server.send_message(msg)
        return True
    except Exception as e:
        print("SMTP email send error: ", e)
        return False