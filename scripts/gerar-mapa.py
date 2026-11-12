"""Gera docs/hierarquia-agentes.svg e confere que todo texto cabe na caixa (Segoe UI real; roda no Windows).

Uso: python scripts/gerar-mapa.py docs/hierarquia-agentes.svg — sai 1 se algum texto vazar.
Mudou o roteamento? Edite este script, não o SVG."""
from html import escape
from PIL import ImageFont
import sys

W, H = 900, 1340
DY = 0  # deslocamento acumulado das faixas abaixo da autoatualização
out, caixas, textos = [], [], []   # textos: (x, y, str, cls, anchor, caixa)

CLS = {"h": (14, True), "s": (11.5, False), "hw": (14, True), "sw": (11.5, False),
       "b": (12.5, True), "t": (11, False)}
FONT = {False: "C:/Windows/Fonts/segoeui.ttf", True: "C:/Windows/Fonts/segoeuib.ttf"}


def rect(x, y, w, h, fill="none", stroke=None, cls=None, rx=4):
    y += DY
    a = f' class="{cls}"' if cls else f' fill="{fill}"' + (f' stroke="{stroke}"' if stroke else "")
    out.append(f'  <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}"{a}/>')
    caixas.append((x, y, w, h))
    return len(caixas) - 1


def text(x, y, s, cls="s", anchor="start", caixa=None):
    y += DY
    a = f' text-anchor="{anchor}"' if anchor != "start" else ""
    out.append(f'  <text class="{cls}" x="{x}" y="{y}"{a}>{escape(s, quote=False)}</text>')
    textos.append((x, y, s, cls, anchor, caixa if caixa is not None else len(caixas) - 1))


def seta(x1, y1, x2, y2):
    y1 += DY
    y2 += DY
    out.append(f'  <line class="arr" x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" marker-end="url(#a)"/>')


VERDE, AZUL, AMBAR, CINZA, ROXO = (("#D1FAE5", "#059669"), ("#DBEAFE", "#2563EB"), ("#FEF3C7", "#D97706"),
                                   ("#F3F4F6", "#9CA3AF"), ("#EDE9FE", "#7C3AED"))

# ---- Camada 1 e porta
rect(320, 16, 260, 56, "#6D28D9", rx=6)
text(450, 40, "Opus 5.5 — cérebro", "hw", "middle")
text(450, 58, "camada 1 · decide, arquiteta, redige peça", "sw", "middle")
rect(215, 94, 470, 62, "#B91C1C", rx=6)
text(450, 114, "Só Claude e modelos locais — nenhuma nuvem de terceiros", "hw", "middle")
text(450, 131, "Codex · AGY/Gemini · Copilot: independentes, nunca acionados por aqui", "sw", "middle")
text(450, 147, "evidência original: nunca · só cópia de trabalho com proveniência", "sw", "middle")
seta(450, 72, 450, 94)


# ---- Camadas 2 e 3
def lado(x0, titulo, linhas, seta_de, sub=("camada 2 · comanda e confere", "camada 3 · trabalha")):
    c = rect(x0, 184, 425, 306, cls="cont", rx=6)
    text(x0 + 10, 204, titulo, "h")
    text(x0 + 10, 222, sub[0], "t", caixa=c)
    if sub[1]:
        text(x0 + 210, 222, sub[1], "t", caixa=c)
    seta(*seta_de)
    y = 232
    for cmd, cmd2, trab, trab2, cor_c, cor_t in linhas:
        if trab is None:
            rect(x0 + 10, y, 405, 56, *CINZA)
            text(x0 + 20, y + 22, cmd, "b")
            text(x0 + 20, y + 40, cmd2, "t")
        else:
            rect(x0 + 10, y, 170, 56, *cor_c)
            text(x0 + 20, y + 22, cmd, "b")
            text(x0 + 20, y + 40, cmd2, "t")
            seta(x0 + 180, y + 28, x0 + 198, y + 28)
            rect(x0 + 200, y, 215, 56, *cor_t)
            text(x0 + 210, y + 22, trab, "b")
            text(x0 + 210, y + 40, trab2, "t")
        y += 63


lado(20, "Locais (Ollama) — nada sai da máquina", [
    ("dsh-local (sonnet)", "1–4 arq. · revisor 2ª família", "DSH", "gpt-oss:20b (8 GB: divide CPU/GPU)", AZUL, VERDE),
    ("qwen-local (haiku)", "lote: >5 arquivos", "Qwen Code", "Qwen3-Coder-Next 80B · minutos", AZUL, VERDE),
    ("opencode (sonnet)", "pergunta ao acervo do caso", "OpenCode · investigador", "Nemotron 3.5 · MCPs rag+forense", AZUL, VERDE),
    ("modelo local: sempre o mais completo", "falta VRAM → descarrega residentes, nunca rebaixa", None, None, None, None),
], (215, 125, 150, 184))

lado(455, "Claude — camada 2 (Sonnet 5.5)", [
    ("Explore · resumidor", "fazem direto; grafo antes de ler arquivo", None, None, None, None),
    ("executor", "plano fechado · 1–2 arquivos direto", None, None, None, None),
    ("revisor", "confere todo trabalho local; adversarial", None, None, None, None),
    ("limiar de despacho", "só vai ao local quando o volume compensa", None, None, None, None),
], (685, 125, 750, 184), sub=("camada 2 · comanda e confere", None))

# ---- Conferência
rect(20, 504, 860, 78, "#FEE2E2", "#DC2626", rx=6)
text(450, 524, "Trabalho da camada 3 é NÃO revisado — o comandante confere antes de devolver ao Opus", "h", "middle")
text(450, 541, "saída crua nunca entra na janela do Opus · código → revisor (sonnet) e, em bloco grande, dsh-local revisor", "s", "middle")
text(450, 557, "consulta ao acervo → conferir proveniência (forense_path/custodia) antes de citar", "s", "middle")
text(450, 573, 'negativo ("não encontrei") → confirmar por Grep literal antes de subir', "s", "middle")
seta(232, 490, 232, 504)
seta(667, 490, 667, 504)

# ---- Contingência
c = rect(20, 596, 860, 150, cls="cont", rx=6)
text(30, 616, "Contingência automática — hook StopFailure, só em fim de crédito (100%) · 1 vez por sessão", "h")
text(30, 633, "sem gatilho por porcentagem (descartado em 24/10/2026) · o Claude revisa o trabalho na volta", "s")
passos = [("fim de crédito", "billing_error · rate_limit", ROXO), ("hook StopFailure", "1 vez por sessão", AMBAR),
          ("claude-local", "mesma conversa", VERDE), ("Ollama local", "qwen3-coder:30b", VERDE),
          ("volta o crédito", "SessionStart avisa", ROXO), ("revisor (sonnet)", "revisa o que o local fez", AZUL)]
x = 30
for i, (a, b, cor) in enumerate(passos):
    rect(x, 648, 136, 50, *cor)
    text(x + 68, 668, a, "b", "middle")
    text(x + 68, 686, b, "t", "middle")
    if i:
        seta(x - 5, 673, x - 1, 673)
    x += 141
text(30, 718, "janela nova na pasta onde a conversa nasceu, em ambiente limpo (sem variáveis CLAUDE_*/ANTHROPIC_* herdadas).", "s", caixa=c)
text(30, 735, "marcador ~/.claude/ollama-pendente.json guarda a pendência de revisão até o Claude concluí-la.", "s", caixa=c)

# ---- Autoatualização
rect(20, 760, 860, 64, "#EDE9FE", "#7C3AED", rx=6)
text(30, 782, "Autoatualização — interruptor TOKEN_ROUTER_AUTOATUALIZAR=ligado (padrão: desligado)", "h")
text(30, 805, "SessionStart, no máx. a cada 6 h, em 2º plano: plugin · Ollama · Qwen · OpenCode · DSH — app em uso é pulado", "s")
DY = 80

# ---- Perfil por máquina (1.25.1)
p = rect(20, 758, 860, 122, cls="cont", rx=6)
text(30, 778, "Perfil por máquina — SessionStart injeta maquinas/<id>.md; onde divergir das regras, vale o perfil", "h")
text(30, 795, "detecção: TOKEN_ROUTER_MAQUINA → hostname → darwin → VRAM (nvidia-smi) · inventário no repo estacoes", "s", caixa=p)
for x0, (cor, t, l1, l2) in zip((35, 315, 595), [
    (VERDE, "workstation-windows", "RTX 2000 Ada 16 GB · 128 GB", "DSH gpt-oss:20b 100% GPU (13 s)"),
    (AMBAR, "workstation Windows", "RTX PRO 1000 8 GB · 64 GB", "DSH gpt-oss 70 s (CPU/GPU)"),
    (("#FCE7F3", "#DB2777"), "personal-device", "48 GB unificados · arm64", "DSH gpt-oss:20b · local 30b")]):
    rect(x0, 806, 270, 64, *cor)
    text(x0 + 10, 825, t, "b")
    text(x0 + 10, 843, l1, "t")
    text(x0 + 10, 859, l2, "t")
DY = 230

# ---- GSD
g = rect(20, 744, 860, 150, cls="cont", rx=6)
text(30, 764, "GSD — fluxo por fases (/gsd-*) · um GSD para cada runtime, independentes", "h")
text(30, 781, "o do Claude vive em ~/.claude (acionado pelo Opus); o do Codex vive em ~/.codex e este plugin não o toca", "s")
for x0, (cor, t, ls) in zip((35, 315, 595), [
    (("#E0E7FF", "#4F46E5"), "Claude · Windows (por máquina)",
     ["GSD instalado só com --claude", "config em settings.local.json", "(não versionado · caminhos C:/...)", "depois: separar-gsd.py"]),
    (CINZA, "claude-config (compartilhado)",
     ["settings.json SEM nada do GSD", "hooks/separar-gsd.py (idempotente)", ".gitignore barra hooks/gsd-*", "nada do GSD do Codex aqui"]),
    (("#FEF3C7", "#D97706"), "Codex (independente)",
     ["agentes em ~/.codex/agents", "instalado e atualizado à parte", "ajuste de esforço mora em ~/.codex", "fora do repo e do plugin"])]):
    rect(x0, 792, 270, 92, *cor)
    text(x0 + 10, 811, t, "h")
    for j, l in enumerate(ls):
        text(x0 + 10, 829 + 16 * j, l, "s")

# ---- Eixos
rect(20, 908, 860, 78, "#F9FAFB", "#D1D5DB")
text(30, 928, "Eixos, em ordem: 1 crédito (o que está escasso) · 2 latência · 3 contexto · 4 diversidade de família (gpt-oss revisa Qwen/Claude).", "s")
text(30, 946, "Gatilhos: >5 arquivos → qwen · 1–4 arquivos → dsh · pergunta sobre o acervo do caso → opencode", "s")
text(30, 962, "· 2ª falha no bug → replanejar no Opus (/effort alto) · bloco >200 linhas → revisor + dsh revisor", "s")
text(30, 978, "· janela >~120 mil → transferir. Ninguém pula camada: o Opus não chama o Ollama direto.", "s")

# ---- Siglas
rect(20, 998, 860, 102, "#FFFFFF", "#D1D5DB")
text(30, 1017, "Siglas", "h")
sig = [("Ollama", "servidor de modelos locais (offline)"), ("DSH", "DeepSeek Harness: agente de código local"),
       ("GSD", "Get Shit Done: fluxo de projeto por fases"), ("MCP", "Model Context Protocol: ferramentas ao agente"),
       ("StopFailure", "hook do Claude Code: fim de crédito"), ("rag", "busca no acervo indexado (RAG)"),
       ("VRAM · GB", "memória da placa de vídeo · gigabytes"), ("8b · 20b · 30b · 80B", "bilhões de parâmetros")]
for k, (a, b) in enumerate(sig):
    x0, y0 = (30 if k < 4 else 455), 1036 + 17 * (k % 4) + DY
    out.append(f'  <text class="s" x="{x0}" y="{y0}"><tspan font-weight="700">{escape(a)}</tspan> — {escape(b)}</text>')
    textos.append((x0, y0, f"{a} — {b}", "s", "start", len(caixas) - 1))

cab = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" font-family="Segoe UI, Inter, Helvetica, Arial, sans-serif">
  <!-- Roteamento do token-router — 24/10/2026 (2.0): só Claude e modelos locais; contingência StopFailure → claude-local. Coordenadas fixas. -->
  <defs>
    <style>
      .h {{ font-size:14px; font-weight:600; fill:#1B2130; }}
      .b {{ font-size:12.5px; font-weight:600; fill:#1B2130; }}
      .s {{ font-size:11.5px; fill:#4B5563; }}
      .t {{ font-size:11px; fill:#4B5563; }}
      .sw {{ font-size:11.5px; fill:#FFFFFF; }}
      .hw {{ font-size:14px; font-weight:600; fill:#FFFFFF; }}
      .cont {{ fill:none; stroke:#9CA3AF; stroke-width:1; stroke-dasharray:5 4; }}
      .arr {{ stroke:#6B7280; stroke-width:1.2; fill:none; }}
    </style>
    <marker id="a" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M2 1L8 5L2 9" fill="none" stroke="#6B7280" stroke-width="1.5"/></marker>
  </defs>
  <rect width="{W}" height="{H}" fill="#FFFFFF"/>
'''

# ---- Checagem: largura real (Segoe UI) + 10% de folga, pelas duas bordas, contra a caixa do texto
erros = 0
for x, y, s, cls, anc, ci in textos:
    px, bold = CLS[cls]
    w = ImageFont.truetype(FONT[bold], round(px * 4)).getlength(s) / 4 * 1.10
    esq = x - (w / 2 if anc == "middle" else 0)
    dir_ = esq + w
    bx, by, bw, bh = caixas[ci]
    if esq < bx + 4 or dir_ > bx + bw - 4 or not (by < y <= by + bh):
        erros += 1
        print(f"VAZA: {s!r} [{esq:.0f}–{dir_:.0f}] caixa [{bx}–{bx + bw}] y={y}")
assert max(by + bh for _, by, _, bh in caixas) <= H
open(sys.argv[1], "w", encoding="utf-8").write(cab + "\n".join(out) + "\n</svg>\n")
print(f"{len(textos)} textos, {erros} vazando")
sys.exit(1 if erros else 0)
