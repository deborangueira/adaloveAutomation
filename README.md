# Adalove CLI

Uma ferramenta de linha de comando que conecta direto na API da **Adalove** e transforma o que você já vê na plataforma em um matérial único que facilita a consulta das informações do módulo atual. O objetivo é tornar extremamente fácil a organização pessoal do seu Notion, calendário ou listas de links de autoestudo. 

## Por que isso existe

A vontade de criar algo assim surgiu do trabalho que senti ao organizar o material de um módulo: buscar os cards e copiar/colar suas informações é um trabalho repetitivo e cansativo.Esse CLI automatiza tudo isso. Você roda um comando, escolhe uma opção no menu, e em segundos tem:

- **O calendário de aulas e ponderadas separados por sprint**
- **Todos os assuntos e lista de links de autoestudos das 8 primeiras semanas para estudar para a prova**
- **Lista de todos os artefatos do projeto organizados por sprint**
- **Um resumo do seu progresso acadêmico** direto no terminal (frequência, nota acumulada, nota necessária na prova).

Todas as informações que geram output são exportadas para uma pasta de sua escolha no seu computador.

## O que você consegue fazer

| Opção do menu | O que gera |
|---|---|
| **Turma** | Mostra a turma, módulo e professores da sessão atual — pra você confirmar que está vendo os dados certos antes de exportar qualquer coisa. |
| **Exportar tudo** | Gera Calendário, Projeto, Prova e Ponderadas de uma vez só, numa única busca. |
| **Material › Calendário** | Todos os encontros da turma (aulas e encontros de projeto), agrupados por sprint, com a disciplina de cada aula colorida e as ponderadas daquela sprint listadas junto. |
| **Material › Projeto** | Os artefatos de "Desenvolvimento de Projeto" — um arquivo por sprint, mais um consolidado com tudo. |
| **Material › Prova** | Um arquivo por disciplina com os assuntos e links das 8 primeiras semanas — ideal pra revisar antes da prova do módulo. |
| **Material › Ponderadas** | As atividades que valem nota (professor, peso e critério de avaliação), separadas por semana, mais um consolidado. |
| **Material › Buscar** | Filtro livre por semana(s) e disciplina(s), com três formatos de saída (só link, só descrição, ou os dois juntos). |
| **Dashboard** | Resumo do progresso no terminal: nota acumulada, nota até o momento, nota necessária na prova, semana atual e frequência (com gráfico de pizza em ASCII). |
| **Setup** | Configura suas credenciais e o mapeamento de professor → disciplina. Normalmente você só faz isso uma vez. |

Em qualquer exportação, o CLI abre um seletor de pasta nativo do macOS perguntando onde salvar os arquivos — se você cancelar, ele usa a pasta `output/` do próprio projeto. Ao final, a pasta escolhida já abre sozinha no Finder.

## Instalação

```bash
git clone <repo>
cd adaloveAutomation
python -m venv .venv && source .venv/bin/activate
pip install -e .

# recomendado: captura automática de credenciais pelo navegador
pip install playwright && playwright install chromium
```

## Uso

```bash
adalove          # menu interativo principal
adalove setup    # (re)configurar credenciais
adalove fetch    # ir direto pro filtro livre (Buscar)
```

Na primeira execução, escolha **Setup**. A partir daí, é só abrir `adalove` e navegar pelo menu — todas as opções acima ficam disponíveis ali.

## Como as atividades são identificadas e classificadas

O sistema tem acesso a todos os cards da turma, mas existe a necessidade de identificar que card é de que tipo de atividade. Nesse processo identifiquei que a API da Adalove mostra apenas um campo numérico `type`, sem rótulo nenhum. A confiança no output, contudo, vem de uma descoberta empírica que uniu evidências de vários lugares: a legenda dos próprios cards (todo card com "Autoestudo" no título era sempre `type 11`), as datas reais dos encontros no calendário da Adalove (que bateram exatamente com `type 1` e `type 2`), e o badge "Atividade ponderada: X pontos" que a interface mostra pra cada nota (confirmando o `gradeWeight`). Cruzando essas pistas cheguei nos quatro valores abaixo.

| Identificação | Classificação | Utilizado no menu em |
|---|---|---|
| `type == 1` | **Encontro de projeto** | Material › Calendário e Exportar tudo |
| `type == 2` | **Encontro de instrução** | Material › Calendário, Material › Prova (seção Instruções, agrupada por sprint) e Exportar tudo |
| `type == 11` e `gradeWeight > 0` | **Ponderadas** | Material › Ponderadas, Material › Calendário, Material › Buscar (marca "(Ponderada)" nos resultados), Exportar tudo e Dashboard |
| `type == 11` e `gradeWeight <= 0` | **Autoestudo** | Material › Prova (seção Autoestudo), Exportar tudo e Dashboard |

Qualquer alteração não documentada da Adalove nesses valores pode quebrar essa classificação sem aviso e gerar outputs incorretos.

## Credenciais: como funciona por baixo dos panos

No seu primeiro acesso o Setup abre um navegador dedicado (via Playwright), separado do seu navegador do dia a dia, e nele:

1. Uma janela abre pedindo login — você loga normalmente (inclusive via Google).
2. O CLI navega até a página que dispara a chamada da API e intercepta a URL e o token automaticamente.
3. Da próxima vez, a sessão já está salva nesse perfil: a captura roda sozinha, sem precisar logar de novo.

Os tokens da Adalove expiram a cada 1 hora. Sempre que isso acontece, o CLI percebe e recaptura sozinho antes mesmo de tentar a requisição, você não vê erro nenhum, só uma mensagem avisando que está renovando.

Se preferir configurar manualmente (ex: Playwright não instalado):

1. Abra o Adalove no navegador e faça login.
2. Na aba **Rede** do DevTools, localize uma requisição para `apiv2.inteli.edu.br`.
3. Copie a URL completa e o valor do cabeçalho `Authorization`.
4. Execute `adalove setup` e cole os valores quando pedido.

## Estrutura dos arquivos gerados

Caso você não escolha uma pasta para receber os materiais solicitados, tudo cai em `output/<turma>/`, onde `<turma>` é o identificador que a própria Adalove usa pra sua sessão (ex: `2026-2A-T17`) — assim, o material de turmas diferentes nunca se mistura:

```
output/
  2026-2A-T17/
    calendario.md          # Material › Calendário
    projeto/                # Material › Projeto
      projeto.md
      sprint-1.md ... sprint-5.md
    prova/                  # Material › Prova
      matemática.md, programação.md, ...
    ponderadas/              # Material › Ponderadas
      ponderadas.md
      semana-01.md, semana-02.md, ...
    buscar/                  # Material › Buscar
      <disciplina>_semana-<semanas>_<modo>.md
```

## Estrutura do projeto

```
adalove/
  api/         # cliente HTTP para a API da Adalove (adalove/api/client.py)
  browser/     # captura automática de credenciais via Playwright
  config/      # config.json, lista de disciplinas, cores e mapeamento de eixo
  filters/     # filtragem e classificação de atividades (semana, disciplina,
               # artefatos de projeto, ponderadas, encontros do calendário)
  models/      # Activity, SectionInfo, StudentStatus, DashboardMetrics
  writers/     # geração de cada arquivo Markdown de saída
cli/
  main.py      # entry-point Typer com os menus interativos (Rich + questionary)
tests/         # testes unitários (pytest)
output/        # arquivos gerados (gitignored)
```

## Rodando os testes

```bash
pytest -q
```
