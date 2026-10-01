"""Regressao: opt-out tem precedencia e nao gera falso positivo em palavras compostas."""
import pytest

from app.services.reply_classifier import classify_reply, suggested_reply


class _Contact:
    name = None


@pytest.mark.parametrize(
    "body",
    [
        "sair",
        "SAIR",
        "Favor remover",
        "quero cancelar",
        "unsubscribe",
        "Nao quero receber mais e-mails",
        "Parem de enviar, por favor",
        "me remova da lista",
    ],
)
def test_optout_detectado(body):
    intent, _ = classify_reply("Re: contato", body)
    assert intent == "descadastro"


@pytest.mark.parametrize(
    "body",
    [
        "Nao temos interesse no momento, obrigado",
        "Ja temos fornecedor de TI",
        "Sem interesse por enquanto",
    ],
)
def test_nao_interessado(body):
    intent, _ = classify_reply("Re: contato", body)
    assert intent == "nao_interessado"


@pytest.mark.parametrize(
    "body,esperado",
    [
        ("Tenho interesse, pode mandar o valor?", "preco"),
        ("Podemos agendar uma videochamada?", "reuniao"),
        ("Como funciona o monitoramento?", "duvida"),
    ],
)
def test_intencoes_comerciais(body, esperado):
    intent, _ = classify_reply("Re: contato", body)
    assert intent == esperado


def test_optout_nao_casa_substring():
    """'assinar' nao pode disparar o opt-out curto 'sair'."""
    intent, _ = classify_reply("Re: contato", "Preciso assinar o contrato ainda hoje")
    assert intent != "descadastro"


def test_optout_tem_precedencia_sobre_interesse():
    """Mesmo com sinal comercial, pedido de saida vence."""
    intent, _ = classify_reply(
        "Re: contato", "Tenho interesse mas quero sair desta lista de e-mails"
    )
    assert intent == "descadastro"


def test_descadastro_nao_gera_resposta_automatica():
    assert suggested_reply(_Contact(), "descadastro") is None
    assert suggested_reply(_Contact(), "nao_interessado") is None
