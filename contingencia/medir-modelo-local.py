#!/usr/bin/env python3
"""Mede modelos locais do Ollama lado a lado, no perfil do OpenCode investigativo.

Quatro medições por modelo, em ordem:

  1. carga fria     -- descarrega tudo, manda um prompt curto, lê `load_duration`
  2. quente          -- N repetições do mesmo prompt curto; mediana de tok/s de
                        leitura e de geração (a fria fica fora da conta)
  3. sessão longa    -- simula T turnos de agente: cada turno acrescenta ~1,5k
                        tokens de "saída de ferramenta" ao histórico e pede uma
                        resposta curta. Registra por turno: tokens no contexto,
                        tok/s de leitura, tok/s de geração e a fração do modelo
                        residente em VRAM (`/api/ps`). É aqui que um denso com
                        atenção completa degrada e um híbrido Mamba não deveria.
  4. tool-calling    -- um pedido com ferramentas cuja schema reproduz a classe
                        que quebrou o Qwen Code (enum com espaço + maxItems +
                        maxLength). Registra se veio tool_call, texto, ou erro.

Saída: CSV por turno e um resumo em stdout. Só métricas -- nenhum conteúdo do
acervo entra aqui; o texto dos turnos é sintético.

Uso:
  python medir-modelo-local.py qwen3:8b nemotron-3.5-lightning:30b-a3b
  python medir-modelo-local.py --turnos 20 --ctx 32768 --saida C:/Casos/_medicoes m1 m2

Regras que o script respeita (medidas em 24/08 e 31/08/2026):
  - só um modelo residente por vez (dois pesos grandes não cabem em 63,5 GB);
  - nunca num_gpu=0;
  - carga fria medida uma vez e separada das médias quentes.
"""
from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

HOST = "http://127.0.0.1:11434"

PROMPT_CURTO = (
    "Explique em três frases a diferença entre um índice B-tree e um índice hash "
    "num banco SQLite. Responda em português."
)


def bloco_ferramenta(turno: int) -> str:
    """~1,5k tokens de saída sintética de ferramenta (listagem fictícia).

    28 linhas: hash e carimbo tokenizam mal (~55 tok/linha no Qwen3). Medido em
    12/09/2026 -- com 90 linhas cada turno passava de 5k tokens.
    """
    linhas = [f"[turno {turno}] resultado da ferramenta listar_diretorio:"]
    for i in range(28):
        tam = (i * 7919 + turno) % 500000
        falso_hash = "%064x" % ((i + 1) * (turno + 1) * 2654435761)
        linhas.append(
            f"  {i:04d}  arquivo_{turno:02d}_{i:03d}.bin  tamanho={tam:>7}  "
            f"mtime=2026-01-{(i % 28) + 1:02d}T{(i % 24):02d}:{(i * 13) % 60:02d}:00  "
            f"sha256={falso_hash[:16]}..."
        )
    linhas.append("Resuma em uma frase quantos itens apareceram e continue a investigação.")
    return "\n".join(linhas)


FERRAMENTAS = [
    {
        "type": "function",
        "function": {
            "name": "listar_diretorio",
            "description": "Lista arquivos de um diretório de trabalho.",
            "parameters": {
                "type": "object",
                "properties": {"caminho": {"type": "string"}},
                "required": ["caminho"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "report_findings",
            "description": "Registra achados (schema na classe que quebrou o sampler).",
            "parameters": {
                "type": "object",
                "properties": {
                    "findings": {
                        "type": "array",
                        "maxItems": 32,
                        "items": {
                            "type": "object",
                            "properties": {
                                "summary": {"type": "string", "maxLength": 200},
                                "priority": {
                                    "type": "string",
                                    "enum": ["Must have", "Nice to have", "Low"],
                                },
                            },
                            "required": ["summary", "priority"],
                        },
                    }
                },
                "required": ["findings"],
            },
        },
    },
]


# ---------------------------------------------------------------- HTTP helpers
def api(path: str, payload: dict | None = None, timeout: int = 1800) -> dict:
    dados = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        HOST + path, data=dados, headers={"Content-Type": "application/json"},
        method="POST" if dados else "GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def descarregar_tudo() -> None:
    for m in api("/api/ps").get("models", []):
        api("/api/generate", {"model": m["name"], "keep_alive": 0})
    for _ in range(30):  # espera o servidor soltar a memória
        if not api("/api/ps").get("models"):
            return
        time.sleep(1)


def residente(modelo: str) -> tuple[float, int, str]:
    """(fração em VRAM, contexto concedido, rótulo CPU/GPU) do modelo carregado."""
    for m in api("/api/ps").get("models", []):
        if m["name"] == modelo:
            tam, vram = m.get("size", 0), m.get("size_vram", 0)
            frac = vram / tam if tam else 0.0
            return frac, m.get("context_length", 0), f"{100 - frac * 100:.0f}% CPU / {frac * 100:.0f}% GPU"
    return 0.0, 0, "não residente"


def chat(modelo: str, mensagens: list[dict], ctx: int, tools: list | None = None,
         num_predict: int = 256) -> dict:
    payload = {
        "model": modelo,
        "messages": mensagens,
        "stream": False,
        "keep_alive": "30m",
        "options": {"num_ctx": ctx, "num_predict": num_predict, "temperature": 0},
    }
    if tools:
        payload["tools"] = tools
    return api("/api/chat", payload)


def toks(resp: dict) -> tuple[float, float, int, int, float]:
    """(tok/s leitura, tok/s geração, tokens lidos, tokens gerados, carga s)."""
    pe, ped = resp.get("prompt_eval_count", 0), resp.get("prompt_eval_duration", 0)
    ev, evd = resp.get("eval_count", 0), resp.get("eval_duration", 0)
    ld = resp.get("load_duration", 0) / 1e9
    return (pe / ped * 1e9 if ped else 0.0, ev / evd * 1e9 if evd else 0.0, pe, ev, ld)


# ------------------------------------------------------------------- medições
def medir(modelo: str, ctx: int, repeticoes: int, turnos: int, escritor: csv.writer) -> dict:
    res: dict = {"modelo": modelo}
    print(f"\n=== {modelo} ===", flush=True)

    # 1. carga fria
    descarregar_tudo()
    t0 = time.perf_counter()
    r = chat(modelo, [{"role": "user", "content": PROMPT_CURTO}], ctx, num_predict=64)
    parede = time.perf_counter() - t0
    _, _, _, _, carga = toks(r)
    frac, ctx_conc, proc = residente(modelo)
    res.update(carga_fria_s=round(carga, 1), parede_fria_s=round(parede, 1),
               ctx_concedido=ctx_conc, processador=proc)
    print(f"  carga fria: {carga:.1f} s (parede {parede:.1f} s) | ctx concedido {ctx_conc} | {proc}", flush=True)
    if frac == 0.0 and "não" not in proc:
        print("  AVISO: 0% GPU -- conferir num_gpu; a regra é nunca num_gpu=0")

    # 2. quente
    leit, ger = [], []
    for i in range(repeticoes):
        r = chat(modelo, [{"role": "user", "content": PROMPT_CURTO}], ctx, num_predict=200)
        pl, pg, *_ = toks(r)
        leit.append(pl)
        ger.append(pg)
        print(f"  quente {i + 1}/{repeticoes}: leitura {pl:6.1f} tok/s | geração {pg:5.1f} tok/s", flush=True)
    res.update(leitura_tok_s=round(statistics.median(leit), 1),
               geracao_tok_s=round(statistics.median(ger), 1))

    # 3. sessão longa
    hist: list[dict] = [{"role": "system", "content":
                         "Você é um agente investigativo. Responda em no máximo duas frases."}]
    primeiro = ultimo = None
    for t in range(1, turnos + 1):
        hist.append({"role": "user", "content": bloco_ferramenta(t)})
        try:
            r = chat(modelo, hist, ctx, num_predict=80)
        except urllib.error.HTTPError as e:
            print(f"  turno {t}: HTTP {e.code} -- {type(e).__name__}; sessão interrompida")
            res["sessao_erro_turno"] = t
            break
        pl, pg, pe, ev, _ = toks(r)
        conteudo = (r.get("message") or {}).get("content", "") or "(vazio)"
        hist.append({"role": "assistant", "content": conteudo})
        frac, _, proc = residente(modelo)
        linha = dict(modelo=modelo, turno=t, tokens_contexto=pe, leitura_tok_s=round(pl, 1),
                     geracao_tok_s=round(pg, 1), gerados=ev, gpu_frac=round(frac, 3), processador=proc)
        escritor.writerow(linha.values())
        if t == 1:
            primeiro = linha
        ultimo = linha
        if t in (1, 5, 10, 15, 20) or t == turnos:
            print(f"  turno {t:2d}: ctx {pe:6d} tok | leitura {pl:6.1f} | geração {pg:5.1f} tok/s | {proc}", flush=True)
        if pe > ctx * 0.95:
            print(f"  janela cheia no turno {t} -- parando a sessão")
            break
    if primeiro and ultimo:
        res.update(sessao_turnos=ultimo["turno"], sessao_ctx_final=ultimo["tokens_contexto"],
                   geracao_turno1=primeiro["geracao_tok_s"], geracao_final=ultimo["geracao_tok_s"],
                   leitura_turno1=primeiro["leitura_tok_s"], leitura_final=ultimo["leitura_tok_s"],
                   gpu_turno1=primeiro["gpu_frac"], gpu_final=ultimo["gpu_frac"])
        g1 = primeiro["geracao_tok_s"]
        queda = 100 * (1 - ultimo["geracao_tok_s"] / g1) if g1 else 0.0
        res["queda_geracao_pct"] = round(queda, 1)
        print(f"  degradação da geração turno 1 -> {ultimo['turno']}: {queda:.1f}%")

    # 4. tool-calling
    try:
        r = chat(modelo, [{"role": "user", "content":
                           "Liste o diretório C:/Casos usando a ferramenta adequada."}],
                 ctx, tools=FERRAMENTAS, num_predict=200)
        msg = r.get("message") or {}
        if msg.get("tool_calls"):
            nome = msg["tool_calls"][0].get("function", {}).get("name")
            res["tool_calling"] = f"ok ({nome})"
        else:
            res["tool_calling"] = "sem tool_call (respondeu texto)"
    except urllib.error.HTTPError as e:
        corpo = ""
        try:
            corpo = json.loads(e.read()).get("error", "")[:80]
        except Exception:
            pass
        res["tool_calling"] = f"ERRO HTTP {e.code}: {corpo}"
    print(f"  tool-calling: {res['tool_calling']}")

    return res


def gpu_compartilhada() -> list[str]:
    """Outros processos na GPU além do próprio Ollama. Medição com a GPU dividida não vale
    (12/09/2026: um WhisperProcess do IPED derrubou o qwen3:8b de 29 para 2,4 tok/s quente)."""
    import subprocess
    try:
        saida = subprocess.run(
            ["nvidia-smi", "--query-compute-apps=process_name", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=15).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    return [l.strip() for l in saida.splitlines() if l.strip() and "ollama" not in l.lower()]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("modelos", nargs="+")
    ap.add_argument("--ctx", type=int, default=32768, help="num_ctx pedido (padrão 32768)")
    ap.add_argument("--repeticoes", type=int, default=3)
    ap.add_argument("--turnos", type=int, default=20)
    ap.add_argument("--saida", default=str(Path.home() / "Casos" / "_medicoes"))
    ap.add_argument("--ignorar-gpu-compartilhada", action="store_true",
                    help="mede mesmo com outro processo na GPU (o resultado NÃO vale para decisão)")
    a = ap.parse_args()

    outros = gpu_compartilhada()
    if outros and not a.ignorar_gpu_compartilhada:
        print("GPU compartilhada com outro processo -- medição não valeria. Processos:")
        for o in outros:
            print("  ", o)
        print("Espere terminar, ou passe --ignorar-gpu-compartilhada (só para teste do script).")
        return 3

    try:
        disponiveis = {m["name"] for m in api("/api/tags")["models"]}
    except Exception as e:
        print(f"Ollama não respondeu em {HOST}: {type(e).__name__}")
        return 1
    faltam = [m for m in a.modelos if m not in disponiveis]
    if faltam:
        print("Modelos ausentes no Ollama:", ", ".join(faltam))
        return 1

    pasta = Path(a.saida)
    pasta.mkdir(parents=True, exist_ok=True)
    carimbo = datetime.now().strftime("%Y-%m-%d_%H%M")
    csv_turnos = pasta / f"medicao-{carimbo}-turnos.csv"
    csv_resumo = pasta / f"medicao-{carimbo}-resumo.csv"

    resultados = []
    with open(csv_turnos, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["modelo", "turno", "tokens_contexto", "leitura_tok_s", "geracao_tok_s",
                    "gerados", "gpu_frac", "processador"])
        for m in a.modelos:
            resultados.append(medir(m, a.ctx, a.repeticoes, a.turnos, w))
            f.flush()
    descarregar_tudo()

    chaves = sorted({k for r in resultados for k in r}, key=lambda k: (k != "modelo", k))
    with open(csv_resumo, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=chaves)
        w.writeheader()
        w.writerows(resultados)

    print("\n=== RESUMO ===")
    for r in resultados:
        print(f"{r['modelo']}: fria {r.get('carga_fria_s')} s | quente leitura {r.get('leitura_tok_s')} "
              f"/ geração {r.get('geracao_tok_s')} tok/s | sessão {r.get('sessao_turnos')} turnos, "
              f"ctx {r.get('sessao_ctx_final')}, geração {r.get('geracao_turno1')} -> {r.get('geracao_final')} "
              f"({r.get('queda_geracao_pct')}%), GPU {r.get('gpu_turno1')} -> {r.get('gpu_final')} | "
              f"tools: {r.get('tool_calling')}")
    print(f"\nCSV: {csv_turnos}\n     {csv_resumo}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
