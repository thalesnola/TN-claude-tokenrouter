# Hook SessionStart: se houve trabalho feito pelos modelos locais (Ollama) durante
# uma queda de creditos, injeta instrucao para o modelo Claude revisar esse trabalho.
# O marcador e criado pela funcao claude-local (perfil do PowerShell).
$marker = Join-Path $env:USERPROFILE '.claude\ollama-pendente.json'
if ((Test-Path $marker) -and ($env:ANTHROPIC_BASE_URL -notmatch 'localhost|127\.0\.0\.1')) {
    try { $dados = Get-Content $marker -Raw | ConvertFrom-Json } catch { $dados = $null }
    $inicio = if ($dados) { $dados.inicio } else { 'desconhecido' }
    $dir = if ($dados) { $dados.diretorio } else { 'desconhecido' }
    $ctx = "REVISAO PENDENTE (contingencia Ollama): durante uma indisponibilidade de creditos, " +
        "modelos locais (Ollama/Qwen) trabalharam nesta maquina a partir de $inicio no diretorio '$dir'. " +
        "Antes de prosseguir com qualquer tarefa nova, revise o trabalho feito por eles: " +
        "use git diff/log se for repositorio, ou compare arquivos modificados desde esse horario. " +
        "DELEGUE a revisao ao subagente 'revisor' (sonnet): use 'Explore' para levantar o que mudou " +
        "e 'resumidor' se o diff for extenso; nao leia o diff inteiro no contexto principal. " +
        "Procure bugs, codigo incompleto e desvios do padrao do projeto; corrija o que for necessario " +
        "e resuma ao usuario o que foi revisado. Ao concluir a revisao, DELETE o arquivo '$marker' " +
        "para encerrar a pendencia."
    @{ hookSpecificOutput = @{ hookEventName = 'SessionStart'; additionalContext = $ctx } } | ConvertTo-Json -Compress -Depth 5
}

