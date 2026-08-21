# Norte MT Marketing Hub

Plataforma própria de CRM, prospecção e automação de divulgação da Norte MT Sistemas.

## Versão atual: V0.2

### O que já existe
- CRM de empresas e contatos
- Funil comercial: `novo`, `contatado`, `interessado`, `proposta`, `cliente`, `perdido`
- Busca e filtros por cidade, segmento, status e texto
- Importação de contatos via CSV
- Cadastro de campanhas
- Segmentação de campanhas por cidade e segmento
- Personalização de assunto e mensagem por contato
- Disparo SMTP com modo seguro `dry-run`
- Bloqueio de reenvio duplicado de campanhas já enviadas
- Registro de envios e falhas
- Controle de consentimento e descadastro
- Follow-ups por e-mail, WhatsApp ou telefone
- Dashboard com métricas e funil comercial
- Docker Compose com PostgreSQL + Redis
- Compatibilidade automática com banco criado na V0.1

## Stack
- Python / FastAPI
- SQLAlchemy
- PostgreSQL 17
- Redis
- Docker Compose

## Rodar

```bash
docker compose up --build
```

Acesse:
- Dashboard: http://localhost:8000
- Swagger: http://localhost:8000/docs
- Health: http://localhost:8000/health

## Teste sem enviar e-mail real

Enquanto `SMTP_HOST` estiver vazio, o sistema permanece em `dry-run`. As campanhas são processadas e registradas, mas nenhum e-mail real sai.

## Funil de leads

Estados disponíveis:

```text
novo -> contatado -> interessado -> proposta -> cliente
                                      \
                                       -> perdido
```

Atualize um contato pela API:

```http
PATCH /contacts/{id}
```

Exemplo:

```json
{
  "status": "interessado",
  "notes": "Empresa pediu apresentação dos serviços"
}
```

## Importar empresas por CSV

Endpoint:

```http
POST /contacts/import-csv
```

O arquivo pode usar `,` ou `;` como separador.

Cabeçalhos aceitos em português ou inglês:

```text
empresa,nome,email,telefone,cidade,segmento,origem,consentimento
```

Existe um modelo em `examples/contatos.csv`.

## Campanhas segmentadas

Ao criar uma campanha você pode informar:

```json
{
  "name": "Empresas de Sinop - Suporte TI",
  "subject": "{{empresa}}, podemos melhorar sua TI?",
  "body": "Olá {{nome}}, atendemos empresas de {{cidade}} com suporte e infraestrutura de TI.",
  "target_city": "Sinop",
  "target_segment": null
}
```

Campos de personalização disponíveis:
- `{{empresa}}`
- `{{nome}}`
- `{{cidade}}`
- `{{segmento}}`

## Follow-up

Criar lembrete:

```http
POST /followups
```

Exemplo:

```json
{
  "contact_id": 1,
  "due_at": "2026-08-25T09:00:00",
  "channel": "email",
  "note": "Enviar segundo contato se não houver resposta"
}
```

Consultar pendências vencidas:

```http
GET /followups/due
```

## Segurança e LGPD

O sistema mantém o envio condicionado ao consentimento registrado e respeita contatos descadastrados. Não use listas obtidas de forma irregular nem faça disparos indiscriminados.

Credenciais reais nunca devem entrar no Git. Use `.env` local e mantenha apenas `.env.example` versionado.

## Roadmap V0.3+
1. Autenticação e usuários
2. Alembic para migrations
3. Worker Celery para filas e agendamento real
4. Recebimento e classificação de respostas de e-mail
5. Follow-up automático condicionado à ausência de resposta
6. Templates comerciais reutilizáveis
7. Pontuação automática de leads
8. Integração WhatsApp Business API
9. Instagram/Facebook via Meta API
10. IA para criação e personalização de conteúdo
11. Landing pages e formulários
12. Métricas de abertura, clique, resposta e conversão
