from collections import defaultdict
from datetime import date
from pathlib import Path

from adalove.models.activity import Activity

OUTPUT_DIR = Path(__file__).parent.parent.parent / "output"
_UNKNOWN_TURMA = "turma-desconhecida"

_BOOK_KEYWORDS = ("sophia", "minhabiblioteca", "minha-biblioteca", "bibliografiainterativa")
_EXCLUDED_DOMAINS = ("inteli.edu.br",)


def _is_book_ref(url: str) -> bool:
    lower = url.lower()
    return any(k in lower for k in _BOOK_KEYWORDS)


def _is_excluded_url(url: str) -> bool:
    lower = url.lower()
    return any(domain in lower for domain in _EXCLUDED_DOMAINS)


def write_subject_links_md(
    activities: list[Activity],
    teacher_subjects: dict[str, str],
    turma: str,
) -> list[Path]:
    """Write one .md per subject with all links; Sophia/biblioteca links in a separate section.

    Lands in output/<turma>/prova/, overwritten on every run — this is a
    current snapshot of the module, not a history of past runs.
    """
    today = date.today().isoformat()

    by_subject: dict[str, list[Activity]] = defaultdict(list)
    for a in activities:
        subject = teacher_subjects.get(a.professor_name, "")
        if subject and subject != "Não presente no módulo":
            by_subject[subject].append(a)

    run_dir = OUTPUT_DIR / (turma or _UNKNOWN_TURMA) / "prova"
    run_dir.mkdir(parents=True, exist_ok=True)

    paths: list[Path] = []
    for subject, acts in sorted(by_subject.items()):
        professors = sorted({a.professor_name for a in acts if a.professor_name})
        titles = list(dict.fromkeys(a.caption for a in acts if a.caption))

        links = [(a.caption, a.url) for a in acts if a.url and not _is_book_ref(a.url) and not _is_excluded_url(a.url)]
        books = [(a.caption, a.url) for a in acts if a.url and _is_book_ref(a.url) and not _is_excluded_url(a.url)]

        lines: list[str] = [
            f"# {subject}",
            "",
            f"> Gerado em: {today}",
            f"> Professor: {', '.join(professors)}",
            "",
            "**Assuntos do módulo:**",
            "",
        ]
        for title in titles:
            lines.append(f"- {title}")
        lines.append("")

        if links:
            lines += ["## Links", ""]
            for _, url in links:
                lines.append(url)
            lines.append("")

        if books:
            lines += ["## Referências a livros", ""]
            for _, url in books:
                lines.append(url)
            lines.append("")

        slug = subject.lower().replace(" ", "-")
        path = run_dir / f"{slug}.md"
        path.write_text("\n".join(lines), encoding="utf-8")
        paths.append(path)

    return paths
