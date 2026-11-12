# Instalação manual (sem sistema de plugins): copia agentes para ~/.claude/agents
# e anexa as regras de roteamento ao ~/.claude/CLAUDE.md (se ainda não estiverem lá).
$ErrorActionPreference = 'Stop'
$repo = Split-Path $PSScriptRoot -Parent
$claudeDir = Join-Path $HOME '.claude'
$agentsDir = Join-Path $claudeDir 'agents'
New-Item -ItemType Directory -Force $agentsDir | Out-Null

Copy-Item (Join-Path $repo 'agents\*.md') $agentsDir -Force
Write-Host "Agentes copiados para $agentsDir"

$claudeMd = Join-Path $claudeDir 'CLAUDE.md'
$rules = Get-Content (Join-Path $repo 'rules\roteamento.md') -Raw
if ((Test-Path $claudeMd) -and (Get-Content $claudeMd -Raw) -match 'Economia de tokens') {
    Write-Host "CLAUDE.md ja contem as regras de roteamento — nada a fazer."
} else {
    Add-Content $claudeMd ("`n" + $rules)
    Write-Host "Regras de roteamento anexadas a $claudeMd"
}
