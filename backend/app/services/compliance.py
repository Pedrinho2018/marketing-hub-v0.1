def can_receive_email(contact) -> tuple[bool, str]:
    if contact.unsubscribed:
        return False, "Contato descadastrado"
    if not contact.consent:
        return False, "Sem consentimento registrado"
    return True, "ok"
