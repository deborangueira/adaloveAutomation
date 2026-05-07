# adalove — Design Spec
> 2026-05-07

## Overview

A local CLI tool that fetches activities from the Adalove university platform API, filters them interactively by week and subject, and writes two markdown output files: one with full activity detail and one with links only (for NotebookLM).

---

## Stack

| Concern | Library |
|---|---|
| CLI entry point | `typer` |
| Interactive prompts | `questionary` |
| HTTP | `requests` |
| HTML stripping | `html.parser` (stdlib) |
| Packaging | `pyproject.toml` (editable install) |

Python 3.11+. No database, no ORM, no async.

---

## Folder Structure

```
adaloveAutomation/
├── adalove/
│   ├── __init__.py
│   ├── api/
│   │   ├── __init__.py
│   │   └── client.py        # HTTP session, fetch activities, auth error
│   ├── models/
│   │   ├── __init__.py
│   │   └── activity.py      # Activity dataclass
│   ├── filters/
│   │   ├── __init__.py
│   │   └── activity.py      # filter by week list, subject list
│   ├── output/
│   │   ├── __init__.py
│   │   ├── markdown.py      # writes output/activities.md
│   │   └── links.py         # writes output/links.md
│   └── config/
│       ├── __init__.py
│       ├── subjects.py      # hardcoded subjects list
│       └── settings.py      # load/save config.json
├── cli/
│   ├── __init__.py
│   └── main.py              # typer app, two commands: setup + fetch
├── output/                  # generated files (gitignored if ever versioned)
│   ├── activities.md
│   └── links.md
├── config.json              # token + section_uuid + teacher→subject map (never versioned)
├── pyproject.toml
└── requirements.txt
```

Each module has one responsibility and no circular imports:
- `models` — no deps
- `filters` — imports `models` only
- `output` — imports `models` only
- `api` — imports `models` only
- `config` — no deps
- `cli` — imports everything

---

## Data Model

Fields extracted from each activity in the API response:

```python
@dataclass
class Activity:
    uuid: str
    caption: str              # title
    description: str          # HTML, stripped to plain text on read
    url: str                  # basicActivityURL
    professor_name: str       # professorName
    folder_caption: str       # e.g. "Semana 05"
    folder_number: int        # parsed from folderCaption, e.g. 5
    study_type: str           # "class", etc.
    status: int               # 1=pending, 2=done, 3=graded (not used in output)
```

All other fields in the API response are ignored.

---

## Configuration

`config.json` lives in the project root and is never committed:

```json
{
  "api_url": "https://...",
  "section_uuid": "378b2000...",
  "token": "Bearer eyJ...",
  "teacher_subjects": {
    "Fillipe Manoel Xavier Resina": "Programação",
    "Professor Y": "Matemática",
    "Professor Z": "Não presente no módulo"
  }
}
```

`settings.py` exposes `load_config() -> dict` and `save_config(data: dict)`. Both raise clear errors if the file is missing or malformed.

---

## Hardcoded Subjects

Defined in `adalove/config/subjects.py`:

```python
SUBJECTS = [
    "Matemática",
    "UX",
    "Programação",
    "Negócios",
    "Liderança",
    "Orientação",
    "Não presente no módulo",
]
```

---

## CLI Commands

### `adalove setup`

Linear wizard using `questionary`. Steps:

1. Prompt: API URL
2. Prompt: Section UUID
3. Prompt: Session token (input hidden)
4. Fetch activities to validate credentials — exit with error on failure
5. Extract all unique `professorName` values from the response
6. For each teacher (sorted alphabetically), show a `questionary.select` with `SUBJECTS` and ask the user to assign it
7. Save everything to `config.json`

Re-running `setup` overwrites the existing config.

### `adalove fetch`

Steps:

1. Load `config.json` — exit with clear message if missing ("Run 'adalove setup' first")
2. Fetch activities from API
3. On HTTP 401/403 or empty response: print "Session expired. Run 'adalove setup' to update your token." and exit
4. Show `questionary.checkbox` for weeks (derived from unique `folderCaption` values, sorted numerically)
5. Show `questionary.checkbox` for subjects (from `SUBJECTS`, excluding "Não presente no módulo")
6. Filter activities by selected weeks and subjects (via teacher→subject mapping)
7. Write `output/activities.md`
8. Write `output/links.md`
9. Print confirmation with file paths

If no weeks or no subjects are selected, prompt again rather than producing empty output.

---

## Filtering Logic

`filters/activity.py` exposes:

```python
def filter_activities(
    activities: list[Activity],
    weeks: list[int],
    subjects: list[str],
    teacher_subjects: dict[str, str],
) -> list[Activity]:
```

An activity passes if:
- Its `folder_number` is in `weeks` (or `weeks` is empty → all)
- Its `professor_name` maps to a subject in `subjects` (or `subjects` is empty → all)
- Its mapped subject is NOT "Não presente no módulo"

---

## Output Format

### `output/activities.md`

```markdown
# Adalove — Semanas 05, 06 | Algoritmos, Matemática
> Gerado em: 2026-05-07

---

## Semana 05

### Programação

#### Videoaula: How Computers Compress Text - Huffman Coding and Huffman Trees
**Professor:** Fillipe Manoel Xavier Resina
**URL:** https://www.youtube.com/watch?v=JsTptu56GM8

O conteúdo deste autoestudo pode ser assistido na videoaula...

---
```

- Weeks sorted numerically
- Subjects sorted alphabetically within each week
- HTML in `description` stripped to plain text (stdlib `html.parser`)
- Activities with no URL omit the URL line

### `output/links.md`

```markdown
# Links — Semanas 05, 06 | Programação, Matemática
> Gerado em: 2026-05-07

## Semana 05

### Programação
- [Videoaula: How Computers Compress Text](https://www.youtube.com/watch?v=JsTptu56GM8)

### Matemática
- [Título da atividade](https://...)

## Semana 06
...
```

- Activities with no URL are omitted from `links.md` entirely
- Structure mirrors `activities.md` for consistency

---

## Error Handling

| Scenario | Behavior |
|---|---|
| `config.json` missing | "Run 'adalove setup' first." + exit 1 |
| Token expired (401/403) | "Session expired. Run 'adalove setup' to update your token." + exit 1 |
| Network error | Print exception message + exit 1 |
| No activities after filter | "No activities match the selected filters." + exit 0 |
| `output/` dir missing | Created automatically |

---

## Installation

```bash
pip install -e .
adalove setup
adalove fetch
```

`pyproject.toml` declares the `adalove` entry point pointing to `cli.main:app`.
