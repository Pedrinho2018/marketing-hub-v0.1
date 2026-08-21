import hashlib
import html
import imaplib
import os
import re
from datetime import datetime
from email import message_from_bytes
from email.header import decode_header
from email.message import Message
from email.utils import parseaddr, parsedate_to_datetime


def decode_mime(value: str | None) -> str:
    if not value:
        return ""
    parts: list[str] = []
    for chunk, encoding in decode_header(value):
        if isinstance(chunk, bytes):
            parts.append(chunk.decode(encoding or "utf-8", errors="replace"))
        else:
            parts.append(chunk)
    return "".join(parts)


def text_body(message: Message) -> str:
    plain_parts: list[str] = []
    html_parts: list[str] = []

    for part in message.walk() if message.is_multipart() else [message]:
        if part.get_content_disposition() == "attachment":
            continue
        content_type = part.get_content_type()
        if content_type not in {"text/plain", "text/html"}:
            continue
        payload = part.get_payload(decode=True)
        if payload is None:
            continue
        charset = part.get_content_charset() or "utf-8"
        value = payload.decode(charset, errors="replace")
        if content_type == "text/plain":
            plain_parts.append(value)
        else:
            html_parts.append(value)

    if plain_parts:
        return "\n".join(plain_parts).strip()

    raw_html = "\n".join(html_parts)
    without_tags = re.sub(r"<[^>]+>", " ", raw_html)
    return re.sub(r"\s+", " ", html.unescape(without_tags)).strip()


class InboxReader:
    def __init__(self):
        self.host = os.getenv("IMAP_HOST", "")
        self.port = int(os.getenv("IMAP_PORT", "993"))
        self.user = os.getenv("IMAP_USER", "")
        self.password = os.getenv("IMAP_PASSWORD", "")
        self.mailbox = os.getenv("IMAP_MAILBOX", "INBOX")
        self.connection: imaplib.IMAP4_SSL | None = None

    @property
    def configured(self) -> bool:
        return bool(self.host and self.user and self.password)

    def __enter__(self):
        if not self.configured:
            return self
        self.connection = imaplib.IMAP4_SSL(self.host, self.port)
        self.connection.login(self.user, self.password)
        status, _ = self.connection.select(self.mailbox)
        if status != "OK":
            raise RuntimeError(f"Não foi possível abrir a caixa {self.mailbox}")
        return self

    def __exit__(self, exc_type, exc, tb):
        if self.connection is not None:
            try:
                self.connection.close()
            except Exception:
                pass
            try:
                self.connection.logout()
            except Exception:
                pass
        self.connection = None

    def fetch_unseen(self, limit: int = 50) -> list[dict]:
        if not self.configured:
            return []
        if self.connection is None:
            raise RuntimeError("Conexão IMAP não iniciada")

        status, data = self.connection.search(None, "UNSEEN")
        if status != "OK" or not data:
            return []

        ids = data[0].split()[-limit:]
        messages: list[dict] = []

        for imap_id in ids:
            status, payload = self.connection.fetch(imap_id, "(BODY.PEEK[])")
            if status != "OK" or not payload:
                continue

            raw = next((item[1] for item in payload if isinstance(item, tuple)), None)
            if not raw:
                continue

            message = message_from_bytes(raw)
            sender_name, sender_email = parseaddr(decode_mime(message.get("From")))
            subject = decode_mime(message.get("Subject"))
            body = text_body(message)[:50000]
            raw_message_id = (message.get("Message-ID") or "").strip()

            try:
                received_at = parsedate_to_datetime(message.get("Date")) if message.get("Date") else None
                if received_at and received_at.tzinfo:
                    received_at = received_at.astimezone().replace(tzinfo=None)
            except Exception:
                received_at = None

            if not raw_message_id:
                digest = hashlib.sha256(
                    f"{sender_email}|{subject}|{received_at}|{body}".encode("utf-8", errors="ignore")
                ).hexdigest()
                raw_message_id = f"generated:{digest}"

            messages.append(
                {
                    "imap_id": imap_id.decode(),
                    "message_id": raw_message_id[:255],
                    "sender_email": sender_email.lower().strip(),
                    "sender_name": sender_name.strip() or None,
                    "subject": subject[:500],
                    "body": body,
                    "received_at": received_at or datetime.utcnow(),
                }
            )

        return messages

    def mark_seen(self, imap_id: str) -> None:
        if self.connection is None:
            return
        self.connection.store(imap_id, "+FLAGS", "\\Seen")
