"""External delivery adapters for subscriptions and scheduled reports."""

import mimetypes
import smtplib
from email.message import EmailMessage
from pathlib import Path
from typing import Iterable

import httpx

from app.config import get_settings


class ReportDeliveryService:
    def __init__(self):
        self.settings = get_settings()

    def send_feishu_text(self, title: str, body: str) -> None:
        webhook_url = self.settings.feishu_webhook_url.strip()
        if not webhook_url:
            raise RuntimeError("未配置 FEISHU_WEBHOOK_URL")

        response = httpx.post(
            webhook_url,
            json={
                "msg_type": "text",
                "content": {"text": f"{title}\n{body}"},
            },
            timeout=10,
        )
        response.raise_for_status()
        try:
            payload = response.json()
        except ValueError:
            return
        code = payload.get("code", payload.get("StatusCode", 0))
        if code not in (0, "0", None):
            message = payload.get("msg") or payload.get("StatusMessage") or "飞书推送失败"
            raise RuntimeError(str(message))

    def send_email(
        self,
        recipients: Iterable[str],
        subject: str,
        body: str,
        attachment_path: str | None = None,
        attachment_name: str | None = None,
    ) -> None:
        addresses = sorted({address.strip() for address in recipients if address and address.strip()})
        if not addresses:
            raise RuntimeError("没有有效的邮件收件人")
        if not self.settings.smtp_host or not self.settings.smtp_from_address:
            raise RuntimeError("未配置 SMTP_HOST 或 SMTP_FROM_ADDRESS")

        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = self.settings.smtp_from_address
        message["To"] = ", ".join(addresses)
        message.set_content(body)

        if attachment_path:
            path = Path(attachment_path)
            content_type, _ = mimetypes.guess_type(path.name)
            maintype, subtype = (content_type or "application/octet-stream").split("/", 1)
            message.add_attachment(
                path.read_bytes(),
                maintype=maintype,
                subtype=subtype,
                filename=attachment_name or path.name,
            )

        with smtplib.SMTP(
            self.settings.smtp_host,
            self.settings.smtp_port,
            timeout=15,
        ) as smtp:
            if self.settings.smtp_use_tls:
                smtp.starttls()
            if self.settings.smtp_username:
                smtp.login(self.settings.smtp_username, self.settings.smtp_password)
            smtp.send_message(message)
