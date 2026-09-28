from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage


class MailConfigError(RuntimeError):
    pass


def send_html(subject: str, html_body: str) -> None:
    host = os.getenv("SMTP_HOST", "").strip()
    username = os.getenv("SMTP_USERNAME", "").strip()
    password = os.getenv("SMTP_PASSWORD", "")
    mail_to = os.getenv("MAIL_TO", "").strip()
    mail_from = os.getenv("MAIL_FROM", "").strip() or username
    security = (os.getenv("SMTP_SECURITY", "").strip().lower() or "starttls")
    default_port = "465" if security == "ssl" else "587"
    port = int(os.getenv("SMTP_PORT", "").strip() or default_port)

    missing = [name for name, value in {
        "SMTP_HOST": host,
        "SMTP_USERNAME": username,
        "SMTP_PASSWORD": password,
        "MAIL_TO": mail_to,
        "MAIL_FROM": mail_from,
    }.items() if not value]
    if missing:
        raise MailConfigError(f"Missing mail configuration: {', '.join(missing)}")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = mail_from
    message["To"] = mail_to
    message.set_content("请使用支持 HTML 的邮件客户端查看估值日报。")
    message.add_alternative(html_body, subtype="html")

    if security == "ssl":
        with smtplib.SMTP_SSL(host, port, timeout=30) as smtp:
            smtp.login(username, password)
            smtp.send_message(message)
    else:
        with smtplib.SMTP(host, port, timeout=30) as smtp:
            smtp.ehlo()
            if security == "starttls":
                smtp.starttls()
                smtp.ehlo()
            smtp.login(username, password)
            smtp.send_message(message)
