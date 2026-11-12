#!/usr/bin/env python3
"""Atualiza aplicativos vinculados ao token-router, se o usuário ligar o interruptor.

O hook apenas agenda a execução; --verificar consulta versões sem instalar nada.
"""
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

for _fluxo in (sys.stdout, sys.stderr):
    try:
        _fluxo.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

PASTA = Path.home() / ".claude" / "token-router"
ESTADO = PASTA / "autoatualizacao.json"
LOCK = PASTA / "autoatualizacao.lock"
LOG = PASTA / "autoatualizacao.log"
INTERVALO_H = 6
PACOTES_NPM = ("@qwen-code/qwen-code", "opencode-ai", "@deepseek-ai/dsh")
# O npm 11 pula os scripts de instalação fora desta lista e ainda sai com código 0. No Windows
# isso não mudou nenhum arquivo do DSH (medido em 04/11/2026, 0.2.1-rc.5), mas no Mac é o
# script do dsh-subprocess-local que devolve o bit de execução ao spawn-helper do node-pty.
SCRIPTS_NPM = {
    "@deepseek-ai/dsh": ("@deepseek-ai/dsh-subprocess-local", "koffi", "node-pty",
                         "@google/genai", "protobufjs"),
}
# id → trechos do CAMINHO do executável em uso (por caminho, não por nome).
# Ollama: o servidor sempre roda; em uso = modelo carregado.
WINGET = {
    "Ollama.Ollama": (),
}


def agora():
    return dt.datetime.now().astimezone()


def data(iso):
    return dt.datetime.fromisoformat(iso) if iso else None


def registrar(mensagem):
    PASTA.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(f"{agora().isoformat()} {mensagem}\n")


def ler_json(caminho, padrao):
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return padrao


def gravar_json(caminho, valor):
    PASTA.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(valor, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def comando(args, timeout=60):
    return subprocess.run(args, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=timeout)


def erro_curto(exc):
    return re.sub(r"\s+", " ", str(exc)).strip()[:160]


def resultado(app, antes=None, depois=None, motivo=None):
    if motivo:
        return f"{app}: pulado ({motivo})"
    return f"{app}: {antes} → {depois}" if antes != depois else f"{app}: em dia"


def versao_plugin():
    registro = ler_json(Path.home() / ".claude/plugins/installed_plugins.json", {})
    entradas = registro.get("plugins", {}).get("token-router@local-user-plugins")
    entrada = entradas[0] if isinstance(entradas, list) and entradas else entradas or {}
    return entrada.get("version", "?") if isinstance(entrada, dict) else "?"


def plugin(executar):
    app = "token-router"
    # Caminho completo: no Windows o `claude` do npm é `claude.cmd`, e o subprocess não acha
    # `.cmd` pelo nome curto (WinError 2, medido em 23/09/2026).
    claude = shutil.which("claude")
    if not claude:
        return resultado(app, motivo="claude ausente")
    antes = versao_plugin()
    if not executar:
        return resultado(app, motivo=f"versão {antes}; a remota só se vê atualizando o marketplace")
    for args in ((claude, "plugin", "marketplace", "update", "local-user-plugins"),
                 (claude, "plugin", "update", "token-router@local-user-plugins")):
        r = comando(list(args), 180)
        if r.returncode:
            raise RuntimeError(erro_curto(r.stderr or r.stdout or f"código {r.returncode}"))
    # Não remover caches antigos: a sessão aberta usa CLAUDE_PLUGIN_ROOT daquela versão.
    return resultado(app, antes, versao_plugin())


def scripts_pendentes(saida):
    return re.findall(r"allow-scripts\s+(\S+@\S+) \(", saida)


def instalar_npm(npm_bin, pacote):
    args = [npm_bin, "install", "-g"]
    if pacote in SCRIPTS_NPM:
        args.append("--allow-scripts=" + ",".join(SCRIPTS_NPM[pacote]))
    return comando([*args, f"{pacote}@latest"], 300)


def npm(executar):
    npm_bin = "npm.cmd" if os.name == "nt" else "npm"
    if not shutil.which(npm_bin):
        return [resultado("npm", motivo="não instalado")]
    instalados = json.loads(comando([npm_bin, "ls", "-g", "--depth=0", "--json"], 45).stdout).get("dependencies", {})
    fora = comando([npm_bin, "outdated", "-g", "--json"], 45)
    # npm outdated retorna 1 precisamente quando encontrou pacotes desatualizados.
    if fora.returncode not in (0, 1):
        raise RuntimeError(erro_curto(fora.stderr or fora.stdout))
    desatualizados = json.loads(fora.stdout or "{}")
    linhas = []
    for pacote in PACOTES_NPM:
        app = f"npm {pacote}"
        if pacote not in instalados:
            linhas.append(resultado(app, motivo="não instalado"))
        elif pacote not in desatualizados:
            linhas.append(resultado(app))
        else:
            antes = instalados[pacote].get("version", "?")
            depois = desatualizados[pacote].get("latest", "latest")
            if executar:
                r = instalar_npm(npm_bin, pacote)
                linha = (resultado(app, antes, depois) if r.returncode == 0 else
                         f"{app}: falhou ({erro_curto(r.stderr or r.stdout)})")
                pendentes = scripts_pendentes(r.stdout + r.stderr)
                if pendentes:
                    linha += f" (scripts não rodados: {', '.join(pendentes)})"
                linhas.append(linha)
            else:
                linhas.append(resultado(app, antes, depois))
    return linhas


def ollama_ocupado():
    if not shutil.which("ollama"):
        return False
    r = comando(["ollama", "ps"], 15)
    return r.returncode == 0 and len(r.stdout.strip().splitlines()) > 1


def winget(executar):
    if os.name != "nt":
        return [resultado("winget", motivo="somente Windows")]
    if not shutil.which("winget"):
        return [resultado("winget", motivo="não instalado")]
    try:
        r = comando(["powershell", "-NoProfile", "-Command", "(Get-Process).Path"], 30)
        em_uso = r.stdout.lower() if r.returncode == 0 else None
    except Exception:
        em_uso = None
    linhas = []
    for ident, trechos in WINGET.items():
        app = f"winget {ident}"
        # Consulta por id: a tabela geral do `winget upgrade` trunca ids em console estreito.
        r = comando(["winget", "list", "--id", ident, "--exact", "--upgrade-available",
                     "--accept-source-agreements", "--disable-interactivity"], 90)
        if ident.lower() not in (r.stdout + r.stderr).lower():
            linhas.append(resultado(app))
        elif trechos and em_uso is None:
            linhas.append(resultado(app, motivo="não foi possível verificar se está em uso"))
        elif any(t in em_uso for t in trechos) or (ident == "Ollama.Ollama" and ollama_ocupado()):
            linhas.append(resultado(app, motivo="em uso"))
        elif not executar:
            linhas.append(resultado(app, "instalada", "disponível"))
        else:
            atual = comando(["winget", "upgrade", "--id", ident, "--exact", "--silent",
                            "--accept-package-agreements", "--accept-source-agreements",
                            "--disable-interactivity"], 600)
            texto = atual.stdout + atual.stderr
            if re.search(r"administrat|elevat", texto, re.I):
                linhas.append(resultado(app, motivo="requer administrador"))
            else:
                linhas.append(resultado(app, "instalada", "atualizada") if atual.returncode == 0 else
                              f"{app}: falhou ({erro_curto(texto)})")
    return linhas


def brew(executar):
    if sys.platform != "darwin":
        return [resultado("Homebrew", motivo="somente macOS")]
    if not shutil.which("brew"):
        return [resultado("Homebrew", motivo="não instalado")]
    r = comando(["brew", "outdated", "--json"], 60)
    if r.returncode:
        raise RuntimeError(erro_curto(r.stderr or r.stdout))
    dados = json.loads(r.stdout)
    antigos = {x["name"]: x for x in dados.get("formulae", [])}
    linhas = []
    for formula in ("ollama", "ripgrep"):
        app = f"brew {formula}"
        if formula not in antigos:
            linhas.append(resultado(app))
        elif formula == "ollama" and ollama_ocupado():
            linhas.append(resultado(app, motivo="em uso"))
        else:
            item = antigos[formula]
            antes, depois = item.get("installed_versions", ["?"])[0], item.get("current_version", "?")
            if executar:
                atual = comando(["brew", "upgrade", formula], 600)
                linhas.append(resultado(app, antes, depois) if atual.returncode == 0 else
                              f"{app}: falhou ({erro_curto(atual.stderr or atual.stdout)})")
            else:
                linhas.append(resultado(app, antes, depois))
    return linhas


ADAPTADORES = (("token-router", plugin), ("npm global", npm),
              ("winget", winget), ("Homebrew", brew))


def coletar(executar):
    linhas = []
    for nome, adaptador in ADAPTADORES:
        try:
            valor = adaptador(executar)
            linhas.extend(valor if isinstance(valor, list) else [valor])
        except Exception as exc:
            linhas.append(f"{nome}: falhou ({erro_curto(exc)})")
    return linhas


def lock_valido():
    trava = ler_json(LOCK, {})
    inicio = data(trava.get("inicio"))
    return bool(inicio and agora() - inicio < dt.timedelta(hours=2))


def executar(imprimir=False):
    PASTA.mkdir(parents=True, exist_ok=True)
    if lock_valido():
        if imprimir:
            print("autoatualização já em andamento")
        return
    inicio = agora().isoformat()
    gravar_json(LOCK, {"pid": os.getpid(), "inicio": inicio})
    gravar_json(ESTADO, {"inicio": inicio, "fim": None, "resumo": [], "relatado": False})
    try:
        linhas = coletar(True)
        gravar_json(ESTADO, {"inicio": inicio, "fim": agora().isoformat(),
                             "resumo": linhas, "relatado": False})
        for linha in linhas:
            registrar(linha)
        if imprimir:
            print("\n".join(linhas))
    finally:
        LOCK.unlink(missing_ok=True)


def hook():
    if os.environ.get("TOKEN_ROUTER_AUTOATUALIZAR") != "ligado":
        return
    try:
        estado = ler_json(ESTADO, {})
        if estado.get("fim") and not estado.get("relatado"):
            linhas = [str(x).replace("\n", " ") for x in estado.get("resumo", [])]
            # Só o que pede atenção: mudança, falha, ou app pulado por motivo passageiro. Pulos
            # permanentes (outro SO) repetiriam o aviso em toda sessão.
            mudou = [x for x in linhas if "→" in x or ": falhou" in x or
                     any(m in x for m in ("(em uso)", "administrador", "verificar se está em uso"))]
            resumo = "; ".join(mudou) if mudou else f"tudo em dia ({len(linhas)} itens)"
            print(json.dumps({"systemMessage": f"[token-router] autoatualização: {resumo}"}, ensure_ascii=False))
            estado["relatado"] = True
            gravar_json(ESTADO, estado)
        inicio = data(estado.get("inicio"))
        if not lock_valido() and (inicio is None or agora() - inicio >= dt.timedelta(hours=INTERVALO_H)):
            opcoes = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL,
                      "stderr": subprocess.DEVNULL, "close_fds": True}
            if os.name == "nt":
                opcoes["creationflags"] = (subprocess.DETACHED_PROCESS |
                    subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW)
            else:
                opcoes["start_new_session"] = True
            subprocess.Popen([sys.executable, __file__, "--executar"], **opcoes)
    except Exception as exc:
        try:
            registrar(f"hook falhou: {erro_curto(exc)}")
        except Exception:
            pass


if __name__ == "__main__":
    if sys.argv[1:] == ["--hook"]:
        hook()
    elif sys.argv[1:] == ["--executar"]:
        executar()
    elif sys.argv[1:] == ["--agora"]:
        executar(imprimir=True)
    elif sys.argv[1:] == ["--verificar"]:
        print("\n".join(coletar(False)))
    else:
        print("uso: atualizar-vinculados.py --hook|--verificar|--agora|--executar", file=sys.stderr)
        sys.exit(2)
