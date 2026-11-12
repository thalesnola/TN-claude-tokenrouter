# Setup de máquina nova — ordem de instalação

Sequência mínima para deixar uma máquina nova equivalente à de origem. Cada passo
depende do anterior.

## 1. Pré-requisitos do sistema

| Requisito | Windows | Verificar |
|---|---|---|
| Git (traz o Git Bash) | `winget install Git.Git` | `git --version` |
| Python ≥ 3.12 | `winget install Python.Python.3.12` | `python --version` |
| uv | `winget install astral-sh.uv` | `uv --version` |
| Claude Code | app desktop ou CLI | `claude --version` |

> O **Git Bash é obrigatório no Windows**: o hook do plugin declara `"shell": "bash"`.
> Sem ele o Claude Code cai no PowerShell, a expansão `${CLAUDE_PLUGIN_ROOT}` vira
> vazia e as regras de roteamento não são injetadas — sem erro visível.

## 2. Graphify (requisito do roteamento)

```bash
uv tool install graphifyy
graphify install --platform claude
```

Verificar: `graphify --version` responde e `/graphify` aparece como skill.
É requisito, não opcional: as regras mandam consultar o grafo antes de ler arquivos.

## 3. Plugin token-router

```
/plugin marketplace add local-user/claude-token-router
/plugin install token-router@local-user-plugins
```

Traz os 4 subagentes (Explore/resumidor em Haiku, executor/revisor em Sonnet) e as
regras de roteamento, injetadas a cada sessão.

## 4. Configuração pessoal (opcional, máquina principal)

Restaura CLAUDE.md, settings.json, hooks, agentes, memória e os **manifestos de
plugins**:

```powershell
git clone https://github.com/local-user/claude-config "$env:USERPROFILE\.claude"
```

Faça isso **antes do primeiro uso** do Claude Code na máquina, para não conflitar
com os arquivos que ele cria sozinho. Depois, `claude` → `/login`.

## 5. Plugins do marketplace oficial

O clone do passo 4 traz `plugins/installed_plugins.json` e `known_marketplaces.json`
(o que estava instalado e de onde), mas **não** traz o conteúdo — `plugins/cache/` e
`plugins/marketplaces/` ficam de fora do backup por serem clones reproduzíveis.
Materialize com a CLI (não precisa do `/plugin` interativo):

```
claude plugin install claude-security@claude-plugins-official
```

Varredura profunda de vulnerabilidades dentro da sessão, com cada achado contestado
antes de ser reportado. Sem dependência externa.

## 6. Serena (MCP de análise semântica de código)

**Não instalar pelo plugin** — o `.mcp.json` do plugin `serena@claude-plugins-official`
chama `uvx` sem fixar o Python, e qualquer correção nele mora em `plugins/cache/`,
que `claude plugin update` sobrescreve. Registrar o servidor direto:

```
claude mcp add -s user serena -- uvx --python 3.12 --from git+https://github.com/oraios/serena serena start-mcp-server
```

⚠️ **O `--python 3.12` não é enfeite.** Sem ele o `uvx` pega o Python mais novo da
máquina (3.14 aqui); o `pyyaml` 6.0.2 não tem wheel para ele, o uv tenta compilar de
fonte e morre em `Microsoft Visual C++ 14.0 or greater is required`. Ajustar a versão
para alguma que tenha wheel pronta na máquina de destino (`uv python list --only-installed`).

O **primeiro start baixa e compila do GitHub** — demora e exige rede. Sem `uv`/`uvx`
(passo 1) o servidor nem sobe.

Conferir: `claude mcp get serena` deve dizer `Status: ✔ Connected`.

> O escopo `user` grava em `~/.claude.json`, que **não** entra no backup da config
> (fica fora de `~/.claude`). Em máquina nova, rode o comando acima à mão.

## 6b. Clone de desenvolvimento deste plugin — guarda de nome de caso

Em quem edita o plugin (clone em `~/claude-token-router`), uma vez por clone:

```powershell
python scripts/guarda-nome-de-caso.py --instalar
```

O `pre-commit` barra linha adicionada com o nome de uma pasta de `Casos`. O auditor do ACERVO
não pega isso — nome de operação não tem formato — e já vazou num commit deste repo.

## 7. Repositório de conhecimento ACERVO — hooks de sigilo (obrigatório se clonar)

Só se a máquina for usada com o acervo `C:\ACERVO` (repo `acervo-conhecimento`, privado).
**Logo depois do clone**, antes do primeiro commit:

```powershell
powershell -File C:\ACERVO\Segundo_Cerebro\.sistema\scripts\instalar-hook-git.ps1
```

Instala `pre-commit` e `pre-push` em `.git/hooks`, que rodam o auditor de sigilo e
**bloqueiam** commit/push com identificador de caso (CPF, CEP, nº de IPL, telefone,
endereço, IMEI, placa) no conteúdo.

⚠️ **`.git/hooks/` não é versionado** — clone novo nasce **sem** essa rede, e nada
avisa. É por isso que este passo é obrigatório e não opcional.

| Hook | Audita |
|---|---|
| `pre-commit` | o conteúdo **staged** (não a árvore de trabalho) |
| `pre-push` | o **range inteiro** que sobe — pega commit feito com `--no-verify` |

Conferir sem commitar nada:

```powershell
powershell -File C:\ACERVO\Segundo_Cerebro\.sistema\scripts\pre-commit.ps1
```

Sai `[pre-commit] limpo.` quando não há nada staged ou o staged está limpo.

## 8. Contingência Ollama (opcional)

Só se a máquina for usada com créditos limitados. Ver [`contingencia/README.md`](contingencia/README.md):
Ollama + modelos Qwen, funções `claude`/`claude-local` no perfil e o hook de revisão.

## Verificação final

```powershell
graphify --version                 # skill de grafo disponível
claude --version                   # CLI no PATH
git --version                      # Git Bash presente (Windows)
uvx --version                      # necessário para o MCP do serena
claude plugin list                 # token-router e claude-security habilitados
claude mcp get serena              # deve dizer "Connected"
Test-Path C:\ACERVO\.git\hooks\pre-push   # True se os hooks de sigilo foram instalados
```

Numa sessão do Claude Code: as regras de roteamento devem aparecer no início
(status "Carregando regras de roteamento"), e `/graphify --help` deve responder.
