from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .database import Base, engine, get_db
from .models import Campaign, Contact, SendLog
from .schemas import CampaignCreate, ContactCreate
from .services.compliance import can_receive_email
from .services.email_sender import EmailSender

app = FastAPI(title="Norte MT Marketing Hub", version="0.1.0")
templates = Jinja2Templates(directory="app/templates")
Base.metadata.create_all(bind=engine)

@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    contacts = db.scalar(select(func.count()).select_from(Contact)) or 0
    campaigns = db.scalar(select(func.count()).select_from(Campaign)) or 0
    sends = db.scalar(select(func.count()).select_from(SendLog)) or 0
    return templates.TemplateResponse("index.html", {"request": request, "contacts": contacts, "campaigns": campaigns, "sends": sends})

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/contacts")
def list_contacts(db: Session = Depends(get_db)):
    return db.scalars(select(Contact).order_by(Contact.id.desc())).all()

@app.post("/contacts")
def create_contact(payload: ContactCreate, db: Session = Depends(get_db)):
    if db.scalar(select(Contact).where(Contact.email == payload.email)):
        raise HTTPException(409, "E-mail já cadastrado")
    item = Contact(**payload.model_dump())
    db.add(item); db.commit(); db.refresh(item)
    return item

@app.get("/campaigns")
def list_campaigns(db: Session = Depends(get_db)):
    return db.scalars(select(Campaign).order_by(Campaign.id.desc())).all()

@app.post("/campaigns")
def create_campaign(payload: CampaignCreate, db: Session = Depends(get_db)):
    item = Campaign(**payload.model_dump())
    db.add(item); db.commit(); db.refresh(item)
    return item

@app.post("/campaigns/{campaign_id}/send")
def send_campaign(campaign_id: int, db: Session = Depends(get_db)):
    campaign = db.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(404, "Campanha não encontrada")

    sender = EmailSender()
    contacts = db.scalars(select(Contact)).all()
    sent = skipped = failed = 0

    for contact in contacts:
        allowed, reason = can_receive_email(contact)
        if not allowed:
            skipped += 1
            continue
        log = SendLog(campaign_id=campaign.id, contact_id=contact.id, status="processing")
        db.add(log); db.flush()
        try:
            pid = sender.send(contact.email, campaign.subject, campaign.body)
            log.status = "sent"; log.provider_message_id = pid; sent += 1
        except Exception as exc:
            log.status = "failed"; log.error = str(exc); failed += 1

    campaign.status = "sent" if failed == 0 else "partial"
    db.commit()
    return {"sent": sent, "skipped": skipped, "failed": failed, "dry_run": sender.dry_run}
