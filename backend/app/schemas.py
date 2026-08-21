from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr

LeadStatus = Literal["novo", "contatado", "interessado", "proposta", "cliente", "perdido"]
InboxStatus = Literal["new", "reviewed", "replied", "ignored"]


class ContactCreate(BaseModel):
    company: str
    name: str | None = None
    email: EmailStr
    phone: str | None = None
    city: str | None = None
    segment: str | None = None
    status: LeadStatus = "novo"
    source: str | None = None
    notes: str | None = None
    consent: bool = False


class ContactUpdate(BaseModel):
    company: str | None = None
    name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    city: str | None = None
    segment: str | None = None
    status: LeadStatus | None = None
    source: str | None = None
    notes: str | None = None
    consent: bool | None = None
    unsubscribed: bool | None = None


class CampaignCreate(BaseModel):
    name: str
    subject: str
    body: str
    target_city: str | None = None
    target_segment: str | None = None


class FollowUpCreate(BaseModel):
    contact_id: int
    due_at: datetime
    channel: Literal["email", "whatsapp", "telefone"] = "email"
    note: str | None = None


class IncomingReplyCreate(BaseModel):
    sender_email: EmailStr
    sender_name: str | None = None
    subject: str = ""
    body: str
    message_id: str | None = None
    received_at: datetime | None = None
