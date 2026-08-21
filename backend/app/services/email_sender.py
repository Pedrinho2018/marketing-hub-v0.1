import os
import smtplib
from email.message import EmailMessage

class EmailSender:
    def __init__(self):
        self.host = os.getenv("SMTP_HOST", "")
        self.port = int(os.getenv("SMTP_PORT", "587"))
        self.user = os.getenv("SMTP_USER", "")
        self.password = os.getenv("SMTP_PASSWORD", "")
        self.from_addr = os.getenv("SMTP_FROM", "contato@nortemtsistemas.com.br")

    @property
    def dry_run(self) -> bool:
        return not self.host

    def send(self, to: str, subject: str, body: str) -> str:
        if self.dry_run:
            return f"dry-run:{to}"

        msg = EmailMessage()
        msg["From"] = self.from_addr
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)

        with smtplib.SMTP(self.host, self.port, timeout=30) as smtp:
            smtp.starttls()
            if self.user:
                smtp.login(self.user, self.password)
            smtp.send_message(msg)
        return "smtp:sent"
