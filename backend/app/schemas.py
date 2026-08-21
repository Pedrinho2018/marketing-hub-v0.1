from pydantic import BaseModel, EmailStr

class ContactCreate(BaseModel):
    company: str
    name: str | None = None
    email: EmailStr
    phone: str | None = None
    city: str | None = None
    segment: str | None = None
    consent: bool = False

class CampaignCreate(BaseModel):
    name: str
    subject: str
    body: str
