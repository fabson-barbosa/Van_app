"""Processa notificações agendadas vencidas, tenant por tenant (Bloco B3).

Uso:
    cd backend
    python scripts/processar_notificacoes.py

Pensado para ser chamado periodicamente por algo externo (cron, Cloud
Scheduler batendo um Cloud Run Job) — a cadência em si é decisão de deploy,
fora do escopo deste script. Idempotente: rodar de novo (ou em paralelo) não
duplica envio (ver `app/services/agendador.py`).

Conecta como `vaivem_app` (mesmas credenciais da aplicação, via `.env`) — RLS
continua fail-closed. Como o job precisa varrer TODOS os tenants (não só um),
itera tenant por tenant, setando `app.tenant_id` com escopo de TRANSAÇÃO
(`set_config(..., true)`), igual `get_tenant_db` faz por request
(`app/api/deps.py`) — inclusive o mesmo listener `after_begin`, necessário
porque `processar_notificacoes_pendentes` comita uma transação por linha
processada; sem reaplicar o tenant a cada nova transação, a 2ª linha em
diante do mesmo tenant cairia sem `app.tenant_id` setado (RLS fail-closed
faria o processamento simplesmente não achar mais nada daquele tenant).
`tenants` em si não tem RLS (é a raiz da hierarquia, sem `tenant_id` próprio)
— dá pra listar todos sem setar nada.
"""
import datetime

from sqlalchemy import event, select, text

from app.core.db import SessionLocal
from app.models.tenant import Tenant
from app.services.agendador import processar_notificacoes_pendentes
from app.services.notificacoes import StubFCMSender


def _processar_tenant(tenant_id, agora, sender) -> int:
    db = SessionLocal()
    tenant_id_str = str(tenant_id)

    def _set_tenant_on_begin(session, transaction, connection, _tid=tenant_id_str):
        connection.execute(text("SELECT set_config('app.tenant_id', :tid, true)"), {"tid": _tid})

    event.listen(db, "after_begin", _set_tenant_on_begin)
    try:
        return processar_notificacoes_pendentes(db, agora, sender)
    finally:
        event.remove(db, "after_begin", _set_tenant_on_begin)
        db.close()


def main() -> None:
    agora = datetime.datetime.now(datetime.timezone.utc)
    sender = StubFCMSender()  # troque por um FCMSender real quando a integração existir

    db = SessionLocal()
    try:
        tenant_ids = [t.id for t in db.scalars(select(Tenant))]
    finally:
        db.close()

    total = sum(_processar_tenant(tenant_id, agora, sender) for tenant_id in tenant_ids)
    print(f"Processadas {total} notificações vencidas em {len(tenant_ids)} tenant(s).")


if __name__ == "__main__":
    main()
