# Adalove CLI

CLI para estudantes do Inteli que consomem a plataforma **Adalove**. Conecta diretamente à API da plataforma, filtra atividades por semana e disciplina, e gera arquivos Markdown prontos para uso — sem precisar abrir o navegador.

## O que faz

- **Dashboard** — exibe no terminal um resumo do seu progresso acadêmico: nota acumulada, nota até o momento, nota necessária na prova, semana atual, ponderadas da semana e auto-estudos pendentes/concluídos, com um gráfico de pizza ASCII mostrando sua frequência.
- **Buscar** — baixa todas as atividades da API, permite filtrar por semanas e disciplinas via menu interativo, e gera dois arquivos em `output/`:
  - `activities-<timestamp>.md` — atividades com título, professor, URL e descrição, organizadas por semana e disciplina.
  - `links-<timestamp>.md` — lista limpa de links das atividades filtradas.
- **Setup** — configura credenciais (URL da API + token Bearer) e mapeia cada professor à sua disciplina. Tenta capturar as credenciais automaticamente via Playwright; cai para entrada manual se não estiver instalado.

## Instalação

```bash
git clone <repo>
cd adaloveAutomation
python -m venv .venv && source .venv/bin/activate
pip install -e .

# opcional: captura automática de credenciais
pip install playwright && playwright install chromium
```

## Uso

```bash
adalove          # menu interativo principal
adalove setup    # (re)configurar credenciais
adalove fetch    # filtrar e exportar atividades
```

Na primeira execução, escolha **Setup** para salvar suas credenciais em `config.json`. Depois use **Buscar** para exportar ou **Dashboard** para ver seu resumo.

## Credenciais

O token da API expira periodicamente. Quando isso ocorrer, o CLI detecta automaticamente e tenta renovar via browser. Se preferir renovar manualmente:

1. Abra o Adalove no navegador.
2. Inspecione a aba **Rede** e localize uma requisição para `apiv2.inteli.edu.br`.
3. Copie a URL completa e o cabeçalho `Authorization`.
4. Execute `adalove setup` e cole os valores.

## Estrutura

```
adalove/
  api/         # cliente HTTP para a API da plataforma
  browser/     # captura automática de credenciais via Playwright
  config/      # carregamento de config.json e lista de disciplinas
  filters/     # filtragem de atividades por semana/disciplina/professor
  models/      # Activity, StudentStatus, DashboardMetrics
  writers/     # geração dos arquivos Markdown de saída
cli/
  main.py      # entry-point Typer com menus interativos (Rich + questionary)
output/        # arquivos gerados (gitignored)
tests/         # testes unitários (pytest)
```
