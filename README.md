# Norte MT Marketing Hub

Plataforma própria de CRM, prospecção e automação de divulgação da Norte MT Sistemas.

## Versão atual: V0.3

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
- Leitura de respostas por IMAP
- Caixa de entrada interna para respostas recebidas
- Associação automática da resposta ao lead pelo endereço de e-mail
- Classificação automática de intenção comercial
- Atualização automática do funil conforme a resposta
- Sugestão de resposta comercial
- Aprovação manual antes de qualquer resposta ser enviada
- Dashboard com métricas, funil e respostas novas
- Docker Compose com PostgreSQL + Redis
- Compatibilidade automática com banco criado nas versões anteriores

## Stack
- Python / FastAPI
- SQLAlchemy
- PostgreSQL 17
- Redis
- Docker Compose
- SMTP para envio
- IMAP para leitura de respostas

## Rodar

```bash
docker compose up --build
```

Acesse:
- Dashboard: http://localhost:8000
- Swagger: http://localhost:8000/docs
- Health: http://localhost:8000/health

## Modo seguro

Enquanto `SMTP_HOST` estiver vazio, nenhum e-mail real é enviado. As campanhas e respostas aprovadas ficam em `dry-run`.

A V0.3 também **não envia respostas recebidas automaticamente**. O sistema analisa e sugere uma resposta, mas o envio exige chamada explícita do endpoint de aprovação.

## Configurar envio SMTP

Copie `.env.example` para `.env` e preencha apenas localmente:

```env
SMTP_HOST=smtp.seu-provedor.com
SMTP_PORT=587
SMTP_USER=contato@seudominio.com.br
SMTP_PASSWORD=SUA_SENHA_OU_APP_PASSWORD
SMTP_FROM=contato@seudominio.com.br
```

Nunca envie `.env` real para o GitHub.

## Configurar leitura IMAP

No mesmo `.env`:

```env
IMAP_HOST=imap.seu-provedor.com
IMAP_PORT=993
IMAP_USER=contato@seudominio.com.br
IMAP_PASSWORD=SUA_SENHA_OU_APP_PASSWORD
IMAP_MAILBOX=INBOX
```

Depois reinicie:

```bash
docker compose up --build
```

Sincronize mensagens não lidas:

```http
POST /inbox/sync
```

Se o IMAP não estiver configurado, o endpoint informa `configured: false` sem quebrar a aplicação.

## Testar a inteligência sem e-mail real

Você pode simular uma resposta diretamente pelo Swagger:

```http
POST /inbox/replies
```

Exemplo:

```json
{
  "sender_email": "cliente@empresa.com.br",
  "sender_name": "João",
  "subject": "Re: Suporte de TI",
  "body": "Tenho interesse. Você consegue me passar um valor?"
}
```

O sistema:
1. procura o remetente no CRM;
2. classifica a intenção;
3. atualiza o funil quando aplicável;
4. registra a mensagem na caixa de entrada;
5. cria uma resposta sugerida.

## Intenções reconhecidas

- `interessado`
- `preco`
- `reuniao`
- `duvida`
- `nao_interessado`
- `descadastro`
- `outro`

Respostas de `descadastro` atualizam o contato para não receber novas campanhas. Respostas de `nao_interessado` e `descadastro` não recebem sugestão automática de continuidade comercial.

## Caixa de entrada

Consultar tudo:

```http
GET /inbox
```

Apenas novas:

```http
GET /inbox?status=new
```

Filtrar por intenção:

```http
GET /inbox?intent=preco
```

Marcar como revisada:

```http
PATCH /inbox/{id}/reviewed
```

Ignorar:

```http
PATCH /inbox/{id}/ignore
```

## Aprovar e enviar uma resposta

Depois de revisar `suggested_reply`:

```http
POST /inbox/{id}/approve-send
```

Sem SMTP configurado, o endpoint retorna `dry_run: true` e não envia nada. Com SMTP configurado, o e-mail é enviado e a mensagem passa para `replied`.

## Funil de leads

```text
novo -> contatado -> interessado -> proposta -> cliente
                                      \
                                       -> perdido
```

Quando chega uma resposta comercial positiva, leads `novo` ou `contatado` podem avançar automaticamente para `interessado`.

## Importar empresas por CSV

Endpoint:

```http
POST /contacts/import-csv
```

O arquivo pode usar `,` ou `;` como separador.

Cabeçalhos aceitos:

```text
empresa,nome,email,telefone,cidade,segmento,origem,consentimento
```

Existe um modelo em `examples/contatos.csv`.

## Campanhas segmentadas

Exemplo:

```json
{
  "name": "Empresas de Sinop - Suporte TI",
  "subject": "{{empresa}}, podemos melhorar sua TI?",
  "body": "Olá {{nome}}, atendemos empresas de {{cidade}} com suporte e infraestrutura de TI.",
  "target_city": "Sinop",
  "target_segment": null
}
```

Campos de personalização:
- `{{empresa}}`
- `{{nome}}`
- `{{cidade}}`
- `{{segmento}}`

## Follow-up

Criar lembrete:

```http
POST /followups
```

Consultar vencidos:

```http
GET /followups/due
```

## Segurança e LGPD

Use somente contatos obtidos de forma legítima. Respeite descadastro, consentimento e preferência de comunicação.

O projeto mantém credenciais fora do repositório e bloqueia continuidade automática para respostas de descadastro ou falta de interesse.

## Próximos passos V0.4+
1. Autenticação e usuários
2. Alembic para migrations
3. Worker Celery para sincronização e filas agendadas
4. Página visual de Inbox/CRM sem depender do Swagger
5. Edição da resposta sugerida antes do envio
6. Integração com um LLM para respostas realmente contextuais
7. Pontuação automática de leads
8. Follow-up automático condicionado à ausência de resposta
9. Templates comerciais reutilizáveis
10. WhatsApp Business API
11. Instagram/Facebook via Meta API
12. Landing pages e métricas de abertura, clique, resposta e conversão
