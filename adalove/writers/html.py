import json
import re
from collections import defaultdict
from datetime import date, datetime, timedelta
from html import escape
from pathlib import Path

from adalove.config.subjects import SUBJECT_COLORS
from adalove.filters.activity import (
    ENCONTRO_LABELS,
    get_autoestudos,
    get_encontros,
    get_ponderadas,
    get_project_artifacts,
    infer_teacher_subjects,
    sprint_number,
)
from adalove.models.activity import Activity
from adalove.models.section_info import SectionInfo

OUTPUT_DIR = Path(__file__).parent.parent.parent / "output"
_UNKNOWN_TURMA = "turma-desconhecida"
_INSTRUCAO_LABEL = "Instrução"

# Same empirically-confirmed 3h display offset used in writers/calendario.py.
_DISPLAY_OFFSET = timedelta(hours=3)

_BOOK_KEYWORDS = ("sophia", "minhabiblioteca", "minha-biblioteca", "bibliografiainterativa")
_EXCLUDED_DOMAINS = ("inteli.edu.br",)

# Same first-8-weeks scope cli/main.py's _MODO_PROVA_WEEKS applies before
# calling write_subject_links_md — the Prova tab covers what "Material ›
# Prova" always has (assuntos e links das 8 primeiras semanas), not the whole
# module.
_PROVA_WEEKS = range(1, 9)

_PLANNING_RE = re.compile(r"planning\s*(\d+)", re.IGNORECASE)
_REVIEW_RE = re.compile(r"review.*?(\d+)", re.IGNORECASE)
_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")


def _format_date(date_str: str) -> str:
    if not date_str:
        return ""
    dt = datetime.fromisoformat(date_str.replace("Z", "+00:00")) + _DISPLAY_OFFSET
    return dt.strftime("%d/%m/%Y")


def _short_projeto_title(caption: str) -> str:
    m = _PLANNING_RE.search(caption)
    if m:
        return f"Planning {m.group(1)}"
    m = _REVIEW_RE.search(caption)
    if m:
        return f"Review {m.group(1)}"
    return caption.strip()


def _is_book_ref(url: str) -> bool:
    lower = url.lower()
    return any(k in lower for k in _BOOK_KEYWORDS)


def _is_excluded_url(url: str) -> bool:
    lower = url.lower()
    return any(domain in lower for domain in _EXCLUDED_DOMAINS)


def _md_to_html(text: str) -> str:
    """Minimal renderer for the light markdown produced by
    Activity.description_markdown/avaliacao_markdown (bold via **, "- "
    bullets, blank-line paragraphs) — just enough to display that text safely,
    not a general markdown parser. Escapes first, so bold/list markers are the
    only markup that survives into the output HTML."""
    if not text:
        return ""
    blocks = []
    for para in text.split("\n\n"):
        lines = [line for line in para.split("\n") if line.strip()]
        if not lines:
            continue
        if all(line.startswith("- ") for line in lines):
            rendered_items = [_BOLD_RE.sub(r"<strong>\1</strong>", escape(line[2:])) for line in lines]
            items = "".join(f"<li>{item}</li>" for item in rendered_items)
            blocks.append(f"<ul>{items}</ul>")
        else:
            html_line = "<br>".join(_BOLD_RE.sub(r"<strong>\1</strong>", escape(line)) for line in lines)
            blocks.append(f"<p>{html_line}</p>")
    return "".join(blocks)


def _build_resumo(
    activities: list[Activity],
    encontros: list[Activity],
    ponderadas: list[Activity],
    artifacts: list[Activity],
    subjects_by_teacher: dict[str, str],
) -> list[dict]:
    ponderadas_by_week: dict[int, list[Activity]] = defaultdict(list)
    for a in ponderadas:
        ponderadas_by_week[a.folder_number].append(a)

    instrucao_by_week: dict[int, list[Activity]] = defaultdict(list)
    for a in encontros:
        if ENCONTRO_LABELS.get(a.type) == _INSTRUCAO_LABEL:
            instrucao_by_week[a.folder_number].append(a)

    artifacts_by_week: dict[int, list[Activity]] = defaultdict(list)
    for a in artifacts:
        artifacts_by_week[a.folder_number].append(a)

    weeks = []
    for w in sorted({a.folder_number for a in activities}):
        week_ponderadas = ponderadas_by_week.get(w, [])
        ponderadas_subjects = sorted({
            subjects_by_teacher.get(a.professor_name, "") or a.professor_name for a in week_ponderadas
        })

        counts: dict[str, int] = defaultdict(int)
        first_seen: dict[str, str] = {}
        for a in sorted(instrucao_by_week.get(w, []), key=lambda a: a.date):
            subject = subjects_by_teacher.get(a.professor_name, "") or a.professor_name
            counts[subject] += 1
            first_seen.setdefault(subject, a.date)
        total = sum(counts.values())
        composicao = (
            [{"subject": s, "fraction": counts[s] / total} for s in sorted(counts, key=lambda s: first_seen[s])]
            if total
            else []
        )

        weeks.append({
            "week": w,
            "ponderadasSubjects": ponderadas_subjects,
            "composicao": composicao,
            "artifactCount": len(artifacts_by_week.get(w, [])),
        })
    return weeks


def _build_sprints(
    encontros: list[Activity], ponderadas: list[Activity], subjects_by_teacher: dict[str, str]
) -> list[dict]:
    encontros_by_sprint: dict[int, list[Activity]] = defaultdict(list)
    for a in encontros:
        encontros_by_sprint[sprint_number(a.folder_number)].append(a)

    ponderadas_by_sprint: dict[int, list[Activity]] = defaultdict(list)
    for a in ponderadas:
        ponderadas_by_sprint[sprint_number(a.folder_number)].append(a)

    sprints = []
    for sprint in sorted(set(encontros_by_sprint) | set(ponderadas_by_sprint)):
        items = []
        for a in encontros_by_sprint.get(sprint, []):
            tipo = ENCONTRO_LABELS.get(a.type, "")
            if tipo == _INSTRUCAO_LABEL:
                subject = subjects_by_teacher.get(a.professor_name, "")
                items.append({
                    "date": _format_date(a.date),
                    "week": a.folder_number,
                    "subject": subject or None,
                    "label": subject or tipo,
                    "title": a.caption.strip(),
                })
            else:
                items.append({
                    "date": _format_date(a.date),
                    "week": a.folder_number,
                    "subject": None,
                    "label": None,
                    "title": _short_projeto_title(a.caption),
                })

        sprint_ponderadas = [
            {
                "subject": subjects_by_teacher.get(a.professor_name, "") or a.professor_name,
                "weight": a.grade_weight,
                "week": a.folder_number,
                "title": a.caption.strip(),
            }
            for a in ponderadas_by_sprint.get(sprint, [])
        ]
        sprints.append({"number": sprint, "encontros": items, "ponderadas": sprint_ponderadas})
    return sprints


def _build_projeto(artifacts: list[Activity]) -> list[dict]:
    grouped: dict[int, list[Activity]] = defaultdict(list)
    for a in artifacts:
        grouped[a.folder_number].append(a)

    return [
        {
            "sprint": sprint_number(week_num),
            "week": week_num,
            "artifacts": [
                {
                    "caption": a.caption.strip(),
                    "html": _md_to_html(a.description_markdown),
                    # Raw markdown alongside the rendered HTML — the "Exportar
                    # dados" button rebuilds projeto.md client-side from this,
                    # since the page has no server to call write_project_md.
                    "descriptionMarkdown": a.description_markdown,
                }
                for a in acts
            ],
        }
        for week_num, acts in sorted(grouped.items())
    ]


def _build_prova(activities: list[Activity], teacher_subjects: dict[str, str]) -> list[dict]:
    by_subject: dict[str, list[Activity]] = defaultdict(list)
    for a in activities:
        subject = teacher_subjects.get(a.professor_name, "")
        if subject and subject != "Não presente no módulo":
            by_subject[subject].append(a)

    subjects = []
    for subject, acts in sorted(by_subject.items()):
        professors = sorted({a.professor_name for a in acts if a.professor_name})

        instrucoes_by_sprint: dict[int, list[str]] = defaultdict(list)
        for a in acts:
            if a.caption and ENCONTRO_LABELS.get(a.type) == _INSTRUCAO_LABEL:
                titles = instrucoes_by_sprint[sprint_number(a.folder_number)]
                if a.caption not in titles:
                    titles.append(a.caption)

        autoestudo_titles = list(dict.fromkeys(a.caption for a in get_autoestudos(acts) if a.caption))
        links = list(dict.fromkeys(
            a.url for a in acts if a.url and not _is_book_ref(a.url) and not _is_excluded_url(a.url)
        ))
        books = list(dict.fromkeys(
            a.url for a in acts if a.url and _is_book_ref(a.url) and not _is_excluded_url(a.url)
        ))

        subjects.append({
            "name": subject,
            "professors": professors,
            "instrucoesBySprint": [
                {"sprint": s, "titles": titles} for s, titles in sorted(instrucoes_by_sprint.items())
            ],
            "autoestudo": autoestudo_titles,
            "links": links,
            "books": books,
        })
    return subjects


def _build_turma_disciplinas(activities: list[Activity], teacher_subjects: dict[str, str]) -> list[dict]:
    """Same subject → professor(s) grouping as _build_prova, but over every
    activity (not just the first 8 weeks) — this feeds the Turma tab, which
    is about the module's overall structure, not exam scope."""
    by_subject: dict[str, set[str]] = defaultdict(set)
    for a in activities:
        subject = teacher_subjects.get(a.professor_name, "")
        if subject and subject != "Não presente no módulo" and a.professor_name:
            by_subject[subject].add(a.professor_name)
    return [
        {"subject": subject, "professors": sorted(professors)}
        for subject, professors in sorted(by_subject.items())
    ]


def _build_ponderadas(ponderadas: list[Activity], subjects_by_teacher: dict[str, str]) -> list[dict]:
    grouped: dict[int, list[Activity]] = defaultdict(list)
    for a in ponderadas:
        grouped[a.folder_number].append(a)

    return [
        {
            "week": week_num,
            "items": [
                {
                    "caption": a.caption.strip(),
                    "professor": a.professor_name,
                    "subject": subjects_by_teacher.get(a.professor_name, "") or None,
                    "weight": a.grade_weight,
                    "html": _md_to_html(a.avaliacao_markdown),
                    # Raw markdown for the "Exportar dados" button — see the
                    # matching note in _build_projeto.
                    "avaliacaoMarkdown": a.avaliacao_markdown,
                }
                for a in acts
            ],
        }
        for week_num, acts in sorted(grouped.items())
    ]


def _build_data(activities: list[Activity], section: SectionInfo, teacher_subjects: dict[str, str]) -> dict:
    encontros = get_encontros(activities)
    ponderadas = get_ponderadas(activities)
    artifacts = get_project_artifacts(activities)

    # Saved mapping wins; axis-inferred fills in anything not yet configured —
    # same precedence as writers/calendario.py. writers/subject_links.py's
    # equivalent (the Prova tab here) only trusts the saved mapping, so that
    # one stays on the raw teacher_subjects param instead.
    subjects_by_teacher = {**infer_teacher_subjects(activities), **teacher_subjects}

    return {
        "turma": section.section_caption or _UNKNOWN_TURMA,
        "generatedAt": date.today().isoformat(),
        "subjectColors": SUBJECT_COLORS,
        "turmaInfo": {
            "caption": section.section_caption,
            "moduloCaption": section.project_caption,
            "moduloDescricao": section.project_description,
            "orientador": section.advisor_name,
            "grupo": section.group_caption,
            "dataSessao": section.section_date,
            "disciplinas": _build_turma_disciplinas(activities, teacher_subjects),
        },
        "resumo": _build_resumo(activities, encontros, ponderadas, artifacts, subjects_by_teacher),
        "sprints": _build_sprints(encontros, ponderadas, subjects_by_teacher),
        "projeto": _build_projeto(artifacts),
        "prova": _build_prova(
            [a for a in activities if a.folder_number in _PROVA_WEEKS], teacher_subjects
        ),
        "ponderadas": _build_ponderadas(ponderadas, subjects_by_teacher),
    }


def write_html_dashboard(
    activities: list[Activity],
    section: SectionInfo,
    teacher_subjects: dict[str, str],
    output_dir: Path | None = None,
) -> Path:
    """Write a single <output_dir>/<turma>/dashboard.html (output_dir defaults
    to OUTPUT_DIR), overwritten on every run — an interactive, self-contained
    (no external assets, works straight off the filesystem) view over the
    same data as the Calendário/Projeto/Prova/Ponderadas Markdown files, with
    tabs, copy-to-clipboard on project artifacts and Prova links, and a
    per-tab "Exportar dados" button that rebuilds that tab's .md file
    client-side and downloads it (the page has no server to call the writer
    functions directly once it's open in a browser).
    """
    data = _build_data(activities, section, teacher_subjects)
    # The JSON sits inside a <script type="application/json"> tag as inert
    # text, parsed via JSON.parse() in JS — never interpreted as markup or
    # code, so a caption containing "</script>" can't break out of the tag or
    # execute. `\/` is a legal JSON escape for `/`, so this is safe wherever
    # it lands in the payload.
    data_json = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")

    turma_dir = (output_dir or OUTPUT_DIR) / (section.section_caption or _UNKNOWN_TURMA)
    turma_dir.mkdir(parents=True, exist_ok=True)

    path = turma_dir / "dashboard.html"
    path.write_text(_TEMPLATE.replace("__DATA__", data_json), encoding="utf-8")
    return path


_TEMPLATE = r"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Adalove — Dashboard</title>
<style>
:root {
  color-scheme: light dark;
  --bg: #ffffff;
  --bg-alt: #f5f6f8;
  --border: #e2e4e9;
  --text: #1c1f26;
  --text-muted: #6b7280;
  --accent: #4f46e5;
  --card-bg: #ffffff;
  --shadow: 0 1px 3px rgba(0,0,0,0.06);
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #14161b;
    --bg-alt: #1b1e25;
    --border: #2b2f38;
    --text: #e7e9ee;
    --text-muted: #9aa1ad;
    --accent: #8b85ff;
    --card-bg: #1d2028;
    --shadow: 0 1px 3px rgba(0,0,0,0.3);
  }
}
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  background: var(--bg);
  color: var(--text);
  line-height: 1.5;
}
header {
  position: sticky;
  top: 0;
  z-index: 10;
  background: var(--bg);
  border-bottom: 1px solid var(--border);
  padding: .5rem 1.25rem 0;
}
footer {
  text-align: center; color: var(--text-muted); font-size: .75rem;
  padding: 1.5rem 1.25rem 2rem;
}
.tabs { display: flex; gap: .25rem; flex-wrap: wrap; }
.tab {
  border: none;
  background: transparent;
  color: var(--text-muted);
  padding: .55rem .9rem;
  font-size: .9rem;
  cursor: pointer;
  border-bottom: 2px solid transparent;
}
.tab.active { color: var(--accent); border-bottom-color: var(--accent); font-weight: 600; }
.section-actions { margin-bottom: 1rem; }
.export-btn {
  border: 1px solid var(--accent); background: var(--accent); color: #fff;
  border-radius: 6px; padding: .45rem .9rem; font-size: .82rem; cursor: pointer;
}
.export-btn:hover { opacity: .9; }
.kind-filter { display: flex; gap: .4rem; flex-wrap: wrap; margin-bottom: 1rem; }
.kind-filter button {
  border: 1px solid var(--border); background: var(--card-bg); color: var(--text);
  border-radius: 999px; padding: .3rem .8rem; font-size: .8rem; cursor: pointer;
}
.kind-filter button.active { background: var(--accent); color: #fff; border-color: var(--accent); }
.scope-note { color: var(--text-muted); font-size: .78rem; margin: 0 0 1.25rem; }
.split-layout { display: grid; grid-template-columns: 1fr 1px 2fr; gap: 1.5rem; }
.split-nav { display: flex; flex-direction: column; gap: .15rem; }
.split-nav button {
  text-align: left; border: none; background: transparent; color: var(--text-muted);
  padding: .55rem .75rem; font-size: .88rem; cursor: pointer; border-radius: 6px;
}
.split-nav button:hover { background: var(--bg-alt); }
.split-nav button.active { background: var(--accent); color: #fff; font-weight: 600; }
.split-divider { background: var(--border); }
.split-content { min-width: 0; }
@media (max-width: 900px) {
  .split-layout { grid-template-columns: 1fr; }
  .split-divider { display: none; }
  .split-nav { flex-direction: row; flex-wrap: wrap; }
}
.proj-item { margin-bottom: 1.75rem; }
.proj-item-head { display: flex; justify-content: space-between; align-items: flex-start; gap: .5rem; margin-bottom: .6rem; }
.proj-item-head h3 { margin: 0; font-size: 1rem; }
.proj-item-body { position: relative; max-height: 150px; overflow: hidden; }
.proj-item-body.expanded { max-height: none; }
.proj-item-body.collapsible:not(.expanded)::after {
  content: ''; position: absolute; left: 0; right: 0; bottom: 0; height: 56px;
  background: linear-gradient(to bottom, transparent, var(--bg));
  pointer-events: none;
}
.ver-mais-btn {
  display: inline-block; margin-top: .5rem; border: none; background: transparent;
  color: var(--accent); font-size: .8rem; font-weight: 600; cursor: pointer; padding: 0;
}
main { padding: 1.25rem; max-width: 1280px; margin: 0 auto; }
.view { display: none; }
.view.active { display: block; }
.section { margin-bottom: 1.75rem; }
.section h2 { font-size: 1.05rem; margin: 0 0 .75rem; }
.section h3 { font-size: .95rem; margin: 1.25rem 0 .5rem; }
.scroll-x { overflow-x: auto; }
.week-summary { display: flex; flex-direction: column; }
.week-summary-header, .week-row {
  display: grid; grid-template-columns: 2.2rem 5.75rem 1fr 3.5rem; align-items: center; gap: .6rem;
}
.week-summary-header {
  color: var(--text-muted); font-size: .68rem; text-transform: uppercase; letter-spacing: .05em;
  font-weight: 600; padding: 0 .5rem .6rem; border-bottom: 1px solid var(--border);
}
.week-summary-header span:last-child, .week-row .artefatos-cell { text-align: right; }
.week-row {
  padding: .6rem .5rem; border-bottom: 1px solid var(--border); border-radius: 8px;
}
.week-row:last-child { border-bottom: none; }
.week-row:hover { background: var(--bg-alt); }
.week-row .ponderadas-cell { display: flex; flex-wrap: wrap; gap: .3rem; }
.week-row .artefatos-cell { color: var(--text-muted); font-size: .82rem; font-variant-numeric: tabular-nums; }
.week-pill {
  display: inline-flex; align-items: center; justify-content: center;
  width: 1.6rem; height: 1.6rem; border-radius: 50%; background: var(--bg-alt);
  color: var(--text-muted); font-size: .75rem; font-weight: 600; font-variant-numeric: tabular-nums;
}
.bar { display: flex; width: 56px; height: 10px; border-radius: 999px; overflow: hidden; background: var(--bg-alt); }
.bar span { height: 100%; }
.bar span:first-child { border-radius: 999px 0 0 999px; }
.bar span:last-child { border-radius: 0 999px 999px 0; }
.bar span:only-child { border-radius: 999px; }
.badge {
  display: inline-block; padding: .1rem .45rem; border-radius: 999px; font-size: .72rem;
  color: #fff; white-space: nowrap;
}
.badge.neutral { background: var(--text-muted); }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: .75rem; }
.card {
  background: var(--card-bg); border: 1px solid var(--border); border-radius: 10px;
  padding: .85rem 1rem; box-shadow: var(--shadow);
}
.card h3, .card h4 { margin: 0 0 .4rem; font-size: .92rem; }
.card .meta { color: var(--text-muted); font-size: .78rem; margin: 0 0 .4rem; }
.card-head { display: flex; justify-content: space-between; align-items: flex-start; gap: .5rem; }
.card-head h4 { margin: 0; }
.copy-btn {
  flex: none; border: 1px solid var(--border); background: var(--card-bg); color: var(--text-muted);
  border-radius: 6px; padding: .15rem .5rem; font-size: .7rem; cursor: pointer;
}
.copy-btn.copied { color: var(--accent); border-color: var(--accent); }
ul.plain { margin: .3rem 0; padding-left: 1.1rem; font-size: .85rem; }
.info-list { display: grid; grid-template-columns: max-content 1fr; gap: .5rem 1.5rem; margin: 0; font-size: .88rem; }
.info-list dt { color: var(--text-muted); }
.info-list dd { margin: 0; }
ul.encontros { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: .4rem; }
ul.encontros li { font-size: .85rem; display: flex; gap: .5rem; align-items: baseline; }
ul.encontros .date { color: var(--text-muted); font-variant-numeric: tabular-nums; min-width: 5.2rem; flex: none; }
ul.encontros .title { flex: 1 1 auto; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
ul.encontros .badge { flex: none; }
ul.encontros li.divider { display: block; height: 0; padding: 0; margin: .3rem 0; border-top: 1px solid var(--border); }
.links a { display: block; font-size: .8rem; color: var(--accent); word-break: break-all; margin-bottom: .2rem; }
.rich p { margin: .3rem 0; font-size: .85rem; }
.rich ul { margin: .3rem 0; padding-left: 1.1rem; font-size: .85rem; }
.rich strong { font-weight: 600; }
.empty-state { color: var(--text-muted); font-size: .85rem; padding: 1rem 0; }
</style>
</head>
<body>
<header>
  <div class="tabs">
    <button class="tab" data-view="calendario">Calendário</button>
    <button class="tab" data-view="projeto">Projeto</button>
    <button class="tab" data-view="prova">Prova</button>
    <button class="tab" data-view="ponderadas">Ponderadas</button>
    <button class="tab" data-view="turma">Turma</button>
  </div>
</header>
<main>
  <section class="view" id="view-calendario">
    <div class="section-actions"><button class="export-btn" id="export-calendario">Exportar dados</button></div>
    <div class="split-layout">
      <div class="week-summary" id="resumo-table"></div>
      <div class="split-divider"></div>
      <div class="split-content" id="sprints"></div>
    </div>
  </section>
  <section class="view" id="view-projeto">
    <div class="section-actions"><button class="export-btn" id="export-projeto">Exportar dados</button></div>
    <div class="split-layout">
      <nav class="split-nav" id="projeto-nav"></nav>
      <div class="split-divider"></div>
      <div class="split-content" id="projeto-content"></div>
    </div>
  </section>
  <section class="view" id="view-prova">
    <div class="section-actions"><button class="export-btn" id="export-prova">Exportar dados</button></div>
    <div class="split-layout">
      <nav class="split-nav" id="prova-nav"></nav>
      <div class="split-divider"></div>
      <div class="split-content">
        <div class="kind-filter" id="prova-kind-filter">
          <button class="active" data-kind="instrucoes">Instruções</button>
          <button data-kind="autoestudo">Autoestudo</button>
          <button data-kind="links">Links</button>
        </div>
        <p class="scope-note">Conteúdo das 8 primeiras semanas do módulo.</p>
        <div id="prova-content"></div>
      </div>
    </div>
  </section>
  <section class="view" id="view-ponderadas">
    <div class="section-actions"><button class="export-btn" id="export-ponderadas">Exportar dados</button></div>
    <div id="ponderadas"></div>
  </section>
  <section class="view" id="view-turma">
    <div class="section">
      <h2 id="turma-caption"></h2>
      <dl class="info-list" id="turma-details"></dl>
    </div>
    <div class="section">
      <h2>Disciplinas → Professores</h2>
      <ul class="plain" id="turma-disciplinas"></ul>
    </div>
  </section>
</main>
<footer>
  <span id="turma-name"></span> · Gerado em <span id="generated-at"></span>
</footer>
<script id="data" type="application/json">__DATA__</script>
<script>
const DATA = JSON.parse(document.getElementById('data').textContent);
const el = (tag, cls, text) => {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text !== undefined) n.textContent = text;
  return n;
};
const subjectColor = (name) => DATA.subjectColors[name] || null;

function badge(label, subject) {
  const b = el('span', 'badge', label);
  const color = subject ? subjectColor(subject) : null;
  if (color) { b.style.background = color; } else { b.classList.add('neutral'); }
  return b;
}

function richHtml(container, html) {
  const wrap = el('div', 'rich');
  wrap.innerHTML = html || '';
  container.appendChild(wrap);
}

function plainText(html) {
  const tmp = document.createElement('div');
  tmp.innerHTML = html || '';
  return (tmp.innerText || tmp.textContent || '').trim();
}

function fallbackCopy(text, done) {
  const ta = document.createElement('textarea');
  ta.value = text;
  ta.style.position = 'fixed';
  ta.style.opacity = '0';
  document.body.appendChild(ta);
  ta.focus();
  ta.select();
  try { document.execCommand('copy'); } catch (e) { /* clipboard unavailable */ }
  document.body.removeChild(ta);
  done();
}

function copyText(text, btn) {
  const original = btn.textContent;
  const done = () => {
    btn.textContent = 'Copiado!';
    btn.classList.add('copied');
    setTimeout(() => { btn.textContent = original; btn.classList.remove('copied'); }, 1200);
  };
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).then(done).catch(() => fallbackCopy(text, done));
  } else {
    fallbackCopy(text, done);
  }
}

function downloadText(filename, content) {
  const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = el('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

document.getElementById('turma-name').textContent = DATA.turma;
document.getElementById('generated-at').textContent = DATA.generatedAt;

// ── Resumo do módulo (transposto: semanas viram linhas) ───────────────────
const SUBJECT_ABBR = {
  'Programação': 'Prog', 'Matemática': 'Mat', 'Negócios': 'Neg',
  'Liderança': 'Lid', 'UX': 'UX', 'Orientação': 'Orient',
};
const subjectAbbr = (name) => SUBJECT_ABBR[name] || name;

(function renderResumo() {
  const root = document.getElementById('resumo-table');

  const header = el('div', 'week-summary-header');
  ['', 'Composição', 'Ponderadas', 'Artefatos'].forEach(h => header.appendChild(el('span', null, h)));
  root.appendChild(header);

  DATA.resumo.forEach(w => {
    const row = el('div', 'week-row');
    row.appendChild(el('span', 'week-pill', String(w.week)));

    const compCell = el('div');
    if (w.composicao.length) {
      const bar = el('div', 'bar');
      w.composicao.forEach(seg => {
        const s = el('span');
        s.style.width = (seg.fraction * 100) + '%';
        s.style.background = subjectColor(seg.subject) || 'var(--text-muted)';
        s.title = seg.subject;
        bar.appendChild(s);
      });
      compCell.appendChild(bar);
    }
    row.appendChild(compCell);

    const pondCell = el('div', 'ponderadas-cell');
    w.ponderadasSubjects.forEach(s => pondCell.appendChild(badge(subjectAbbr(s), s)));
    row.appendChild(pondCell);

    row.appendChild(el('span', 'artefatos-cell', w.artifactCount ? String(w.artifactCount) : '–'));
    root.appendChild(row);
  });
})();

// ── Sprints (Calendário) ────────────────────────────────────────────────
(function renderSprints() {
  const root = document.getElementById('sprints');
  DATA.sprints.forEach(sprint => {
    const section = el('div', 'section');
    section.appendChild(el('h3', null, `Sprint ${sprint.number}`));

    const list = el('ul', 'encontros');
    let prevWeek = null;
    sprint.encontros.forEach(item => {
      if (prevWeek !== null && item.week !== prevWeek) list.appendChild(el('li', 'divider'));
      prevWeek = item.week;
      const li = el('li');
      li.appendChild(el('span', 'date', item.date));
      if (item.label) li.appendChild(badge(item.label, item.subject));
      const titleSpan = el('span', 'title', item.title);
      titleSpan.title = item.title;
      li.appendChild(titleSpan);
      list.appendChild(li);
    });
    section.appendChild(list);
    root.appendChild(section);
  });
})();

// ── Projeto ──────────────────────────────────────────────────────────────
(function renderProjeto() {
  const navRoot = document.getElementById('projeto-nav');
  const contentRoot = document.getElementById('projeto-content');
  if (!DATA.projeto.length) {
    document.querySelector('#view-projeto .split-divider').style.display = 'none';
    contentRoot.appendChild(el('div', 'empty-state', 'Nenhum artefato de projeto encontrado.'));
    return;
  }

  // Only adds the "Ver tudo" toggle (and the fade) when the collapsed body
  // actually clips content — short artifacts stay as-is, nothing to expand.
  function makeExpandable(body) {
    requestAnimationFrame(() => {
      if (body.scrollHeight <= body.clientHeight + 4) return;
      body.classList.add('collapsible');
      const toggle = el('button', 'ver-mais-btn', 'Ver tudo');
      toggle.type = 'button';
      toggle.addEventListener('click', () => {
        const expanded = body.classList.toggle('expanded');
        toggle.textContent = expanded ? 'Ver menos' : 'Ver tudo';
      });
      body.after(toggle);
    });
  }

  function renderContent(sprint) {
    contentRoot.innerHTML = '';
    sprint.artifacts.forEach(a => {
      const item = el('article', 'proj-item');
      const head = el('div', 'proj-item-head');
      head.appendChild(el('h3', null, a.caption));
      const copyBtn = el('button', 'copy-btn', 'Copiar');
      copyBtn.type = 'button';
      copyBtn.addEventListener('click', () => {
        const text = a.html ? `${a.caption}\n\n${plainText(a.html)}` : a.caption;
        copyText(text, copyBtn);
      });
      head.appendChild(copyBtn);
      item.appendChild(head);

      const body = el('div', 'proj-item-body');
      richHtml(body, a.html);
      item.appendChild(body);
      contentRoot.appendChild(item);
      makeExpandable(body);
    });
  }

  DATA.projeto.forEach((sprint, i) => {
    const btn = el('button', i === 0 ? 'active' : null, `Sprint ${sprint.sprint}`);
    btn.type = 'button';
    btn.addEventListener('click', () => {
      navRoot.querySelectorAll('button').forEach(b => b.classList.toggle('active', b === btn));
      renderContent(sprint);
    });
    navRoot.appendChild(btn);
  });

  // The Projeto tab starts hidden (display:none), where scrollHeight reads
  // as 0 — makeExpandable's overflow check would always come up empty. Defer
  // the first render until the tab is actually visible, so the measurement
  // reflects real layout.
  let initialized = false;
  document.querySelector('.tab[data-view="projeto"]').addEventListener('click', () => {
    if (!initialized) {
      initialized = true;
      renderContent(DATA.projeto[0]);
    }
  });
})();

// ── Prova ────────────────────────────────────────────────────────────────
(function renderProva() {
  const navRoot = document.getElementById('prova-nav');
  const contentRoot = document.getElementById('prova-content');
  if (!DATA.prova.length) {
    document.querySelector('#view-prova .split-divider').style.display = 'none';
    document.querySelector('#view-prova .kind-filter').style.display = 'none';
    contentRoot.appendChild(el('div', 'empty-state', 'Nenhuma disciplina mapeada encontrada.'));
    return;
  }

  let currentSubject = DATA.prova[0];
  let currentKind = 'instrucoes';

  function renderContent() {
    contentRoot.innerHTML = '';
    const subj = currentSubject;

    if (currentKind === 'instrucoes') {
      if (!subj.instrucoesBySprint.length) {
        contentRoot.appendChild(el('p', 'empty-state', 'Nenhuma instrução registrada.'));
      } else {
        subj.instrucoesBySprint.forEach(s => {
          contentRoot.appendChild(el('p', 'meta', `Sprint ${s.sprint}`));
          const ul = el('ul', 'plain');
          s.titles.forEach(t => ul.appendChild(el('li', null, t)));
          contentRoot.appendChild(ul);
        });
      }
    } else if (currentKind === 'autoestudo') {
      if (!subj.autoestudo.length) {
        contentRoot.appendChild(el('p', 'empty-state', 'Nenhum autoestudo registrado.'));
      } else {
        const ul = el('ul', 'plain');
        subj.autoestudo.forEach(t => ul.appendChild(el('li', null, t)));
        contentRoot.appendChild(ul);
      }
    } else if (currentKind === 'links') {
      if (subj.links.length) {
        const head = el('div', 'card-head');
        head.appendChild(el('h4', null, 'Links'));
        const copyAllBtn = el('button', 'copy-btn', 'Copiar todos');
        copyAllBtn.type = 'button';
        copyAllBtn.addEventListener('click', () => copyText(subj.links.join('\n'), copyAllBtn));
        head.appendChild(copyAllBtn);
        contentRoot.appendChild(head);
        const div = el('div', 'links');
        subj.links.forEach(u => { const a = el('a', null, u); a.href = u; a.target = '_blank'; a.rel = 'noopener'; div.appendChild(a); });
        contentRoot.appendChild(div);
      } else {
        contentRoot.appendChild(el('p', 'empty-state', 'Nenhum link registrado.'));
      }
      if (subj.books.length) {
        contentRoot.appendChild(el('h4', null, 'Referências a livros'));
        const div = el('div', 'links');
        subj.books.forEach(u => { const a = el('a', null, u); a.href = u; a.target = '_blank'; a.rel = 'noopener'; div.appendChild(a); });
        contentRoot.appendChild(div);
      }
    }
  }

  DATA.prova.forEach((subj, i) => {
    const btn = el('button', i === 0 ? 'active' : null, subj.name);
    btn.type = 'button';
    btn.addEventListener('click', () => {
      navRoot.querySelectorAll('button').forEach(b => b.classList.toggle('active', b === btn));
      currentSubject = subj;
      renderContent();
    });
    navRoot.appendChild(btn);
  });

  const kindButtons = document.querySelectorAll('#prova-kind-filter button');
  kindButtons.forEach(btn => btn.addEventListener('click', () => {
    kindButtons.forEach(b => b.classList.toggle('active', b === btn));
    currentKind = btn.dataset.kind;
    renderContent();
  }));

  renderContent();
})();

// ── Ponderadas ───────────────────────────────────────────────────────────
(function renderPonderadas() {
  const root = document.getElementById('ponderadas');
  if (!DATA.ponderadas.length) { root.appendChild(el('div', 'empty-state', 'Nenhuma ponderada encontrada.')); return; }
  DATA.ponderadas.forEach(week => {
    const section = el('div', 'section');
    section.appendChild(el('h2', null, `Semana ${String(week.week).padStart(2, '0')}`));
    const grid = el('div', 'grid');
    week.items.forEach(item => {
      const card = el('article', 'card');
      card.appendChild(el('h4', null, item.caption));
      const meta = [];
      if (item.professor) meta.push(item.professor);
      meta.push(`${item.weight} pontos`);
      card.appendChild(el('p', 'meta', meta.join(' — ')));
      richHtml(card, item.html);
      grid.appendChild(card);
    });
    section.appendChild(grid);
    root.appendChild(section);
  });
})();

// ── Turma ────────────────────────────────────────────────────────────────
(function renderTurma() {
  const info = DATA.turmaInfo;
  document.getElementById('turma-caption').textContent = info.caption || DATA.turma;

  const dl = document.getElementById('turma-details');
  [
    ['Módulo', info.moduloCaption],
    ['Descrição', info.moduloDescricao],
    ['Orientador(a)', info.orientador],
    ['Grupo', info.grupo],
    ['Data da sessão', info.dataSessao],
  ].forEach(([label, value]) => {
    if (!value) return;
    dl.appendChild(el('dt', null, label));
    dl.appendChild(el('dd', null, value));
  });

  const list = document.getElementById('turma-disciplinas');
  if (!info.disciplinas.length) {
    list.appendChild(el('li', 'empty-state', 'Nenhuma disciplina mapeada encontrada.'));
  } else {
    info.disciplinas.forEach(d => {
      const li = el('li');
      li.appendChild(badge(d.subject, d.subject));
      li.appendChild(document.createTextNode(` ${d.professors.join(', ')}`));
      list.appendChild(li);
    });
  }
})();

// ── Tabs ─────────────────────────────────────────────────────────────────
const tabs = document.querySelectorAll('.tab');
const views = document.querySelectorAll('.view');
function activateTab(name) {
  tabs.forEach(t => t.classList.toggle('active', t.dataset.view === name));
  views.forEach(v => v.classList.toggle('active', v.id === `view-${name}`));
}
tabs.forEach(t => t.addEventListener('click', () => activateTab(t.dataset.view)));
activateTab('calendario');

// ── Exportar dados (rebuilds each tab's .md, matching the writers/*.py
// output, since this static page has no server to call them directly) ─────
const pad2 = (n) => String(n).padStart(2, '0');

function coloredMd(label) {
  const color = subjectColor(label);
  return color ? `_<span style="color:${color}">${label}</span>_` : `_${label}_`;
}

function blocksMd(subject, fraction) {
  const count = Math.max(1, Math.round(fraction * 10));
  const blocks = '█'.repeat(count);
  const color = subjectColor(subject);
  return color ? `<span style="color:${color}">${blocks}</span>` : blocks;
}

function buildCalendarioMd() {
  const lines = ['# Calendário', `> Gerado em: ${DATA.generatedAt}`, '', '---', '', '## Resumo do Módulo', ''];

  const headers = ['', ...DATA.resumo.map(w => `Semana ${pad2(w.week)}`)];
  lines.push(`| ${headers.join(' | ')} |`);
  lines.push(`|${headers.map(() => '---').join('|')}|`);
  lines.push(`| **Ponderadas** | ${DATA.resumo.map(w => w.ponderadasSubjects.map(coloredMd).join(', ')).join(' | ')} |`);
  lines.push(`| **Composição de aulas** | ${DATA.resumo.map(w => w.composicao.map(seg => blocksMd(seg.subject, seg.fraction)).join('')).join(' | ')} |`);
  lines.push(`| **Artefatos** | ${DATA.resumo.map(w => w.artifactCount ? String(w.artifactCount) : '').join(' | ')} |`);
  lines.push('');

  DATA.sprints.forEach(sprint => {
    lines.push(`## Sprint ${sprint.number}`, '');
    sprint.encontros.forEach(item => {
      lines.push(item.label
        ? `- **${item.date}** — ${coloredMd(item.label)} — ${item.title}`
        : `- **${item.date}** — ${item.title}`);
    });
    lines.push('');
    if (sprint.ponderadas.length) {
      lines.push('**Ponderadas:**', '');
      sprint.ponderadas.forEach(p => lines.push(`- ${coloredMd(p.subject)} — ${p.weight} pontos — Semana ${pad2(p.week)}`));
      lines.push('');
    }
  });
  return lines.join('\n');
}

function buildProjetoMd() {
  const lines = ['# Projeto', `> Gerado em: ${DATA.generatedAt}`, '', '---', ''];
  DATA.projeto.forEach(sprint => {
    lines.push(`## Sprint ${sprint.sprint} (Semana ${pad2(sprint.week)})`, '');
    sprint.artifacts.forEach(a => {
      lines.push(`### ${a.caption}`, '');
      if (a.descriptionMarkdown) lines.push(a.descriptionMarkdown, '');
    });
    lines.push('---', '');
  });
  return lines.join('\n');
}

function buildPonderadaCell(item) {
  const parts = [`**Título:** ${item.caption}`];
  if (item.professor) parts.push(`**Professor:** ${item.professor}`);
  parts.push(`**Peso:** ${item.weight} pontos`);
  if (item.avaliacaoMarkdown) parts.push(`**Descrição:** ${item.avaliacaoMarkdown}`);
  return parts.join('<br>').replace(/\|/g, '\\|').replace(/\n/g, '<br>');
}

function buildPonderadasMd() {
  const lines = ['# Ponderadas', `> Gerado em: ${DATA.generatedAt}`, '', '---', ''];
  DATA.ponderadas.forEach(week => {
    lines.push(`## Semana ${pad2(week.week)}`, '', '| Ponderadas |', '|---|');
    week.items.forEach(item => lines.push(`| ${buildPonderadaCell(item)} |`));
    lines.push('');
  });
  return lines.join('\n');
}

function buildProvaMd() {
  const blocks = DATA.prova.map(subj => {
    const lines = [`# ${subj.name}`, '', `> Gerado em: ${DATA.generatedAt}`];
    if (subj.professors.length) lines.push(`> Professor: ${subj.professors.join(', ')}`);
    lines.push('');
    if (subj.instrucoesBySprint.length) {
      lines.push('## Instruções', '');
      subj.instrucoesBySprint.forEach(s => {
        lines.push(`### Sprint ${s.sprint}`, '');
        s.titles.forEach(t => lines.push(`- ${t}`));
        lines.push('');
      });
    }
    if (subj.autoestudo.length) {
      lines.push('## Autoestudo', '');
      subj.autoestudo.forEach(t => lines.push(`- ${t}`));
      lines.push('');
    }
    if (subj.links.length) {
      lines.push('## Links', '');
      subj.links.forEach(u => lines.push(u));
      lines.push('');
    }
    if (subj.books.length) {
      lines.push('## Referências a livros', '');
      subj.books.forEach(u => lines.push(u));
      lines.push('');
    }
    return lines.join('\n');
  });
  return blocks.join('\n---\n\n');
}

document.getElementById('export-calendario').addEventListener('click', () => downloadText('calendario.md', buildCalendarioMd()));
document.getElementById('export-projeto').addEventListener('click', () => downloadText('projeto.md', buildProjetoMd()));
document.getElementById('export-prova').addEventListener('click', () => downloadText('prova.md', buildProvaMd()));
document.getElementById('export-ponderadas').addEventListener('click', () => downloadText('ponderadas.md', buildPonderadasMd()));
</script>
</body>
</html>
"""
