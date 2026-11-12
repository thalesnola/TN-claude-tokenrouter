#!/usr/bin/env python3
"""Impede que a versao do plugin ANDE PARA TRAS.

POR QUE ISTO EXISTE (medido em 31/08/2026):
uma sessao concorrente escreveu `1.7.2` por cima de `1.9.1` no `plugin.json`.
Ninguem errou de proposito -- ela partiu de um estado anterior do arquivo e nao
viu que a versao ja havia avancado. O conteudo dos commits sobreviveu; o que se
perdeu foi a monotonia do numero, e **ninguem audita isso**. Quem puxa o plugin
recebe uma versao menor e o CLI nao ve motivo para atualizar.

⚠️ A comparacao e NUMERICA, campo a campo. Comparar como texto e o proprio bug:
"1.9.1" > "1.10.0" em ordem alfabetica, e 1.10.0 e a maior das duas.

Dois modos, porque uma barreira so tem furo:

  pre-commit  compara o plugin.json STAGED contra o do HEAD.
              Fecha: edicao distraida indo ao historico.
  pre-push    compara o plugin.json do que SOBE contra o do remoto.
              Fecha: commit feito com --no-verify, ou em clone sem hook.

Sai 0 (segue), 1 (bloqueia).
"""
import json
import subprocess
import sys

ARQ = ".claude-plugin/plugin.json"


def _git(*args, entrada=None):
    r = subprocess.run(["git", *args], stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, input=entrada)
    return r.returncode, r.stdout.decode("utf-8", "replace")


def versao_em(rev):
    """Versao do plugin.json numa revisao. None se o arquivo nao existe la."""
    cod, saida = _git("show", f"{rev}:{ARQ}")
    if cod != 0:
        return None
    return _ler(saida, f"revisao {rev[:8]}")


def versao_staged():
    """Versao do plugin.json como esta no INDEX (o que vai ao commit)."""
    cod, saida = _git("show", f":{ARQ}")
    if cod != 0:
        return None
    return _ler(saida, "conteudo staged")


def _ler(texto, origem):
    try:
        v = json.loads(texto)["version"]
    except Exception as e:
        print(f"[versao] {ARQ} ilegivel em {origem}: {e}", file=sys.stderr)
        sys.exit(1)
    return v


def tupla(v):
    """'1.10.0' -> (1, 10, 0). Parte nao numerica vira -1, o que a ordena antes."""
    saida = []
    for p in str(v).split("."):
        try:
            saida.append(int(p))
        except ValueError:
            saida.append(-1)
    while len(saida) < 3:
        saida.append(0)
    return tuple(saida)


def barra(nova, antiga, contexto):
    print(f"\n[versao] BLOQUEADO: a versao do plugin andaria para tras.",
          file=sys.stderr)
    print(f"         {contexto}", file=sys.stderr)
    print(f"         atual : {antiga}", file=sys.stderr)
    print(f"         sua    : {nova}", file=sys.stderr)
    print(f"\n  Isso costuma significar que voce partiu de um {ARQ} desatualizado:",
          file=sys.stderr)
    print("  outra sessao ja subiu a versao. Puxe, funda, e suba a partir da maior.",
          file=sys.stderr)
    print(f"\n  Conferir:  git show HEAD:{ARQ} | grep version\n", file=sys.stderr)
    return 1


def modo_pre_commit():
    cod, _ = _git("rev-parse", "--verify", "HEAD")
    if cod != 0:
        return 0                      # primeiro commit do repo
    nova = versao_staged()
    if nova is None:
        return 0                      # plugin.json nao esta no commit
    antiga = versao_em("HEAD")
    if antiga is None:
        return 0                      # arquivo nasce neste commit
    if tupla(nova) < tupla(antiga):
        return barra(nova, antiga, "comparando o commit contra o HEAD")
    return 0


def modo_pre_push():
    zeros = "0" * 40
    problemas = 0
    for linha in sys.stdin.read().splitlines():
        campos = linha.split()
        if len(campos) < 4:
            continue
        _, sha_local, _, sha_remoto = campos[:4]
        if sha_local.strip("0") == "":
            continue                  # exclusao de branch
        if sha_remoto == zeros:
            continue                  # branch nova: nao ha com o que comparar
        nova = versao_em(sha_local)
        antiga = versao_em(sha_remoto)
        if nova is None or antiga is None:
            continue
        if tupla(nova) < tupla(antiga):
            problemas |= barra(nova, antiga,
                               f"comparando {sha_local[:8]} contra o remoto {sha_remoto[:8]}")
    return problemas


if __name__ == "__main__":
    modo = sys.argv[1] if len(sys.argv) > 1 else "pre-commit"
    sys.exit(modo_pre_push() if modo == "pre-push" else modo_pre_commit())
