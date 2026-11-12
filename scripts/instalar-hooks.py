#!/usr/bin/env python3
"""Instala os hooks de git do token-router. Rodar UMA VEZ por clone.

⚠️ `.git/hooks/` NAO e versionado. Clone novo nasce sem nenhum hook, e nada
avisa -- o commit passa, a versao regride, e ninguem fica sabendo. Mesma
armadilha ja registrada para os hooks de sigilo do Segundo Cerebro.

Instala duas barreiras, porque uma so tem furo:
  pre-commit  -> compara o plugin.json staged contra o HEAD
  pre-push    -> compara o que sobe contra o remoto (pega commit com --no-verify)

Idempotente: reescreve os dois arquivos a cada execucao.
"""
import os
import stat
import subprocess
import sys

MOLDE = """#!/bin/sh
# Gerado por scripts/instalar-hooks.py do token-router. Nao editar a mao.
exec python "$(git rev-parse --show-toplevel)/scripts/verificar-versao.py" {modo} "$@"
"""


def main():
    r = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if r.returncode != 0:
        sys.exit("Rode de dentro do repositorio do plugin.")
    raiz = r.stdout.decode().strip()

    if not os.path.exists(os.path.join(raiz, "scripts", "verificar-versao.py")):
        sys.exit("Nao achei scripts/verificar-versao.py em " + raiz)

    alvo = os.path.join(raiz, ".git", "hooks")
    os.makedirs(alvo, exist_ok=True)

    for modo in ("pre-commit", "pre-push"):
        cam = os.path.join(alvo, modo)
        with open(cam, "w", newline="\n", encoding="utf-8") as f:
            f.write(MOLDE.format(modo=modo))
        # No Windows o git roda o hook via sh e ignora permissao. No macOS/Linux,
        # hook sem bit de execucao e ignorado EM SILENCIO -- o commit passa.
        os.chmod(cam, os.stat(cam).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        exec_ok = bool(os.stat(cam).st_mode & stat.S_IXUSR)
        if sys.platform.startswith("win"):
            nota = "bit de execucao irrelevante no Windows (git roda o hook via sh)"
        elif exec_ok:
            nota = "executavel: sim"
        else:
            nota = "executavel: NAO -- CORRIGIR; sem o bit o hook e ignorado EM SILENCIO"
        print("instalado: " + cam)
        print("           " + nota)

    print("\nTestar sem commitar:")
    print("  python scripts/verificar-versao.py pre-commit")


if __name__ == "__main__":
    main()
