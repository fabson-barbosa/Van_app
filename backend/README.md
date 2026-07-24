# VaiVem — Backend (API)

API FastAPI da plataforma. Scaffold inicial.

## Rodar localmente

```bash
cp .env.example .env        # preencha os valores
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Acesse `http://localhost:8000/docs` para a documentação interativa (Swagger).

## Estrutura prevista (Fase 1)

```
app/
├── main.py            # entrypoint (pronto)
├── core/              # config, segurança, RLS por tenant
├── models/            # SQLAlchemy + PostGIS
├── schemas/           # Pydantic
├── api/               # rotas: tenants, routes, tracking, students...
├── services/          # motor de ETA, notificações, pagamentos
└── workers/           # filas / tarefas assíncronas
```
