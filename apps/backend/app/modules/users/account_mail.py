"""Account mail transport using the existing SMTP configuration."""
import smtplib
import ssl
from email.message import EmailMessage
from fastapi import HTTPException
from app.core.config import get_settings


def send_account_email(email, subject, text):
    settings = get_settings()
    if not settings.smtp_username or not settings.smtp_password:
        raise HTTPException(503, "El envío de correos no está configurado")
    message = EmailMessage()
    message["From"] = settings.smtp_from or settings.smtp_username
    message["To"] = email
    message["Subject"] = subject
    message.set_content(text)
    try:
        context = ssl.create_default_context()
        transport = smtplib.SMTP_SSL if settings.smtp_port == 465 else smtplib.SMTP
        with transport(settings.smtp_host, settings.smtp_port, timeout=15,
                       **({"context": context} if settings.smtp_port == 465 else {})) as smtp:
            if settings.smtp_port != 465:
                smtp.starttls(context=context)
            smtp.login(settings.smtp_username, settings.smtp_password.replace(" ", ""))
            if smtp.send_message(message):
                raise smtplib.SMTPException("Recipient refused")
    except (OSError, smtplib.SMTPException):
        raise HTTPException(502, "No se pudo enviar el correo; vuelve a intentarlo") from None
