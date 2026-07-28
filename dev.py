#!/usr/bin/env python
"""Sobe o ambiente de desenvolvimento inteiro do VaiVem com um comando.

    python dev.py

Faz, em ordem:

1.  `docker compose up -d --wait` (Postgres+PostGIS e Redis)
2.  `alembic upgrade head` — como **owner** (`vaivem`), nunca como `vaivem_app`,
    que é o role da aplicação e não tem privilégio de DDL (ver PROGRESSO.md, gate
    do B1)
3.  `scripts/seed_demo.py` — idempotente; garante as viagens `planejada` de HOJE
4.  API (`uvicorn --host 0.0.0.0`), Metro/Expo (`--host lan`) e o processador de
    notificações agendadas, os três em paralelo, com log prefixado

Ctrl+C derruba os três (os containers ficam de pé — `docker compose down` é
decisão sua).

O processador de notificações roda em laço porque o aviso de *preparo* é
agendado no banco (B3) e só sai quando alguém processa a fila; `chegada` e
`iminência` saem inline no próprio request e não dependem dele.

Flags úteis:

    python dev.py --sem-docker --sem-migrations --sem-seed   # só sobe os processos
    python dev.py --sem-mobile                               # só backend
    python dev.py --corrigir-env                             # reescreve mobile/.env se o IP da LAN mudou
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
BACKEND = RAIZ / "backend"
MOBILE = RAIZ / "mobile"
ENV_MOBILE = MOBILE / ".env"

# Migrations rodam como owner. A aplicação continua conectando como `vaivem_app`
# (backend/.env) — é o que mantém os testes de RLS honestos, já que todo
# superuser tem BYPASSRLS.
OWNER_DATABASE_URL = os.environ.get(
    "VAIVEM_OWNER_DATABASE_URL",
    "postgresql+psycopg://vaivem:vaivem@localhost:5432/vaivem",
)

PORTA_API = 8000
PORTA_METRO = 8081

_CORES = {"api": "\033[36m", "metro": "\033[35m", "push": "\033[33m"}
_RESET = "\033[0m"
_USAR_COR = sys.stdout.isatty() and os.name != "nt" or os.environ.get("WT_SESSION")


def _colorir(nome: str, texto: str) -> str:
    if not _USAR_COR:
        return texto
    return f"{_CORES.get(nome, '')}{texto}{_RESET}"


def passo(msg: str) -> None:
    print(f"\n\033[1m==> {msg}\033[0m" if _USAR_COR else f"\n==> {msg}", flush=True)


def aviso(msg: str) -> None:
    print(f"\033[33m!! {msg}\033[0m" if _USAR_COR else f"!! {msg}", flush=True)


def ip_lan() -> str:
    """IP do adaptador que tem a rota default.

    Não usa `Get-NetIPAddress`/`ipconfig`: em máquina com WSL2 eles listam o
    adaptador virtual `vEthernet (WSL ...)` junto com o físico, e só o físico
    está na mesma rede do celular (PROGRESSO.md, B4). O truque do socket UDP
    devolve exatamente a interface de saída — nenhum pacote é enviado.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def ambiente_backend() -> dict[str, str]:
    env = os.environ.copy()
    # `python scripts/x.py` põe scripts/ no sys.path, não backend/ — sem isso o
    # import de `app.core` falha.
    env["PYTHONPATH"] = str(BACKEND)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUNBUFFERED"] = "1"
    return env


def rodar(cmd: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> None:
    """Roda um comando até o fim e aborta o script se ele falhar."""
    print(f"    $ {' '.join(cmd)}", flush=True)
    resultado = subprocess.run(cmd, cwd=str(cwd), env=env)
    if resultado.returncode != 0:
        sys.exit(f"\nFalhou: {' '.join(cmd)} (código {resultado.returncode})")


def esperar_http(url: str, *, rotulo: str, timeout: float = 180.0) -> bool:
    inicio = time.monotonic()
    while time.monotonic() - inicio < timeout:
        try:
            with urllib.request.urlopen(url, timeout=3):
                return True
        except urllib.error.HTTPError:
            return True  # respondeu (mesmo que 4xx) — a porta está de pé
        except (urllib.error.URLError, OSError, TimeoutError):
            time.sleep(1.5)
    aviso(f"{rotulo} não respondeu em {timeout:.0f}s ({url}) — veja o log acima")
    return False


class Servico:
    """Processo de longa duração com log prefixado e encerramento confiável."""

    def __init__(self, nome: str, cmd: list[str], cwd: Path, env: dict[str, str]):
        self.nome = nome
        self.cmd = cmd
        self.cwd = cwd
        self.env = env
        self.proc: subprocess.Popen[str] | None = None

    def iniciar(self) -> None:
        criacao = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
        self.proc = subprocess.Popen(
            self.cmd,
            cwd=str(self.cwd),
            env=self.env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            creationflags=criacao,
        )
        threading.Thread(target=self._bombear, daemon=True).start()

    def _bombear(self) -> None:
        assert self.proc and self.proc.stdout
        for linha in self.proc.stdout:
            print(_colorir(self.nome, f"[{self.nome}] ") + linha.rstrip(), flush=True)

    def encerrar(self) -> None:
        if not self.proc or self.proc.poll() is not None:
            return
        if os.name == "nt":
            # `npx expo` e `uvicorn` criam filhos; terminate() no pai deixaria
            # órfão segurando a porta. /T mata a árvore inteira.
            subprocess.run(
                ["taskkill", "/T", "/F", "/PID", str(self.proc.pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            self.proc.terminate()
        try:
            self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.proc.kill()


class Agendador(threading.Thread):
    """Chama `scripts/processar_notificacoes.py` em laço.

    O script é idempotente por desenho (B3: `FOR UPDATE SKIP LOCKED`, uma linha
    por transação), então repetir a chamada nunca duplica envio.
    """

    def __init__(self, intervalo: int, env: dict[str, str]):
        super().__init__(daemon=True)
        self.intervalo = intervalo
        self.env = env
        self.parar = threading.Event()

    def run(self) -> None:
        cmd = [sys.executable, "scripts/processar_notificacoes.py"]
        while not self.parar.is_set():
            try:
                r = subprocess.run(
                    cmd,
                    cwd=str(BACKEND),
                    env=self.env,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                )
                saida = (r.stdout or "").strip() or (r.stderr or "").strip()
                if saida:
                    for linha in saida.splitlines():
                        print(_colorir("push", "[push] ") + linha, flush=True)
            except Exception as exc:  # noqa: BLE001 — laço de dev não pode morrer
                print(_colorir("push", "[push] ") + f"erro: {exc}", flush=True)
            self.parar.wait(self.intervalo)


def conferir_env_mobile(ip: str, corrigir: bool) -> None:
    """O app aponta para o IP da LAN via EXPO_PUBLIC_API_BASE_URL.

    Num aparelho físico, `localhost`/`10.0.2.2` resolveriam para o próprio
    celular — o IP tem que ser o da máquina, e ele muda quando o DHCP renova.
    """
    esperado = f"http://{ip}:{PORTA_API}"
    if not ENV_MOBILE.exists():
        aviso(f"{ENV_MOBILE} não existe. Crie com: EXPO_PUBLIC_API_BASE_URL={esperado}")
        return

    conteudo = ENV_MOBILE.read_text(encoding="utf-8")
    achado = re.search(r"^EXPO_PUBLIC_API_BASE_URL=(.*)$", conteudo, re.MULTILINE)
    atual = achado.group(1).strip() if achado else None
    if atual == esperado:
        return

    if corrigir and achado:
        ENV_MOBILE.write_text(
            re.sub(
                r"^EXPO_PUBLIC_API_BASE_URL=.*$",
                f"EXPO_PUBLIC_API_BASE_URL={esperado}",
                conteudo,
                count=1,
                flags=re.MULTILINE,
            ),
            encoding="utf-8",
        )
        passo(f"mobile/.env atualizado: {atual} -> {esperado}")
        return

    aviso(
        f"mobile/.env aponta para {atual!r}, mas o IP desta máquina é {ip}.\n"
        f"   O app não vai achar a API. Rode com --corrigir-env, ou edite à mão:\n"
        f"   EXPO_PUBLIC_API_BASE_URL={esperado}"
    )


def main() -> int:
    p = argparse.ArgumentParser(description="Sobe o ambiente de dev do VaiVem.")
    p.add_argument("--sem-docker", action="store_true", help="não mexe nos containers")
    p.add_argument("--sem-migrations", action="store_true", help="pula alembic upgrade head")
    p.add_argument("--sem-seed", action="store_true", help="pula o seed de demonstração")
    p.add_argument("--sem-mobile", action="store_true", help="não sobe o Metro/Expo")
    p.add_argument("--sem-agendador", action="store_true", help="não processa notificações agendadas")
    p.add_argument("--corrigir-env", action="store_true", help="reescreve mobile/.env com o IP atual")
    p.add_argument("--intervalo-agendador", type=int, default=30, metavar="S")
    args = p.parse_args()

    ip = ip_lan()
    env_backend = ambiente_backend()

    if not args.sem_docker:
        passo("Subindo Postgres e Redis")
        rodar(["docker", "compose", "up", "-d", "--wait"], cwd=RAIZ)

    if not args.sem_migrations:
        passo("Migrations (como owner, não como vaivem_app)")
        env_owner = env_backend | {"DATABASE_URL": OWNER_DATABASE_URL}
        rodar([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=BACKEND, env=env_owner)

    if not args.sem_seed:
        passo("Seed (idempotente — garante as viagens de hoje)")
        rodar([sys.executable, "scripts/seed_demo.py"], cwd=BACKEND, env=env_backend)

    if not args.sem_mobile:
        conferir_env_mobile(ip, args.corrigir_env)

    servicos: list[Servico] = [
        Servico(
            "api",
            [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", str(PORTA_API)],
            BACKEND,
            env_backend,
        )
    ]

    if not args.sem_mobile:
        npx = shutil.which("npx") or ("npx.cmd" if os.name == "nt" else "npx")
        env_mobile = os.environ.copy()
        env_mobile["FORCE_COLOR"] = "0"
        servicos.append(Servico("metro", [npx, "expo", "start", "--host", "lan"], MOBILE, env_mobile))

    passo("Subindo os processos")
    for s in servicos:
        s.iniciar()

    agendador: Agendador | None = None
    if not args.sem_agendador:
        agendador = Agendador(args.intervalo_agendador, env_backend)
        agendador.start()

    esperar_http(f"http://{ip}:{PORTA_API}/docs", rotulo="API")
    if not args.sem_mobile:
        esperar_http(f"http://{ip}:{PORTA_METRO}/status", rotulo="Metro")

    print(
        f"""
{'=' * 62}
  API      http://{ip}:{PORTA_API}        (docs em /docs)
  Expo Go  exp://{ip}:{PORTA_METRO}

  Login (senha demo12345 para todos):
    motorista     motorista.centro@demo.vaivem.com.br
    responsavel   responsavel.alice@demo.vaivem.com.br
    admin         admin@demo.vaivem.com.br

  Ctrl+C encerra. Os containers seguem de pé.
{'=' * 62}
""",
        flush=True,
    )

    try:
        while True:
            for s in servicos:
                if s.proc and s.proc.poll() is not None:
                    aviso(f"'{s.nome}' morreu (código {s.proc.returncode}). Encerrando o resto.")
                    raise KeyboardInterrupt
            time.sleep(1)
    except KeyboardInterrupt:
        passo("Encerrando")
        if agendador:
            agendador.parar.set()
        for s in servicos:
            s.encerrar()

    return 0


if __name__ == "__main__":
    sys.exit(main())
