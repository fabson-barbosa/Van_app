"""Reconciliação de relógio — app do Motorista offline (Bloco B4).

Lógica pura (sem sessão de banco, sem HTTP) — mesma filosofia de
`trip_state_machine.py`/`leg_duration.py`.

Problema: o relógio do aparelho pode divergir do relógio do servidor (deriva
de hardware, fuso mal configurado, usuário mexendo na hora). Sem correção,
`chegou_em`/`checkin_em` herdariam esse erro diretamente — e é exatamente
sobre a DIFERENÇA entre esses timestamps que o motor de tempos do B3 (trajeto,
dwell, EWMA de `leg_duration`) faz toda a sua aritmética.

Solução: o app envia, junto de cada evento, `device_timestamp` (relógio do
aparelho no momento do toque) e `device_enviado_em` (relógio do aparelho no
momento do POST — pode ser bem depois, se o evento ficou na fila offline).
O servidor calcula `offset = agora_servidor - device_enviado_em` e aplica esse
MESMO offset a `device_timestamp`: `ocorrido_em = device_timestamp + offset`.
Isso cancela a deriva e preserva exatamente o intervalo que o aparelho mediu
entre o toque e o envio — é esse intervalo, não o valor absoluto, que importa
para o motor de tempos.

`confiavel=False` sinaliza ao chamador (`app/services/pos_evento.py`) para
não gravar amostra de `leg_duration` a partir deste evento — um instante que
caiu no relógio do servidor por falta de dado do aparelho (ou por um offset
absurdo) não é uma medida real de trajeto, e contaminaria o EWMA.
"""
from __future__ import annotations

import datetime
from dataclasses import dataclass

OFFSET_MAXIMO = datetime.timedelta(hours=24)


@dataclass(frozen=True)
class InstanteReconciliado:
    ocorrido_em: datetime.datetime
    confiavel: bool


def reconciliar(
    *,
    device_timestamp: datetime.datetime | None,
    device_enviado_em: datetime.datetime | None,
    agora_servidor: datetime.datetime,
    nao_antes_de: datetime.datetime | None = None,
) -> InstanteReconciliado:
    """Calcula o instante reconciliado de um evento.

    Cai em `agora_servidor` (relógio do servidor, comportamento anterior ao
    B4) sempre que os dados do aparelho estão ausentes, o offset implícito
    estoura `OFFSET_MAXIMO`, ou o resultado violaria uma das duas garantias
    de sanidade: nunca no futuro em relação ao servidor, nunca antes do
    início da viagem (`nao_antes_de`, quando informado).
    """
    if device_timestamp is None or device_enviado_em is None:
        return InstanteReconciliado(ocorrido_em=agora_servidor, confiavel=False)

    offset = agora_servidor - device_enviado_em
    if abs(offset) > OFFSET_MAXIMO:
        return InstanteReconciliado(ocorrido_em=agora_servidor, confiavel=False)

    ocorrido_em = device_timestamp + offset

    if ocorrido_em > agora_servidor:
        return InstanteReconciliado(ocorrido_em=agora_servidor, confiavel=False)
    if nao_antes_de is not None and ocorrido_em < nao_antes_de:
        return InstanteReconciliado(ocorrido_em=agora_servidor, confiavel=False)

    return InstanteReconciliado(ocorrido_em=ocorrido_em, confiavel=True)
