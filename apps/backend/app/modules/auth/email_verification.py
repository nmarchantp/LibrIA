"""Expiring, rate-limited email codes delivered over authenticated Gmail SMTP."""
import hashlib
import hmac
import secrets
import smtplib
import ssl
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

from fastapi import HTTPException
from sqlalchemy import select

from app.core.config import get_settings
from app.modules.auth.models import AuthAccount


def send_verification_email(email: str, code: str):
    settings = get_settings()
    if not settings.smtp_username or not settings.smtp_password:
        raise HTTPException(503, "El envío de correos aún no está configurado. Contacta al administrador.")
    message = EmailMessage()
    message["Subject"] = "Verifica tu correo para vincular Google a LibrIA"
    message["From"] = settings.smtp_from or settings.smtp_username
    message["To"] = email
    message.set_content(f"Tu código de verificación de LibrIA es: {code}\n\n"
                        "Vence en 5 minutos. Escríbelo en Mi cuenta para continuar con la vinculación de Google.\n"
                        "Si no solicitaste este correo, puedes ignorarlo.")
    try:
        context = ssl.create_default_context()
        smtp_class = smtplib.SMTP_SSL if settings.smtp_port == 465 else smtplib.SMTP
        kwargs = {"context": context} if settings.smtp_port == 465 else {}
        with smtp_class(settings.smtp_host, settings.smtp_port, timeout=15, **kwargs) as smtp:
            if settings.smtp_port != 465:
                smtp.starttls(context=context)
            smtp.login(settings.smtp_username, settings.smtp_password.replace(" ", ""))
            if smtp.send_message(message):
                raise smtplib.SMTPException("Recipient refused")
    except (OSError, smtplib.SMTPException):
        raise HTTPException(502, "No se pudo enviar el código. Inténtalo nuevamente más tarde.") from None


def code_hash(user_id, email, code):
    payload = f"{user_id}:{email}:{code}".encode()
    return hmac.new(get_settings().jwt_secret.encode(), payload, hashlib.sha256).hexdigest()


def locked_account(db, user_id):
    return db.scalar(select(AuthAccount).where(AuthAccount.user_id == user_id)
                     .with_for_update().execution_options(populate_existing=True))


def request_code(db, user_id, email):
    account = locked_account(db, user_id)
    now = datetime.now(timezone.utc)
    if account.google_subject and account.google_email_verified_at:
        raise HTTPException(409, "Ya tienes una cuenta de Google vinculada.")
    if account.google_email_code_sent_at and now - account.google_email_code_sent_at < timedelta(seconds=60):
        raise HTTPException(429, "Espera un minuto antes de solicitar otro código.")
    code = f"{secrets.randbelow(1000000):06d}"
    account.google_email = email.lower()
    account.google_email_verified_at = None
    account.google_email_code_hash = code_hash(user_id, account.google_email, code)
    account.google_email_code_expires_at = now + timedelta(minutes=5)
    account.google_email_code_sent_at = now
    account.google_email_code_attempts = 0
    try:
        send_verification_email(account.google_email, code)
        db.commit()
        return {"status": "sent", "email": account.google_email,
                "expires_at": account.google_email_code_expires_at,
                "resend_at": account.google_email_code_sent_at + timedelta(seconds=60)}
    except Exception:
        db.rollback()
        raise


def confirm_code(db, user_id, code):
    account = locked_account(db, user_id)
    now = datetime.now(timezone.utc)
    if (not account.google_email_code_hash or not account.google_email_code_expires_at
            or now >= account.google_email_code_expires_at or account.google_email_code_attempts >= 5):
        raise HTTPException(400, "El código venció o ya no es válido. Solicita uno nuevo.")
    account.google_email_code_attempts += 1
    if not hmac.compare_digest(account.google_email_code_hash, code_hash(user_id, account.google_email, code)):
        db.commit()
        raise HTTPException(400, "Código incorrecto. Revisa el correo recibido.")
    account.google_email_verified_at = now
    account.google_email_code_hash = None
    account.google_email_code_expires_at = None
    db.commit()
