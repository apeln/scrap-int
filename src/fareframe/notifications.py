from __future__ import annotations

from email.message import EmailMessage
import smtplib

from fareframe.settings import EmailSettings


def send_email_report(
    *,
    email_settings: EmailSettings,
    site: str,
    report_body: str,
) -> None:
    if not email_settings.enabled:
        return

    if not email_settings.to:
        raise ValueError("Email notifications are enabled but no recipients are configured")
    if not email_settings.smtp_host:
        raise ValueError("Email notifications are enabled but smtp_host is not configured")
    if not email_settings.from_address:
        raise ValueError("Email notifications are enabled but from_address is not configured")

    message = EmailMessage()
    message["Subject"] = f"{email_settings.subject_prefix} {site} report"
    message["From"] = email_settings.from_address
    message["To"] = ", ".join(email_settings.to)
    message.set_content(report_body)

    with smtplib.SMTP(email_settings.smtp_host, email_settings.smtp_port, timeout=30) as smtp:
        if email_settings.use_tls:
            smtp.starttls()
        if email_settings.smtp_username:
            smtp.login(email_settings.smtp_username, email_settings.smtp_password)
        smtp.send_message(message)
