# Adalove CLI

A Adalove concentra todas as informações acadêmicas do módulo, mas nem sempre é fácil enxergar o panorama completo. Se você quiser organizar seu calendário, entender quais sprints vão exigir mais tempo ou simplesmente levar essas informações para o Notion, por exemplo, acaba precisando navegar por dezenas de cards e copiar tudo manualmente.

Foi dessa necessidade que surgiu o **Adalove CLI**. No começo, a ideia era simplesmente facilitar meu próprio planejamento de estudos, reunindo os materiais para a prova e me dando uma visão mais clara da carga de cada sprint. Com o tempo, outras funcionalidades foram sendo adicionadas, transformando a ferramenta em um apoio para acompanhar o módulo de forma mais simples.

Hoje, esse CLI se conecta diretamente à API da **Adalove** e reúne essas informações em uma visão consolidada, organizada e fácil de consultar. Em poucos segundos, você consegue gerar:

* **Calendário de aulas e ponderadas**, separado por sprint.
* **Todos os assuntos e links de autoestudo** das oito primeiras semanas, facilitando a preparação para a prova.
* **Lista de todos os artefatos do projeto**, organizada por sprint.
* **Resumo do progresso acadêmico**, com frequência, nota acumulada e nota necessária na prova.

Fora o resumo do Dashboard, que aparece direto no terminal, todo o conteúdo gerado é exportado em **Markdown** para uma pasta de sua escolha, facilitando a organização em ferramentas como Notion, Obsidian ou qualquer editor de texto.


## O que você consegue fazer

| Opção do menu | O que gera | Output |
|---|---|---|
| **Turma** | Turma, módulo e professores | só terminal |
| **Exportar tudo** | Gera de uma vez as opções com \* abaixo| conjunto completo |
| **Material › Calendário** \* | Encontros e ponderadas organizados por sprint | Um arquivo |
| **Material › Projeto** \* | Todos os artefatos do projeto | 6 arquivos (por sprint + unificado) |
| **Material › Prova** \* | Assuntos e links das 8 primeiras semanas | 5 arquivos (por disciplina) |
| **Material › Ponderadas** \* | Todas as ponderadas | por semana + unificado |
| **Material › Buscar** | Filtro livre por semana/disciplina | por disciplina |
| **Dashboard** | Progresso acadêmico | só terminal |
| **Setup** | Credenciais e disciplinas | - |

Em qualquer exportação, o CLI abre um seletor de pasta nativo do macOS perguntando onde salvar os arquivos, se você cancelar, ele usa a pasta `output/` do próprio projeto. Ao final, a pasta escolhida já abre sozinha no Finder.

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

Depois da autenticação, todos os dados vêm de uma única requisição HTTP a um endpoint REST da API (`apiv2.inteli.edu.br/.../userdata`), que devolve um JSON puro contendo, no campo `activities`, uma lista única com todas as atividades do módulo (aulas, autoestudos, ponderadas, artefatos de projeto, encontros), tudo misturado, sem nenhum campo que diga explicitamente "isso é uma ponderada" ou "isso é um encontro". 

Por isso surgiu a necessidade de procurar, entre os campos brutos que cada atividade traz, um identificador confiável que separe os tipos entre si. Encontrei esse identificador no campo numérico `type`, mas ele vem sem rótulo nenhum e precisei criar critérios que fossem confiáveis o suficiente para categorizar as atividades corretamente. 

A confiança no output vem, portanto, de uma descoberta empírica que uniu evidências de vários lugares: a legenda dos próprios cards evidenciou o `type 11` (todo card com "Autoestudo" no título era sempre desse tipo), e o badge "Atividade ponderada: X pontos" que a interface mostra pra cada nota evidenciou o `gradeWeight` como critério complementar para separar os autoestudos ponderados dos não ponderados. Além disso, a presença de datas foi o diferencial que separou os cards de encontro de todos os outros, sendo eles identificados com `type 1` ou `type 2`. 

Cruzando essas pistas, cheguei aos quatro valores abaixo.

| Identificação | Classificação | Utilizado no menu em |
|---|---|---|
| `type == 1` | Encontro de **projeto** | Material › Calendário e Exportar tudo |
| `type == 2` | Encontro de **instrução** | Material › Calendário, Material › Prova (seção Instruções, agrupada por sprint) e Exportar tudo |
| `type == 11` e `gradeWeight > 0` | **Ponderadas** | Material › Ponderadas, Material › Calendário, Material › Buscar (marca "(Ponderada)" nos resultados), Exportar tudo e Dashboard |
| `type == 11` e `gradeWeight <= 0` | **Autoestudo** | Material › Prova (seção Autoestudo), Exportar tudo e Dashboard |

Qualquer alteração não documentada que a Adalove fizer nesses valores pode quebrar essa classificação sem aviso e gerar outputs incorretos. Por isso, no caso de inconsistência, sugiro fazer a checagem desses identificadores.

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

## Créditos

Este projeto foi desenvolvido a partir da base disponibilizada por **Rafael Josué** em um repositório público próprio, que implementava a estrutura inicial do CLI (cliente da API, filtros e modelos) e o processo de captura de credenciais utilizando Playwright. A partir dessa fundação, expandi a solução, desenvolvendo a automação e as funcionalidades que compõem a versão atual do projeto.