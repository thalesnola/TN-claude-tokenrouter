#!/usr/bin/env python3
"""Detecta a máquina atual e imprime seu perfil de roteamento em Markdown."""

import json
import os
import shutil
import socket
import subprocess
import sys
from pathlib import Path

for _fluxo in (sys.stdout, sys.stderr):
    try:
        _fluxo.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

RAIZ = Path(__file__).parent.parent
MAQUINAS = RAIZ / "maquinas"
CATALOGO = MAQUINAS / "maquinas.json"


def detectar_maquina(hostname: str, plataforma: str, ler_vram_mib) -> tuple[str | None, str | None]:
    """Retorna o primeiro perfil existente e a regra que o identificou."""
    dados = json.loads(CATALOGO.read_text(encoding="utf-8"))
    manual = os.environ.get("TOKEN_ROUTER_MAQUINA")
    if manual and (MAQUINAS / f"{manual}.md").is_file():
        return manual, "variável"

    hostnames = {chave.casefold(): valor for chave, valor in dados["hostnames"].items()}
    ident = hostnames.get(hostname.casefold())
    if ident and (MAQUINAS / f"{ident}.md").is_file():
        return ident, "hostname"

    if plataforma == "darwin" and (MAQUINAS / "personal-device.md").is_file():
        return "personal-device", "darwin"
    if plataforma == "win32":
        vram = ler_vram_mib()
        if vram is not None:
            ident = "workstation-windows" if vram >= 12000 else (
                "workstation-windows" if vram > 0 else None)
            if ident and (MAQUINAS / f"{ident}.md").is_file():
                return ident, "nvidia-smi"
    return None, None


def ler_vram_mib() -> int | None:
    """Consulta a VRAM da primeira GPU NVIDIA, quando disponível."""
    executavel = shutil.which("nvidia-smi")
    if not executavel:
        return None
    try:
        resultado = subprocess.run(
            [executavel, "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=3,
        )
        if resultado.returncode:
            return None
        return int(resultado.stdout.splitlines()[0].strip())
    except (OSError, ValueError, IndexError, subprocess.TimeoutExpired):
        return None


def main() -> None:
    """Imprime o perfil selecionado ou uma orientação curta para fixá-lo."""
    hostname = socket.gethostname()
    ident, regra = detectar_maquina(hostname, sys.platform, ler_vram_mib)
    if ident is None:
        dados = json.loads(CATALOGO.read_text(encoding="utf-8"))
        validos = ", ".join(dados["nomes"])
        print(f"Máquina não reconhecida (hostname: {hostname}). Defina "
              f"TOKEN_ROUTER_MAQUINA=<id> como variável de ambiente de usuário. IDs: {validos}.")
        return
    perfil = (MAQUINAS / f"{ident}.md").read_text(encoding="utf-8")
    print(f"<!-- token-router: perfil {ident}, detectado por {regra} -->")
    sys.stdout.write(perfil)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
