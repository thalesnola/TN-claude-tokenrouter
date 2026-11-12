# token-router / contingência Ollama — funções para o perfil do PowerShell
# Instalação: anexe este arquivo ao seu $PROFILE (PowerShell 7) e crie o perfil do
# Windows PowerShell 5.1 apontando para ele (ver contingencia/README.md).
# Requisitos: Ollama >= 0.14, modelo qwen3-coder:30b baixado (os três níveis),
# variável de usuário OLLAMA_CONTEXT_LENGTH=32768 (o padrão 4096 trunca o prompt
# do Claude Code e o modelo responde lixo).

# Expõe `claude` no terminal usando o CLI embutido no app desktop (fora do PATH) — SÓ quando
# esse binário existe. Na workstation-windows não existe e o `claude` é o claude.cmd do npm: uma
# função incondicional sombreava o comando e só devolvia erro (medido em 23/09/2026).
if (Get-ChildItem "$env:APPDATA\Claude\claude-code\*\claude.exe" -ErrorAction SilentlyContinue) {
    function global:claude {
        $exe = Get-ChildItem "$env:APPDATA\Claude\claude-code\*\claude.exe" -ErrorAction SilentlyContinue |
            Sort-Object { [version]($_.Directory.Name) } -Descending |
            Select-Object -First 1 -ExpandProperty FullName
        & $exe @args
    }
}

# Contingência de créditos: retoma a MESMA conversa nos modelos locais via Ollama.
# Uso: `claude-local` (continua a última conversa) ou `claude-local -Nova`.
# Grava um marcador; na volta aos modelos Claude, o hook SessionStart
# (revisar-trabalho-ollama.ps1) manda revisar o trabalho feito localmente.
function claude-local {
    [CmdletBinding()]
    param([switch]$Nova, [string]$Sessao)   # -Sessao <id>: retoma essa conversa (o hook de contingência passa)

    $env:ANTHROPIC_BASE_URL             = 'http://localhost:11434'
    $env:ANTHROPIC_AUTH_TOKEN           = 'ollama'   # exigido pelo protocolo, valor ignorado
    $env:ANTHROPIC_DEFAULT_OPUS_MODEL   = 'qwen3-coder:30b'
    $env:ANTHROPIC_DEFAULT_SONNET_MODEL = 'qwen3-coder:30b'
    $env:ANTHROPIC_DEFAULT_HAIKU_MODEL  = 'qwen3-coder:30b'   # 7b perde o começo do prompt longo (medido 12/08)
    $env:CLAUDE_CODE_MAX_CONTEXT_TOKENS = '32768'            # = contexto concedido; sem isto o CLI supõe 200k e o Ollama trunca

    # Registra a pendência de revisão (preserva o início da primeira queda)
    $marker = Join-Path $env:USERPROFILE '.claude\ollama-pendente.json'
    if (-not (Test-Path $marker)) {
        @{ inicio = (Get-Date -Format o); diretorio = (Get-Location).Path } |
            ConvertTo-Json | Set-Content $marker
    }

    # Garante o serviço do Ollama com contexto suficiente para o Claude Code (>=32K)
    $env:OLLAMA_CONTEXT_LENGTH = '32768'
    if (-not (Get-Process ollama -ErrorAction SilentlyContinue)) {
        Start-Process ollama -ArgumentList 'serve' -WindowStyle Hidden
        Start-Sleep -Seconds 2
    }

    # Resolve o CLI: PATH primeiro; senão, o binário embutido no app desktop
    $claudeExe = (Get-Command claude -CommandType Application -ErrorAction SilentlyContinue).Source
    if (-not $claudeExe) {
        $claudeExe = Get-ChildItem "$env:APPDATA\Claude\claude-code\*\claude.exe" -ErrorAction SilentlyContinue |
            Sort-Object { [version]($_.Directory.Name) } -Descending |
            Select-Object -First 1 -ExpandProperty FullName
    }
    if (-not $claudeExe) {
        Write-Error 'claude.exe nao encontrado (nem no PATH, nem no app desktop).'
        return
    }

    try {
        if ($Nova) { & $claudeExe }
        elseif ($Sessao) { & $claudeExe --resume $Sessao }
        else { & $claudeExe --continue }
    }
    finally {
        # Limpa o ambiente para a próxima sessão voltar aos modelos Claude
        Remove-Item Env:ANTHROPIC_BASE_URL, Env:ANTHROPIC_AUTH_TOKEN,
            Env:ANTHROPIC_DEFAULT_OPUS_MODEL, Env:ANTHROPIC_DEFAULT_SONNET_MODEL,
            Env:ANTHROPIC_DEFAULT_HAIKU_MODEL, Env:CLAUDE_CODE_MAX_CONTEXT_TOKENS -ErrorAction SilentlyContinue
    }
}
