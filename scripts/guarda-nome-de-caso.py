#!/usr/bin/env python3
"""pre-commit: barra linha adicionada que cita o nome de uma pasta de caso (subpastas de Casos).

O auditor do ACERVO acha identificador por FORMA (CPF, IPL, telefone); nome de operação não tem
forma e passou num commit deste repo em 23/09/2026 (histórico teve de ser reescrito).

Instalar uma vez por clone:  python scripts/guarda-nome-de-caso.py --instalar
"""
import re
import subprocess
import sys
from pathlib import Path

RAIZES = [Path("C:/Casos"), Path.home() / "Casos"]


def nomes_de_casos():
    return {d.name for r in RAIZES if r.is_dir() for d in r.iterdir() if d.is_dir() and len(d.name) >= 4}


def achados(diff, nomes):
    rx = [re.compile(rf"\b{re.escape(n)}\b", re.I) for n in nomes]
    return [l for l in diff.splitlines()
            if l.startswith("+") and not l.startswith("+++") and any(r.search(l) for r in rx)]


def instalar():
    git = Path(subprocess.run(["git", "rev-parse", "--git-dir"], capture_output=True, text=True).stdout.strip())
    hook = git / "hooks" / "pre-commit"
    if hook.exists() and "guarda-nome-de-caso" not in hook.read_text(encoding="utf-8", errors="replace"):
        sys.exit(f"{hook} já existe e é de outra origem; não sobrescrevo.")
    hook.write_text('#!/bin/sh\nexec python "$(git rev-parse --show-toplevel)/scripts/guarda-nome-de-caso.py"\n',
                    encoding="utf-8", newline="\n")
    hook.chmod(0o755)
    print(f"instalado: {hook}")


def main():
    diff = subprocess.run(["git", "diff", "--cached", "-U0"], capture_output=True, text=True,
                          encoding="utf-8", errors="replace").stdout
    ruins = achados(diff, nomes_de_casos())
    if ruins:
        print("[guarda] commit barrado: nome de caso nas linhas adicionadas:", file=sys.stderr)
        for l in ruins[:20]:
            print("  " + l[:160], file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    if "--teste" in sys.argv:
        assert achados("+++ b/x\n+sessão do caso Caixote\n-Caixote\n+caixotes", {"CAIXOTE"}) == ["+sessão do caso Caixote"]
        print("ok")
    elif "--instalar" in sys.argv:
        instalar()
    else:
        main()
