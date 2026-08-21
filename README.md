# Norte MT Marketing Hub

MVP para centralizar divulgação da Norte MT Sistemas.

## O que já existe
- CRM de contatos/empresas
- Cadastro de campanhas
- Disparo de e-mail com modo seguro `dry-run`
- Registro de envios
- Controle de consentimento/descadastro
- Dashboard simples
- Docker Compose com PostgreSQL + Redis

## Rodar
```bash
docker compose up --build
```
Acesse:
- Dashboard: http://localhost:8000
- Swagger: http://localhost:8000/docs

## Teste sem enviar e-mail real
Enquanto `SMTP_HOST` estiver vazio, o sistema registra o envio como `dry-run`.

## Roadmap
1. Importação CSV/XLSX de empresas
2. Segmentação por cidade/ramo
3. Modelos de campanhas
4. Agendamento e follow-up
5. Integração com provedor de e-mail
6. Instagram/Facebook via Meta API
7. WhatsApp Business API
8. Pipeline de conteúdo com IA
9. Landing pages e formulários
10. Métricas: abertura, clique, resposta, lead e conversão

## Segurança e LGPD
Use listas legítimas, registre consentimento quando necessário, ofereça descadastro e evite disparos indiscriminados.
