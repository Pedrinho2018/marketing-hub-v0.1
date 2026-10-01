import re
import unicodedata


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    return "".join(ch for ch in normalized if not unicodedata.combining(ch)).lower()


# Palavras curtas de descadastro: exigem limite de palavra para nao casar
# dentro de outras palavras ("sair" em "sairemos", "sai" em "assinar").
STANDALONE_OPTOUT = ("sair", "remover", "descadastrar", "stop", "cancelar")


def _has_standalone_optout(text: str) -> bool:
    return any(re.search(rf"\b{re.escape(w)}\b", text) for w in STANDALONE_OPTOUT)


def classify_reply(subject: str, body: str) -> tuple[str, str]:
    text = normalize_text(f"{subject}\n{body}")

    # Opt-out tem precedencia absoluta sobre qualquer outra intencao.
    if _has_standalone_optout(text):
        return "descadastro", "Descadastrar contato e não enviar novas campanhas."

    rules = [
        (
            "descadastro",
            (
                "descadastrar",
                "descadastro",
                "remova meu email",
                "remover meu email",
                "remova meu e-mail",
                "remover meu e-mail",
                "remova-me",
                "me remova",
                "pare de enviar",
                "parem de enviar",
                "nao envie mais",
                "não envie mais",
                "nao enviem mais",
                "não enviem mais",
                "nao quero receber",
                "não quero receber",
                "cancelar inscricao",
                "cancelar inscrição",
                "unsubscribe",
                "opt-out",
                "opt out",
            ),
            "Descadastrar contato e não enviar novas campanhas.",
        ),
        (
            "nao_interessado",
            (
                "nao tenho interesse",
                "não tenho interesse",
                "nao temos interesse",
                "não temos interesse",
                "sem interesse",
                "nao ha interesse",
                "não há interesse",
                "nao precisamos",
                "não precisamos",
                "nao preciso",
                "não preciso",
                "ja temos fornecedor",
                "já temos fornecedor",
                "ja possuimos",
                "já possuímos",
                "nao quero",
                "não quero",
            ),
            "Encerrar abordagem comercial e marcar o lead como perdido.",
        ),
        (
            "reuniao",
            (
                "reuniao",
                "reunião",
                "agenda",
                "agendar",
                "horario",
                "horário",
                "podemos conversar",
                "ligacao",
                "ligação",
                "videochamada",
            ),
            "Responder propondo horários e avançar o lead para interessado.",
        ),
        (
            "preco",
            (
                "preco",
                "preço",
                "valor",
                "orcamento",
                "orçamento",
                "quanto custa",
                "cotacao",
                "cotação",
                "proposta",
            ),
            "Levantar necessidade e preparar orçamento/proposta comercial.",
        ),
        (
            "interessado",
            (
                "tenho interesse",
                "interessado",
                "interessada",
                "quero saber mais",
                "me explique",
                "pode me passar",
                "gostaria de saber",
            ),
            "Priorizar contato e entender a necessidade da empresa.",
        ),
        (
            "duvida",
            ("como funciona", "duvida", "dúvida", "poderia explicar", "o que voces fazem", "o que vocês fazem"),
            "Responder a dúvida e manter o lead em acompanhamento.",
        ),
    ]

    for intent, terms, action in rules:
        if any(term in text for term in terms):
            return intent, action

    if "?" in body:
        return "duvida", "Responder a dúvida e manter o lead em acompanhamento."

    return "outro", "Revisar manualmente a mensagem antes de responder."


def suggested_reply(contact, intent: str) -> str | None:
    first_name = (contact.name.split()[0] if contact and contact.name else "").strip()
    greeting = f"Olá, {first_name}!" if first_name else "Olá!"

    if intent == "descadastro":
        return None
    if intent == "nao_interessado":
        return None
    if intent == "reuniao":
        return (
            f"{greeting}\n\n"
            "Obrigado pelo retorno. Podemos conversar para entender melhor o cenário da sua empresa e verificar onde a Norte MT Sistemas pode ajudar.\n\n"
            "Me informe, por favor, dois horários que funcionem para você e alinhamos a conversa.\n\n"
            "Atenciosamente,\nNorte MT Sistemas"
        )
    if intent == "preco":
        return (
            f"{greeting}\n\n"
            "Obrigado pelo retorno. Para passar um valor coerente, precisamos entender rapidamente o ambiente e a necessidade da empresa.\n\n"
            "Qual serviço você procura e quantos usuários ou equipamentos aproximadamente precisam ser atendidos?\n\n"
            "Com isso conseguimos direcionar uma proposta mais adequada.\n\n"
            "Atenciosamente,\nNorte MT Sistemas"
        )
    if intent == "interessado":
        return (
            f"{greeting}\n\n"
            "Obrigado pelo interesse. Podemos entender o seu cenário atual e indicar a solução mais adequada em suporte, infraestrutura, redes, automação ou segurança.\n\n"
            "Qual é hoje o principal problema de TI que vocês querem resolver?\n\n"
            "Atenciosamente,\nNorte MT Sistemas"
        )
    if intent == "duvida":
        return (
            f"{greeting}\n\n"
            "Obrigado pela mensagem. Recebemos sua dúvida e vamos responder de forma objetiva conforme a necessidade da sua empresa.\n\n"
            "Se puder detalhar um pouco mais o cenário atual, conseguimos direcionar melhor a solução.\n\n"
            "Atenciosamente,\nNorte MT Sistemas"
        )
    return (
        f"{greeting}\n\n"
        "Obrigado pelo retorno. Recebemos sua mensagem e queremos entender melhor como podemos ajudar.\n\n"
        "Pode nos contar um pouco mais sobre a necessidade da empresa?\n\n"
        "Atenciosamente,\nNorte MT Sistemas"
    )
