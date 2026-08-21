import uuid

from fastapi.testclient import TestClient

from app.main import app
from app.services.email_sender import EmailSender
from app.services.reply_classifier import classify_reply


client = TestClient(app)


def test_health_v03():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "0.3.0"}


def test_reply_classifier_detects_price_request():
    intent, action = classify_reply(
        "Re: Serviços de TI",
        "Tenho interesse. Você consegue me passar um valor?",
    )
    assert intent == "preco"
    assert action


def test_email_sender_is_safe_without_smtp():
    sender = EmailSender()
    assert sender.dry_run is True
    provider_id = sender.send(
        "teste@example.com",
        "Teste CI",
        "Nenhum e-mail real deve sair durante o CI.",
    )
    assert provider_id.startswith("dry-run:")


def test_incoming_reply_updates_lead_pipeline():
    token = uuid.uuid4().hex[:10]
    email = f"ci-{token}@example.com"

    contact = client.post(
        "/contacts",
        json={
            "company": f"Empresa CI {token}",
            "name": "Cliente Teste",
            "email": email,
            "city": "Sinop",
            "segment": "Teste",
            "consent": True,
        },
    )
    assert contact.status_code == 200, contact.text

    reply = client.post(
        "/inbox/replies",
        json={
            "sender_email": email,
            "sender_name": "Cliente Teste",
            "subject": "Re: Serviços de TI",
            "body": "Tenho interesse. Você consegue me passar um valor?",
        },
    )
    assert reply.status_code == 200, reply.text
    payload = reply.json()
    assert payload["intent"] == "preco"
    assert payload["suggested_reply"]

    contacts = client.get("/contacts", params={"q": email})
    assert contacts.status_code == 200
    rows = contacts.json()
    assert len(rows) == 1
    assert rows[0]["status"] == "interessado"
