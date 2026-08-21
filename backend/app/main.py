import csv
import hashlib
import io
from datetime import datetime

from fastapi import Depends, FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, inspect, or_, select, text
from sqlalchemy.orm import Session

from .database import Base, engine, get_db
from .models import Campaign, Contact, FollowUp, IncomingMessage, SendLog
from .schemas import CampaignCreate, ContactCreate, ContactUpdate, FollowUpCreate, IncomingReplyCreate
from .services.compliance import can_receive_email
from .services.email_sender import EmailSender
from .services.inbox_reader import InboxReader
from .services.reply_classifier import classify_reply, suggested_reply

app = FastAPI(title="Norte MT Marketing Hub", version="0.3.0")
templates = Jinja2Templates(directory="app/templates")
Base.metadata.create_all(bind=engine)


def ensure_legacy_columns() -> None:
    """Mantém bancos criados pela V0.1/V0.2 compatíveis com a V0.3.

    Para produção, o próximo passo é substituir isto por Alembic.
    """
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    migrations = {
        "contacts": {
            "status": "ALTER TABLE contacts ADD COLUMN status VARCHAR(30) NOT NULL DEFAULT 'novo'",
            "source": "ALTER TABLE contacts ADD COLUMN source VARCHAR(120)",
            "notes": "ALTER TABLE contacts ADD COLUMN notes TEXT",
            "updated_at": "ALTER TABLE contacts ADD COLUMN updated_at TIMESTAMP",
        },
        "campaigns": {
            "target_city": "ALTER TABLE campaigns ADD COLUMN target_city VARCHAR(120)",
            "target_segment": "ALTER TABLE campaigns ADD COLUMN target_segment VARCHAR(120)",
        },
    }

    with engine.begin() as conn:
        for table_name, columns in migrations.items():
            if table_name not in tables:
                continue
            existing = {column["name"] for column in inspect(engine).get_columns(table_name)}
            for column_name, statement in columns.items():
                if column_name not in existing:
                    conn.execute(text(statement))


ensure_legacy_columns()


def render_for_contact(value: str, contact: Contact) -> str:
    replacements = {
        "{{empresa}}": contact.company or "",
        "{{nome}}": contact.name or "",
        "{{cidade}}": contact.city or "",
        "{{segmento}}": contact.segment or "",
    }
    rendered = value
    for key, replacement in replacements.items():
        rendered = rendered.replace(key, replacement)
    return rendered


def pipeline_stats(db: Session) -> dict[str, int]:
    statuses = ["novo", "contatado", "interessado", "proposta", "cliente", "perdido"]
    return {
        status: db.scalar(
            select(func.count()).select_from(Contact).where(Contact.status == status)
        )
        or 0
        for status in statuses
    }


def normalize_received_at(value: datetime | None) -> datetime:
    if value is None:
        return datetime.utcnow()
    if value.tzinfo is not None:
        return value.astimezone().replace(tzinfo=None)
    return value


def generated_message_id(sender_email: str, subject: str, body: str, received_at: datetime) -> str:
    digest = hashlib.sha256(
        f"{sender_email}|{subject}|{received_at.isoformat()}|{body}".encode("utf-8", errors="ignore")
    ).hexdigest()
    return f"generated:{digest}"


def find_contact_by_email(db: Session, sender_email: str) -> Contact | None:
    return db.scalar(
        select(Contact).where(func.lower(Contact.email) == sender_email.lower().strip())
    )


def apply_intent_to_contact(contact: Contact | None, intent: str) -> None:
    if contact is None:
        return

    if intent == "descadastro":
        contact.unsubscribed = True
        if contact.status != "cliente":
            contact.status = "perdido"
    elif intent == "nao_interessado":
        if contact.status != "cliente":
            contact.status = "perdido"
    elif intent in {"reuniao", "preco", "interessado", "duvida"}:
        if contact.status in {"novo", "contatado"}:
            contact.status = "interessado"

    contact.updated_at = datetime.utcnow()


def ingest_incoming_message(
    db: Session,
    *,
    sender_email: str,
    sender_name: str | None,
    subject: str,
    body: str,
    message_id: str | None,
    received_at: datetime | None,
) -> tuple[IncomingMessage, bool]:
    sender_email = sender_email.lower().strip()
    if not sender_email:
        raise ValueError("Mensagem sem remetente")

    received_at = normalize_received_at(received_at)
    message_id = (message_id or "").strip()[:255]
    if not message_id:
        message_id = generated_message_id(sender_email, subject, body, received_at)

    existing = db.scalar(
        select(IncomingMessage).where(IncomingMessage.message_id == message_id)
    )
    if existing:
        return existing, False

    contact = find_contact_by_email(db, sender_email)
    intent, action = classify_reply(subject, body)
    suggestion = suggested_reply(contact, intent)

    item = IncomingMessage(
        contact_id=contact.id if contact else None,
        message_id=message_id,
        sender_email=sender_email,
        sender_name=(sender_name or "").strip() or None,
        subject=(subject or "")[:500],
        body=(body or "")[:50000],
        intent=intent,
        recommended_action=action,
        suggested_reply=suggestion,
        status="new",
        received_at=received_at,
    )
    db.add(item)
    apply_intent_to_contact(contact, intent)
    db.commit()
    db.refresh(item)
    return item, True


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    contacts = db.scalar(select(func.count()).select_from(Contact)) or 0
    campaigns = db.scalar(select(func.count()).select_from(Campaign)) or 0
    sends = db.scalar(select(func.count()).select_from(SendLog)) or 0
    interested = db.scalar(
        select(func.count()).select_from(Contact).where(Contact.status == "interessado")
    ) or 0
    clients = db.scalar(
        select(func.count()).select_from(Contact).where(Contact.status == "cliente")
    ) or 0
    followups_due = db.scalar(
        select(func.count())
        .select_from(FollowUp)
        .where(FollowUp.status == "pending", FollowUp.due_at <= datetime.utcnow())
    ) or 0
    inbox_new = db.scalar(
        select(func.count())
        .select_from(IncomingMessage)
        .where(IncomingMessage.status == "new")
    ) or 0

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "contacts": contacts,
            "campaigns": campaigns,
            "sends": sends,
            "interested": interested,
            "clients": clients,
            "followups_due": followups_due,
            "inbox_new": inbox_new,
            "pipeline": pipeline_stats(db),
        },
    )


@app.get("/health")
def health():
    return {"status": "ok", "version": "0.3.0"}


@app.get("/stats")
def stats(db: Session = Depends(get_db)):
    return {
        "contacts": db.scalar(select(func.count()).select_from(Contact)) or 0,
        "campaigns": db.scalar(select(func.count()).select_from(Campaign)) or 0,
        "sends": db.scalar(select(func.count()).select_from(SendLog)) or 0,
        "inbox_new": db.scalar(
            select(func.count()).select_from(IncomingMessage).where(IncomingMessage.status == "new")
        )
        or 0,
        "pipeline": pipeline_stats(db),
    }


@app.get("/contacts")
def list_contacts(
    status: str | None = Query(default=None),
    city: str | None = Query(default=None),
    segment: str | None = Query(default=None),
    q: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    stmt = select(Contact)
    if status:
        stmt = stmt.where(Contact.status == status)
    if city:
        stmt = stmt.where(Contact.city.ilike(city))
    if segment:
        stmt = stmt.where(Contact.segment.ilike(segment))
    if q:
        pattern = f"%{q}%"
        stmt = stmt.where(
            or_(
                Contact.company.ilike(pattern),
                Contact.name.ilike(pattern),
                Contact.email.ilike(pattern),
            )
        )
    return db.scalars(stmt.order_by(Contact.id.desc()).limit(500)).all()


@app.post("/contacts")
def create_contact(payload: ContactCreate, db: Session = Depends(get_db)):
    if db.scalar(select(Contact).where(Contact.email == payload.email)):
        raise HTTPException(409, "E-mail já cadastrado")
    item = Contact(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@app.patch("/contacts/{contact_id}")
def update_contact(contact_id: int, payload: ContactUpdate, db: Session = Depends(get_db)):
    contact = db.get(Contact, contact_id)
    if not contact:
        raise HTTPException(404, "Contato não encontrado")

    changes = payload.model_dump(exclude_unset=True)
    new_email = changes.get("email")
    if new_email:
        duplicate = db.scalar(
            select(Contact).where(Contact.email == new_email, Contact.id != contact_id)
        )
        if duplicate:
            raise HTTPException(409, "E-mail já cadastrado em outro contato")

    for field, value in changes.items():
        setattr(contact, field, value)
    contact.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(contact)
    return contact


@app.post("/contacts/import-csv")
async def import_contacts_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(400, "Envie um arquivo CSV")

    raw = await file.read()
    if len(raw) > 5 * 1024 * 1024:
        raise HTTPException(413, "CSV maior que 5 MB")

    try:
        content = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(400, "Use CSV em UTF-8") from exc

    try:
        dialect = csv.Sniffer().sniff(content[:4096], delimiters=",;")
    except csv.Error:
        dialect = csv.excel

    reader = csv.DictReader(io.StringIO(content), dialect=dialect)
    created = skipped = invalid = 0

    def value(row: dict, *keys: str) -> str:
        for key in keys:
            if row.get(key) is not None:
                return str(row.get(key, "")).strip()
        return ""

    for row in reader:
        company = value(row, "company", "empresa")
        email = value(row, "email", "e-mail")
        if not company or not email:
            invalid += 1
            continue

        if db.scalar(select(Contact.id).where(Contact.email == email)):
            skipped += 1
            continue

        consent_raw = value(row, "consent", "consentimento").lower()
        consent = consent_raw in {"1", "true", "sim", "s", "yes"}

        try:
            payload = ContactCreate(
                company=company,
                name=value(row, "name", "nome") or None,
                email=email,
                phone=value(row, "phone", "telefone") or None,
                city=value(row, "city", "cidade") or None,
                segment=value(row, "segment", "segmento", "ramo") or None,
                source=value(row, "source", "origem") or "csv",
                consent=consent,
            )
        except Exception:
            invalid += 1
            continue

        db.add(Contact(**payload.model_dump()))
        created += 1

    db.commit()
    return {"created": created, "skipped": skipped, "invalid": invalid}


@app.get("/campaigns")
def list_campaigns(db: Session = Depends(get_db)):
    return db.scalars(select(Campaign).order_by(Campaign.id.desc())).all()


@app.post("/campaigns")
def create_campaign(payload: CampaignCreate, db: Session = Depends(get_db)):
    item = Campaign(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@app.post("/campaigns/{campaign_id}/send")
def send_campaign(campaign_id: int, db: Session = Depends(get_db)):
    campaign = db.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(404, "Campanha não encontrada")

    sender = EmailSender()
    stmt = select(Contact)
    if campaign.target_city:
        stmt = stmt.where(Contact.city.ilike(campaign.target_city))
    if campaign.target_segment:
        stmt = stmt.where(Contact.segment.ilike(campaign.target_segment))

    contacts = db.scalars(stmt).all()
    sent = skipped = failed = 0
    skip_reasons: dict[str, int] = {}

    for contact in contacts:
        allowed, reason = can_receive_email(contact)
        if not allowed:
            skipped += 1
            skip_reasons[reason] = skip_reasons.get(reason, 0) + 1
            continue

        already_sent = db.scalar(
            select(SendLog.id).where(
                SendLog.campaign_id == campaign.id,
                SendLog.contact_id == contact.id,
                SendLog.status == "sent",
            )
        )
        if already_sent:
            skipped += 1
            skip_reasons["Campanha já enviada"] = skip_reasons.get("Campanha já enviada", 0) + 1
            continue

        log = SendLog(campaign_id=campaign.id, contact_id=contact.id, status="processing")
        db.add(log)
        db.flush()

        try:
            subject = render_for_contact(campaign.subject, contact)
            body = render_for_contact(campaign.body, contact)
            provider_id = sender.send(contact.email, subject, body)
            log.status = "dry-run" if sender.dry_run else "sent"
            log.provider_message_id = provider_id
            sent += 1
            if not sender.dry_run and contact.status == "novo":
                contact.status = "contatado"
                contact.updated_at = datetime.utcnow()
        except Exception as exc:
            log.status = "failed"
            log.error = str(exc)[:2000]
            failed += 1

    if sender.dry_run:
        campaign.status = "dry-run"
    else:
        campaign.status = "sent" if failed == 0 else "partial"

    db.commit()
    return {
        "matched": len(contacts),
        "sent": sent,
        "skipped": skipped,
        "failed": failed,
        "skip_reasons": skip_reasons,
        "dry_run": sender.dry_run,
    }


@app.get("/followups")
def list_followups(status: str | None = None, db: Session = Depends(get_db)):
    stmt = select(FollowUp)
    if status:
        stmt = stmt.where(FollowUp.status == status)
    return db.scalars(stmt.order_by(FollowUp.due_at.asc()).limit(500)).all()


@app.get("/followups/due")
def due_followups(db: Session = Depends(get_db)):
    return db.scalars(
        select(FollowUp)
        .where(FollowUp.status == "pending", FollowUp.due_at <= datetime.utcnow())
        .order_by(FollowUp.due_at.asc())
    ).all()


@app.post("/followups")
def create_followup(payload: FollowUpCreate, db: Session = Depends(get_db)):
    if not db.get(Contact, payload.contact_id):
        raise HTTPException(404, "Contato não encontrado")
    item = FollowUp(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@app.patch("/followups/{followup_id}/done")
def complete_followup(followup_id: int, db: Session = Depends(get_db)):
    item = db.get(FollowUp, followup_id)
    if not item:
        raise HTTPException(404, "Follow-up não encontrado")
    item.status = "done"
    item.completed_at = datetime.utcnow()
    db.commit()
    db.refresh(item)
    return item


@app.get("/inbox")
def list_inbox(
    status: str | None = Query(default=None),
    intent: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    stmt = select(IncomingMessage)
    if status:
        stmt = stmt.where(IncomingMessage.status == status)
    if intent:
        stmt = stmt.where(IncomingMessage.intent == intent)
    return db.scalars(stmt.order_by(IncomingMessage.received_at.desc()).limit(500)).all()


@app.post("/inbox/replies")
def ingest_reply(payload: IncomingReplyCreate, db: Session = Depends(get_db)):
    try:
        item, created = ingest_incoming_message(
            db,
            sender_email=str(payload.sender_email),
            sender_name=payload.sender_name,
            subject=payload.subject,
            body=payload.body,
            message_id=payload.message_id,
            received_at=payload.received_at,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"created": created, "message": item}


@app.post("/inbox/sync")
def sync_inbox(limit: int = Query(default=50, ge=1, le=200), db: Session = Depends(get_db)):
    reader = InboxReader()
    if not reader.configured:
        return {
            "configured": False,
            "fetched": 0,
            "created": 0,
            "duplicates": 0,
            "invalid": 0,
            "message": "Configure IMAP_HOST, IMAP_USER e IMAP_PASSWORD para ler a caixa real.",
        }

    fetched = created = duplicates = invalid = 0

    try:
        with reader:
            messages = reader.fetch_unseen(limit=limit)
            fetched = len(messages)
            for message in messages:
                if not message["sender_email"]:
                    invalid += 1
                    reader.mark_seen(message["imap_id"])
                    continue
                try:
                    _, was_created = ingest_incoming_message(
                        db,
                        sender_email=message["sender_email"],
                        sender_name=message["sender_name"],
                        subject=message["subject"],
                        body=message["body"],
                        message_id=message["message_id"],
                        received_at=message["received_at"],
                    )
                    if was_created:
                        created += 1
                    else:
                        duplicates += 1
                    reader.mark_seen(message["imap_id"])
                except Exception:
                    db.rollback()
                    invalid += 1
    except Exception as exc:
        raise HTTPException(502, f"Falha ao sincronizar IMAP: {exc}") from exc

    return {
        "configured": True,
        "fetched": fetched,
        "created": created,
        "duplicates": duplicates,
        "invalid": invalid,
    }


@app.patch("/inbox/{message_id}/reviewed")
def mark_inbox_reviewed(message_id: int, db: Session = Depends(get_db)):
    item = db.get(IncomingMessage, message_id)
    if not item:
        raise HTTPException(404, "Mensagem não encontrada")
    if item.status == "new":
        item.status = "reviewed"
        db.commit()
        db.refresh(item)
    return item


@app.patch("/inbox/{message_id}/ignore")
def ignore_inbox_message(message_id: int, db: Session = Depends(get_db)):
    item = db.get(IncomingMessage, message_id)
    if not item:
        raise HTTPException(404, "Mensagem não encontrada")
    item.status = "ignored"
    db.commit()
    db.refresh(item)
    return item


@app.post("/inbox/{message_id}/approve-send")
def approve_and_send_reply(message_id: int, db: Session = Depends(get_db)):
    item = db.get(IncomingMessage, message_id)
    if not item:
        raise HTTPException(404, "Mensagem não encontrada")
    if item.status == "replied":
        raise HTTPException(409, "Esta mensagem já foi respondida")
    if item.intent in {"descadastro", "nao_interessado"}:
        raise HTTPException(409, "Resposta automática bloqueada para este tipo de retorno")
    if not item.suggested_reply:
        raise HTTPException(409, "Não existe resposta sugerida para esta mensagem")

    contact = db.get(Contact, item.contact_id) if item.contact_id else None
    if contact and contact.unsubscribed:
        raise HTTPException(409, "Contato está descadastrado")

    subject = item.subject.strip()
    if not subject.lower().startswith("re:"):
        subject = f"Re: {subject}" if subject else "Re: Contato Norte MT Sistemas"

    sender = EmailSender()
    provider_id = sender.send(item.sender_email, subject, item.suggested_reply)
    item.reply_provider_message_id = provider_id

    if sender.dry_run:
        item.status = "reviewed"
    else:
        item.status = "replied"
        item.replied_at = datetime.utcnow()

    db.commit()
    db.refresh(item)
    return {
        "message": item,
        "dry_run": sender.dry_run,
        "provider_message_id": provider_id,
    }
