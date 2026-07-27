"""
VaiVem API — ponto de entrada da aplicação FastAPI.

Sprint 0: fundamentos (config, banco + RLS multi-tenant, auth/RBAC básico).
Sprint 1: cadastros e multi-tenancy — CRUD de veículos, rotas/paradas,
alunos/responsáveis e onboarding do tenant (DPA/LGPD).
Bloco B2: motor de viagem — máquina de estados do aluno, ciclo de vida da
viagem e varredura final (CLAUDE.md §4/§7).
"""
from fastapi import FastAPI

from app.api import alunos, auth, rotas, tenants, veiculos, viagens

app = FastAPI(
    title="VaiVem API",
    description="API da plataforma de gestão de transporte escolar.",
    version="0.1.0",
)

app.include_router(auth.router)
app.include_router(veiculos.router)
app.include_router(rotas.router)
app.include_router(alunos.router)
app.include_router(tenants.router)
app.include_router(viagens.router)


@app.get("/health", tags=["infra"])
def health_check():
    """Verificação simples de disponibilidade do serviço."""
    return {"status": "ok", "service": "vaivem-api", "version": "0.1.0"}


@app.get("/", tags=["infra"])
def root():
    return {"message": "VaiVem API. Veja /docs para a documentação interativa."}
