# Identificação de atividades e exportações do dashboard

## Como as atividades são identificadas e classificadas

Depois da autenticação, todos os dados vêm de uma única requisição HTTP a um endpoint REST da API (`apiv2.inteli.edu.br/.../userdata`), que devolve um JSON puro contendo, no campo `activities`, uma lista única com todas as atividades do módulo (aulas, autoestudos, ponderadas, artefatos de projeto, encontros), tudo misturado, sem nenhum campo que diga explicitamente "isso é uma ponderada" ou "isso é um encontro".

Por isso surgiu a necessidade de procurar, entre os campos brutos que cada atividade traz, um identificador confiável que separe os tipos entre si. Encontrei esse identificador no campo numérico `type`, mas ele vem sem rótulo nenhum e precisei criar critérios que fossem confiáveis o suficiente para categorizar as atividades corretamente.

A confiança no output vem, portanto, de uma descoberta empírica que uniu evidências de vários lugares: a legenda dos próprios cards evidenciou o `type 11` (todo card com "Autoestudo" no título era sempre desse tipo), e o badge "Atividade ponderada: X pontos" que a interface mostra pra cada nota evidenciou o `gradeWeight` como critério complementar para separar os autoestudos ponderados dos não ponderados. Além disso, a presença de datas foi o diferencial que separou os cards de encontro de todos os outros, sendo eles identificados com `type 1` ou `type 2`. Os artefatos de projeto, por sua vez, foram identificados pelo `type 21` — o único valor que aparece exclusivamente nas semanas pares do módulo, exatamente a cadência das entregas de sprint.

Cruzando essas pistas, cheguei aos cinco valores abaixo.

| Identificação | Classificação | Utilizado em |
|---|---|---|
| `type == 1` | Encontro de **projeto** | Dashboard (aba Calendário) |
| `type == 2` | Encontro de **instrução** | Dashboard (abas Calendário e Prova, seção Instruções agrupada por sprint) |
| `type == 11` e `gradeWeight > 0` | **Ponderadas** | Dashboard (abas Ponderadas e Calendário), `adalove fetch` (marca "(Ponderada)" nos resultados) e Progresso |
| `type == 11` e `gradeWeight <= 0` | **Autoestudo** | Dashboard (aba Prova, seção Autoestudo) e Progresso |
| `type == 21` | **Artefato de projeto** | Dashboard (abas Projeto e Calendário, linha/coluna de Artefatos) |

Qualquer alteração não documentada que a Adalove fizer nesses valores pode quebrar essa classificação sem aviso e gerar outputs incorretos. Por isso, no caso de inconsistência, sugiro fazer a checagem desses identificadores.

Alguns campos usados em métricas do Progresso (`Activity.status == 3` para autoestudo "concluído", e a fórmula de nota necessária na prova) seguem a mesma lógica de suposição empírica, mas ainda não foram checados com a mesma profundidade — ver comentários em `adalove/models/dashboard_metrics.py`.

## Exportações do dashboard (botões "Exportar dados")

A opção **Abrir Dashboard** do menu gera um único arquivo `dashboard.html` autocontido (sem dependências externas, funciona offline) e abre ele no navegador. Cada uma das quatro abas do dashboard — Calendário, Projeto, Prova e Ponderadas — tem seu próprio botão de exportação, discreto no rodapé da página, que baixa um arquivo `.md` com o mesmo conteúdo e formato produzido pelos writers internos do projeto (`adalove/writers/calendario.py`, `project.py`, `subject_links.py` e `ponderadas.py`). Como o `dashboard.html` não tem servidor por trás (é só um arquivo aberto localmente no navegador), esses `.md` são remontados inteiramente em JavaScript a partir dos dados já embutidos na própria página, sem chamar os writers em Python — a paridade de formato entre os dois lados é verificada manualmente a cada mudança.

| Aba | Arquivo baixado | Conteúdo |
|---|---|---|
| **Calendário** | `calendario.md` | Resumo do módulo por semana (ponderadas + composição por disciplina) e o cronograma de encontros por sprint, com a listagem de ponderadas de cada sprint — mesmo formato de `writers/calendario.py`. |
| **Projeto** | `projeto.md` | Todos os artefatos do projeto, organizados por sprint — mesmo formato do arquivo consolidado de `writers/project.py`. |
| **Prova** | `prova-<disciplina>.md` | Só a disciplina selecionada no momento na navegação à esquerda da aba (não todas de uma vez) — Instruções por sprint, Autoestudo, Links e Referências a livros, no mesmo formato de `writers/subject_links.py`. O nome do arquivo muda conforme a disciplina escolhida (ex: `prova-matemática.md`). |
| **Ponderadas** | `ponderadas.md` | Todas as ponderadas por semana, com título, professor, peso e descrição — mesmo formato de `writers/ponderadas.py`. |

A aba **Turma** não tem botão de exportação — ela só mostra, na própria tela, os dados da turma (módulo, orientador(a), grupo, data da sessão) e o mapeamento disciplina → professor(es).
