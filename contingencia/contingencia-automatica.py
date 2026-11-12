#!/usr/bin/env python3
"""Hook StopFailure: quando o crédito/limite do Claude acaba, abre `claude-local` (Ollama) sozinho.

Sem nuvem de terceiros (decidido em 24/10/2026): o destino é sempre o Ollama local, na mesma
conversa (`claude-local -Sessao <id>`, na pasta onde ela nasceu). Dispara só em fim de crédito:
billing_error sempre; rate_limit apenas quando a mensagem é de limite de uso ("You've hit
your…", "usage limit") — 429 passageiro e "high load" não. Uma vez por sessão. Grava
~/.claude/ollama-pendente.json para o hook SessionStart mandar revisar o trabalho na volta.

Teste sem abrir janela:  CONTINGENCIA_DRY_RUN=1 python contingencia-automatica.py < evento.json
Autoteste das regras:    python contingencia-automatica.py --teste
"""
import datetime
import json
import os
import re
import subprocess
import sys
from pathlib import Path

# Windows: stdout de hook chega em cp1252; sem isto o "→" do systemMessage derruba o print final.
for _fluxo in (sys.stdout, sys.stderr):
    try:
        _fluxo.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

CLAUDE = Path.home() / ".claude"
PASTA = CLAUDE / "contingencia"
MARCADOR = CLAUDE / "ollama-pendente.json"
LIMITE_DE_USO = re.compile(r"hit your|usage limit|limit reached|resets? ", re.I)


def e_fim_de_credito(ev):
    erro = ev.get("error", "")
    if erro == "billing_error":
        return True
    texto = f"{ev.get('error_details', '')} {ev.get('last_assistant_message', '')}"
    return erro == "rate_limit" and bool(LIMITE_DE_USO.search(texto)) and "high load" not in texto


def cwd_de_origem(transcricao_txt, padrao):
    """Diretório em que a sessão NASCEU (primeiro `cwd` da transcrição). O `cwd` do evento é o
    atual: depois de um `cd` ele aponta para outra pasta e o CLI não acha a conversa
    ("No conversation found to continue" — medido em 23/09/2026)."""
    for linha in transcricao_txt.splitlines():
        try:
            c = json.loads(linha).get("cwd")
        except (ValueError, AttributeError):
            continue
        if c:
            return c
    return padrao


def ambiente_limpo():
    """Sem as variáveis do processo pai: herdadas do app desktop, CLAUDE_CODE_CHILD_SESSION desliga a
    gravação da transcrição e CLAUDE_CODE_SDK_HAS_HOST_AUTH_REFRESH faz o CLI pedir auth ao app —
    cuja conta é justamente a esgotada (medido em 23/09/2026)."""
    return {k: v for k, v in os.environ.items()
            if not k.upper().startswith(("CLAUDE", "ANTHROPIC_"))}


def abrir_janela(cwd, comando):
    env = ambiente_limpo()
    if os.environ.get("CONTINGENCIA_DRY_RUN"):
        print(f"[dry-run] cwd={cwd} comando={comando}", file=sys.stderr)
        return
    if os.name == "nt":
        subprocess.Popen(["pwsh", "-NoExit", "-Command", comando], cwd=cwd, env=env,
                         creationflags=subprocess.CREATE_NEW_CONSOLE)
    else:
        script = f"cd '{cwd}'; {comando}".replace("\\", "\\\\").replace('"', '\\"')
        subprocess.Popen(["osascript", "-e", f'tell application "Terminal" to do script "{script}"'])


def main():
    ev = json.load(sys.stdin)
    if not e_fim_de_credito(ev):
        return
    sessao = ev.get("session_id", "?")
    PASTA.mkdir(parents=True, exist_ok=True)
    trava = PASTA / f"{sessao}.acionada"
    if trava.exists():
        return
    trava.touch()

    cwd = ev.get("cwd") or os.getcwd()
    try:
        transcricao = Path(ev.get("transcript_path", "")).read_text(encoding="utf-8", errors="replace")
    except Exception:
        transcricao = ""

    retomar = f" -Sessao {sessao}" if re.fullmatch(r"[0-9a-fA-F-]{36}", sessao) else ""
    abrir_janela(cwd_de_origem(transcricao, cwd), f"claude-local{retomar}")
    # claude-local grava o marcador ele mesmo; aqui só garante o registro da primeira queda.
    if not os.environ.get("CONTINGENCIA_DRY_RUN") and not MARCADOR.exists():
        MARCADOR.write_text(json.dumps({"inicio": datetime.datetime.now().astimezone().isoformat(),
                                        "diretorio": cwd, "executor": "ollama"}), encoding="utf-8")
    print(json.dumps({"systemMessage": f"[contingência] crédito esgotado ({ev.get('error')}) → Ollama local. "
                                       "Janela aberta; o Claude revisa o trabalho na volta."},
                     ensure_ascii=False))


def teste():
    assert e_fim_de_credito({"error": "billing_error"})
    assert e_fim_de_credito({"error": "rate_limit", "error_details": "You've hit your limit"})
    assert not e_fim_de_credito({"error": "rate_limit", "error_details": "high load, retry"})
    assert not e_fim_de_credito({"error": "server_error"})
    assert cwd_de_origem('{"cwd": "C:/a"}\n{"cwd": "C:/b"}', "x") == "C:/a"
    assert cwd_de_origem("", "x") == "x"
    print("ok")


if __name__ == "__main__":
    teste() if "--teste" in sys.argv else main()
