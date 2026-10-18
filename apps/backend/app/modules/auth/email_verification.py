"""Expiring, rate-limited email codes delivered over authenticated Gmail SMTP."""
import hashlib
import hmac
import secrets
import smtplib
import ssl
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from html import escape
from pathlib import Path

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
    message.add_alternative(f"""<!doctype html>
<html lang="es">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"></head>
<body style="margin:0;padding:0;background-color:#f5f3f8;color:#302b47;font-family:Arial,Helvetica,sans-serif;">
  <div style="display:none;max-height:0;overflow:hidden;mso-hide:all;">Confirma tu correo para vincular Google a LibrIA. Tu código vence en 5 minutos.</div>
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color:#f5f3f8;">
    <tr><td align="center" style="padding:32px 16px;">
      <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:560px;">
        <tr><td align="center" style="padding:20px 16px;background-color:#ffffff;border-radius:16px;">
          <img src="cid:libriaverse-logo" alt="LibrIAverse — Tu universo literario" width="360" style="display:block;width:100%;max-width:360px;height:auto;border:0;">
        </td></tr>
        <tr><td height="24" style="height:24px;font-size:0;line-height:0;">&nbsp;</td></tr>
        <tr><td style="background-color:#ffffff;border:1px solid #e4dfec;border-top:5px solid #60547e;border-radius:16px;padding:36px 24px;">
          <p style="margin:0 0 12px;font-size:11px;font-weight:bold;letter-spacing:2px;color:#76678f;">UN PASO MÁS PARA CONECTARTE</p>
          <h1 style="margin:0 0 16px;font-family:Georgia,serif;font-size:30px;line-height:1.2;">Verifica tu correo</h1>
          <p style="margin:0 0 24px;font-size:16px;line-height:1.6;color:#625c70;">Usa este código en <strong>Mi cuenta</strong> para continuar con la vinculación de tu cuenta de Google.</p>
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
            <tr><td align="center" style="padding:24px 12px;background-color:#f1edf7;border:1px solid #e4dfec;border-radius:12px;">
              <p style="margin:0 0 12px;font-size:12px;color:#625c70;">TU CÓDIGO DE VERIFICACIÓN</p>
              <p dir="ltr" style="margin:0;font-family:Consolas,'Courier New',monospace;font-size:36px;font-weight:bold;letter-spacing:6px;color:#4e416b;">{escape(code)}</p>
            </td></tr>
          </table>
          <p style="margin:18px 0 24px;text-align:center;font-size:14px;color:#625c70;">Válido durante <strong>5 minutos</strong> · No lo compartas.</p>
          <p style="margin:0;padding-top:24px;border-top:1px solid #ece8f1;font-size:14px;line-height:1.6;color:#625c70;">Después de ingresar el código, confirma esta misma cuenta en Google para completar la vinculación.</p>
        </td></tr>
        <tr><td style="padding:24px 16px;text-align:center;font-size:12px;line-height:1.7;color:#726b80;">Si no solicitaste este código, puedes ignorar el correo.<br>Este es un mensaje automático de LibrIA.</td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>""", subtype="html")
    logo_path = Path(__file__).resolve().parents[2] / "assets" / "libriaverse_logo.png"
    message.get_body(preferencelist=("html",)).add_related(
        logo_path.read_bytes(), maintype="image", subtype="png",
        cid="<libriaverse-logo>", disposition="inline", filename="libriaverse_logo.png",
    )
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
