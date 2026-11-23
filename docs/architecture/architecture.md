# Arquitetura — Adalove CLI

> Última revisão: 2026-11-23 · Escopo: o projeto inteiro (pacote `adalove/` + front-ends em `cli/`)

## Visão geral

O Adalove CLI busca os dados do módulo na API da Adalove e os apresenta de três jeitos: um menu no terminal, um servidor web local e um dashboard HTML único com exportação em Markdown. Tudo roda na máquina do estudante. Não há backend próprio, banco de dados nem conta de usuário: o único estado persistente é o `config.json`, que guarda o token, a turma ativa e o mapeamento de professor para disciplina.

## Camadas

```
 cli/main.py  app Typer + menu           cli/server.py  servidor local (Flask)
 cli/commands/  um módulo por comando      cli/templates/  páginas Jinja
 cli/auth.py   credenciais + _call_api
 cli/ui.py, cli/files.py
        │                                      │
        └──────────────┬───────────────────────┘
                       ▼
            adalove/services/        regras compartilhadas pelos front-ends
              turmas.py                ordenar/rotular/trocar turma, switcher do dashboard
              teachers.py              mapear professor → disciplina
                       │
     ┌─────────────────┼──────────────────────┐
     ▼                 ▼                      ▼
adalove/api/      adalove/report/        adalove/writers/
  client.py         model.py               html.py   → dashboard.html
  (HTTP, token)     markdown.py            fetch.py  → .md do `adalove fetch`
                    common.py
     │                 │
     ▼                 ▼
adalove/models/  ◄── adalove/filters/      adalove/config/
  Activity, SectionInfo,  (classificação      paths.py    (todos os caminhos)
  StudentStatus, ...       das atividades)    settings.py (config.json, 0600)
                                              subjects.py (disciplinas, cores, eixos)
adalove/browser/capture.py — captura o token pelo Chromium (Playwright), em processo isolado
```

**Regra de dependência:** as setas apontam só para baixo. `cli/` depende de `adalove/`, e nada em `adalove/` importa `cli/`. `report/` não sabe nada de HTML, e `writers/html.py` não tem regra de negócio, só apresentação.

## Fluxo principal: Abrir Dashboard

1. O front-end carrega o `config.json` e renova o token se ele já tiver expirado, verificando o `exp` do JWT localmente (`token_expired`).
2. `AdaloveClient.fetch_userdata()` faz **uma** requisição a `/sections/<uuid>/userdata`.
3. `report.model.build_report()` transforma as atividades em dados estruturados: resumo por semana, sprints, projeto, prova e ponderadas.
4. `report.markdown.render_exports()` gera o Markdown de cada aba a partir **desses mesmos dados**.
5. `writers/html.py` embute tudo como JSON (relatório, HTML dos textos ricos e Markdown) num `dashboard.html` autocontido, com a fonte embutida para funcionar offline.
6. O `script.js` só desenha a página e baixa o Markdown que já veio pronto. Ele não tem regra de formatação.

## Decisões

| # | Decisão | Por quê |
|---|---------|---------|
| D1 | Uma única fonte para o conteúdo do relatório (`adalove/report/`) | Antes, as mesmas regras (resumo, Prova, filtros de links, datas) existiam em `html.py`, em 4 writers Python sem uso e no `script.js`. Os testes protegiam a cópia que ninguém usava. |
| D2 | O Markdown é gerado em Python e embutido no dashboard | O formato fica testado (`tests/test_markdown_*.py`) e o JS fica só com a apresentação. |
| D3 | `adalove/services/` com funções puras, recebendo dados e não clientes | O terminal e o servidor tinham cópias da troca de turma (3×) e do mapeamento de professores (3×). Funções puras não exigem mudar os pontos de mock dos testes. |
| D4 | Uma requisição por carregamento (`fetch_userdata`) | Os 4 métodos `fetch_*` repetiam o mesmo GET e o mesmo tratamento de erro. Eles continuam existindo como visões finas, por compatibilidade. |
| D5 | `config.json` gravado com permissão 0600 e de forma atômica | O arquivo guarda um bearer token, e uma falha no meio da gravação não pode corrompê-lo. |
| D6 | Captura do token em processo filho com timeout (já existente) | Um Playwright travado não pode prender o servidor nem deixar um Chromium órfão. |
| D7 | Servidor local sem login, preso a 127.0.0.1, com duas guardas: `Host` precisa ser loopback e todo POST com `Origin` precisa vir do próprio servidor | Quem alcança o servidor já consegue ler o `config.json`, então login não protege nada. As guardas impedem que uma página maliciosa aberta no navegador use o servidor (CSRF e DNS rebinding). |
| D8 | Páginas do servidor em templates Jinja (`cli/templates/`) | O escape fica automático. Antes era manual, em f-strings, e fácil de esquecer. |
| D9 | `cli/main.py` só registra comandos e mostra o menu; cada comando fica em `cli/commands/` | O arquivo tinha cerca de 1000 linhas, misturando prompts, credenciais, o gráfico ASCII e o servidor. |

## Convenções

- **Caminhos:** sempre via `adalove/config/paths.py`.
- **Erros da API:** `PermissionError` (token expirado ou inválido), `ConnectionError` (rede) e `ValueError` (token ou URL impossível de enviar). Os front-ends tratam esses três e evitam `except Exception`.
- **Mapeamento de disciplina:** o salvo pelo usuário vence o inferido pelo eixo (`report.common.resolve_subjects`). A aba Prova usa **só** o mapeamento salvo, para nunca colocar material na disciplina errada.
- **Dashboard:** é um arquivo só, sem dependência externa em tempo de execução (CSS, JS e fonte vão inline).

## Dívida técnica conhecida

| Item | Impacto | Sugestão |
|------|---------|----------|
| Ajuste de `sys.path` para o `.venv` (agora em `cli/__init__.py`) | Baixo | Remover depois de reproduzir o problema original. Não consegui reproduzi-lo, então mantive. |
| Token em texto puro no `config.json` (agora 0600) | Baixo, por ser uso local | Opcional: guardar no keychain do sistema (`keyring`) |
| Funções compartilhadas entre módulos do CLI ainda com prefixo `_` (`_call_api`, `_ok`…) | Baixo: só cosmético | Renomear sem o `_` numa próxima passada |
| Premissas não verificadas em `DashboardMetrics` (já documentadas lá) | Médio no Progresso | Validar contra a interface da Adalove |
