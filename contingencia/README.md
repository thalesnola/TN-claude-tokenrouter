# Contingência de créditos — Ollama local (função adicional)

Quando os créditos/limite do Claude acabam, o trabalho não para: um comando troca a
sessão para modelos locais via Ollama, e um hook garante que os modelos Claude
**revisem tudo que o modelo local fez** assim que os créditos voltarem. Os modelos
Claude são sempre os principais; o local é só contingência.

Validado de ponta a ponta em 2026-07-20 (Windows 11, Ollama 0.32.1, Claude Code 2.1.215).

## Instalação (Windows)

1. **Ollama e modelos** (Ollama ≥ 0.14, que fala a Messages API da Anthropic):
   ```powershell
   choco install ollama          # elevado
   ollama pull qwen3-coder:30b   # cérebro/executor local (~18 GB)
   # qwen2.5-coder:7b NÃO: perde o começo de prompt longo — os três níveis usam o 30b
   ```

2. **Contexto obrigatório** — o padrão (4096) trunca o prompt do Claude Code e o
   modelo responde lixo de ~2 tokens:
   ```powershell
   [Environment]::SetEnvironmentVariable('OLLAMA_CONTEXT_LENGTH','32768','User')
   # matar `ollama` E `ollama app` e relançar — o app de bandeja ignora env de shells
   ```

3. **Funções do perfil** — anexe `perfil-claude.ps1` ao seu `$PROFILE` (PowerShell 7).
   Para o Windows PowerShell 5.1 usar o mesmo perfil, crie o dele com:
   ```powershell
   . (Join-Path (Split-Path (Split-Path $PROFILE)) 'PowerShell\Microsoft.PowerShell_profile.ps1')
   ```
   > Se algum caminho tiver acentos, grave os perfis em UTF-8 **com BOM** — o 5.1
   > lê UTF-8 sem BOM como ANSI e quebra silenciosamente.

   > **Regra para qualquer `.ps1` deste repo:** UTF-8 **com BOM**, ou ASCII puro.
   > O Windows PowerShell 5.1 lê UTF-8 sem BOM como ANSI: um travessão (`—`) dentro
   > de uma string vira "cadeia sem terminador" e o script inteiro deixa de parsear.
   > Verificar antes de commitar:
   > `powershell.exe -NoProfile -Command "$e=$null; [Parser]::ParseFile('<script>',[ref]$null,[ref]$e); $e.Count"`

4. **Hook de revisão** — copie `revisar-trabalho-ollama.ps1` para
   `~/.claude/hooks/` e registre no `~/.claude/settings.json`:
   ```json
   "hooks": {
     "SessionStart": [ { "hooks": [ {
       "type": "command", "shell": "powershell",
       "command": "& \"$env:USERPROFILE\\.claude\\hooks\\revisar-trabalho-ollama.ps1\"",
       "timeout": 15, "statusMessage": "Verificando pendência de revisão do Ollama"
     } ] } ]
   }
   ```

5. **Login do CLI** — o CLI embutido no app desktop não herda o login do app:
   rode `claude` no terminal e faça `/login` uma vez (o modo local dispensa login).

## Uso

| Situação | Comando |
|---|---|
| Créditos acabaram no meio do trabalho | sair da sessão → `claude-local` (retoma a mesma conversa) |
| Começar conversa nova no modo local | `claude-local -Nova` |
| Créditos voltaram | `claude` normal — o hook injeta a ordem de revisão automaticamente |

O marcador `~/.claude/ollama-pendente.json` controla a pendência; o próprio modelo
Claude o apaga ao concluir a revisão.

## Limitações conhecidas

- Não existe troca a quente no meio de uma sessão viva — o endpoint é lido na
  inicialização; `claude-local` + `--continue` é o mínimo de fricção possível.
- Modelos locais são bem mais fracos que o Claude: use para tarefas mecânicas e
  bem especificadas (a regra em `rules/roteamento.md` instrui o modelo local a ser
  conservador e anotar suposições).
- O 7B pode alucinar chamadas de ferramenta em prompts artificiais; o 30B é o
  mínimo recomendado para o papel de modelo principal local.

## Medir um modelo candidato antes de trocá-lo (`medir-modelo-local.py`)

Compara modelos do Ollama lado a lado no perfil do OpenCode investigativo: carga fria,
tok/s quente, **sessão de 20 turnos com contexto crescente** (onde um denso com atenção
completa degrada em 8 GB de VRAM) e tool-calling com a schema que quebrou o Qwen Code.
Descarrega tudo antes de cada modelo — nunca dois pesos grandes ao mesmo tempo.

```powershell
python medir-modelo-local.py qwen3:8b nemotron-3.5-lightning:30b-a3b
```

Saída em `~/Casos/_medicoes/medicao-<data>-{turnos,resumo}.csv`. Regra de decisão para o
OpenCode: se o candidato degrada menos com o contexto e passa no tool-calling, ele assume;
empate, fica quem carrega mais rápido a frio. Motivação e quadro em
`nemotron-candidato-ao-opencode-nao-ao-executor` (vault).

## Contingência automática (hook `StopFailure`)

Só Ollama local (decidido em 24/10/2026; antes havia cascata por Codex, AGY, Copilot e Gemini,
que saiu do plugin). Quando o turno falha por fim de crédito (`billing_error`, ou `rate_limit`
com mensagem de limite de uso — nunca 429 passageiro nem "high load"), o hook roda
`contingencia/contingencia-automatica.py` e abre **uma janela nova**, uma vez por sessão, com
`claude-local -Sessao <id>`: a mesma conversa, na pasta onde nasceu, no modelo local. O
marcador `~/.claude/ollama-pendente.json` faz o `SessionStart` mandar revisar o trabalho na volta.
Não há gatilho por porcentagem de cota (o usuário descartou o de 90%): o fim de crédito é o gatilho.

Testar sem abrir janela: `CONTINGENCIA_DRY_RUN=1 python3 contingencia-automatica.py < evento.json`;
regras: `python3 contingencia-automatica.py --teste`.
