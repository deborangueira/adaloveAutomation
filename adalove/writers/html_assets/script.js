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

// Only adds the "Ver tudo" toggle (and the fade) when the collapsed body
// actually clips content — short items stay as-is, nothing to expand. Call
// this only once the containing tab is visible: a hidden (display:none)
// ancestor makes scrollHeight/clientHeight both read 0, so the overflow
// check would always come up empty.
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

// ── Componentes ──────────────────────────────────────────────────────────
// Small DOM factories shared by every tab, so each render function only
// describes *what* to show. Styling lives in style.css under the same names.

const ICON_EXTERNAL = '<path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/>';

function svgIcon(paths, cls, size = 13) {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('class', cls);
  svg.setAttribute('viewBox', '0 0 24 24');
  svg.setAttribute('width', String(size));
  svg.setAttribute('height', String(size));
  svg.setAttribute('fill', 'none');
  svg.setAttribute('stroke', 'currentColor');
  svg.setAttribute('stroke-width', '2');
  svg.setAttribute('stroke-linecap', 'round');
  svg.setAttribute('stroke-linejoin', 'round');
  svg.setAttribute('aria-hidden', 'true');
  svg.innerHTML = paths;
  return svg;
}

// EmptyState — one look for "nothing here" across tabs. `compact` is the
// smaller italic variant used inside cards.
const ICON_EMPTY = '<path d="M22 12h-6l-2 3h-4l-2-3H2"/><path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/>';

function emptyState(text, { compact = false } = {}) {
  if (compact) return el('p', 'empty-state compact', text);
  const box = el('div', 'empty-state');
  box.appendChild(svgIcon(ICON_EMPTY, 'empty-state-icon', 32));
  box.appendChild(el('p', null, text));
  return box;
}

// Adalove sends some captions in ALL CAPS; shown as a sentence they read
// calmer. Mixed-case captions are left exactly as written.
function sentenceCase(text) {
  if (!text || text !== text.toUpperCase() || !/[A-ZÀ-Ý]/.test(text)) return text;
  const lower = text.toLocaleLowerCase('pt-BR');
  return lower.charAt(0).toLocaleUpperCase('pt-BR') + lower.slice(1);
}

// "Hermano Peixoto de Oliveira Junior" → "HJ" (first + last name).
function initials(name) {
  const parts = (name || '').trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return '?';
  const first = parts[0][0];
  const last = parts.length > 1 ? parts[parts.length - 1][0] : '';
  return (first + last).toUpperCase();
}

// LinkItem — a row that opens in a new tab, with an icon saying so. Without
// a url it renders as plain text in the same box, keeping lists aligned.
function linkItem({ title, url, tooltip }) {
  const item = el(url ? 'a' : 'div', 'link-item');
  item.title = tooltip || title;
  item.appendChild(el('span', 'link-item-title', title));
  if (url) {
    item.href = url;
    item.target = '_blank';
    item.rel = 'noopener';
    item.appendChild(svgIcon(ICON_EXTERNAL, 'link-item-icon'));
    item.appendChild(el('span', 'sr-only', '(abre em nova aba)'));
  }
  return item;
}

function linkList(links) {
  const list = el('div', 'link-list');
  links.forEach(l => list.appendChild(linkItem(l)));
  return list;
}

// Raw URLs are hard to scan; show host + path and keep the full URL in the
// tooltip.
function prettyUrl(url) {
  try {
    const u = new URL(url);
    let path = decodeURIComponent(u.pathname).replace(/\/$/, '');
    // A short path (youtube.com/watch) means the query is what identifies it.
    if (path.length < 12 && u.search) path += u.search;
    const shortPath = path.length > 48 ? path.slice(0, 47) + '…' : path;
    return u.hostname.replace(/^www\./, '') + shortPath;
  } catch (e) {
    return url;
  }
}

function copyButton(label, getText) {
  const btn = el('button', 'copy-btn', label);
  btn.type = 'button';
  btn.setAttribute('aria-live', 'polite');
  btn.addEventListener('click', () => copyText(getText(), btn));
  return btn;
}

// ContentCard — title + copy button, optional meta line and a rich-text body
// that collapses when long. Appends to `root` itself because makeExpandable
// needs the card in the DOM to measure it.
// `subject` tints the card with that disciplina's color; `weight` shows the
// ponderada's points prominently. Copying keeps the caption as written.
function appendContentCard(root, { title, meta, html, subject, weight }) {
  const card = el('article', 'content-card');
  const color = subject ? subjectColor(subject) : null;
  if (color) {
    card.classList.add('has-subject');
    card.style.setProperty('--subject', color);
  }
  const head = el('div', 'content-card-head');
  head.appendChild(el('h3', null, sentenceCase(title)));
  const actions = el('div', 'content-card-actions');
  if (weight !== undefined && weight !== null) {
    const pill = el('span', 'weight-pill');
    pill.appendChild(el('strong', null, String(weight)));
    pill.appendChild(document.createTextNode(weight === 1 ? 'ponto' : 'pontos'));
    actions.appendChild(pill);
  }
  actions.appendChild(copyButton('Copiar', () => (html ? `${title}\n\n${plainText(html)}` : title)));
  head.appendChild(actions);
  card.appendChild(head);
  if (meta) card.appendChild(el('p', 'meta', meta));
  const body = el('div', 'content-card-body');
  richHtml(body, html);
  card.appendChild(body);
  root.appendChild(card);
  makeExpandable(body);
  return card;
}

// Tablist — wires buttons as an ARIA tablist: only the selected tab is in
// the Tab order, arrow keys / Home / End move between tabs. `initial` is
// marked without calling onSelect, so callers can defer their first render.
function setupTablist(container, buttons, { label, orientation = 'horizontal', initial = 0, onSelect }) {
  container.setAttribute('role', 'tablist');
  container.setAttribute('aria-orientation', orientation);
  if (label) container.setAttribute('aria-label', label);

  const prevKeys = orientation === 'vertical' ? ['ArrowUp', 'ArrowLeft'] : ['ArrowLeft'];
  const nextKeys = orientation === 'vertical' ? ['ArrowDown', 'ArrowRight'] : ['ArrowRight'];

  const mark = (index) => buttons.forEach((b, i) => {
    const on = i === index;
    b.classList.toggle('active', on);
    b.setAttribute('aria-selected', String(on));
    b.tabIndex = on ? 0 : -1;
  });
  const select = (index) => { mark(index); onSelect(index); };

  buttons.forEach((b, i) => {
    b.type = 'button';
    b.setAttribute('role', 'tab');
    b.addEventListener('click', () => select(i));
    b.addEventListener('keydown', (e) => {
      const n = buttons.length;
      let target = null;
      if (prevKeys.includes(e.key)) target = (i - 1 + n) % n;
      else if (nextKeys.includes(e.key)) target = (i + 1) % n;
      else if (e.key === 'Home') target = 0;
      else if (e.key === 'End') target = n - 1;
      if (target === null) return;
      e.preventDefault();
      select(target);
      buttons[target].focus();
    });
  });

  mark(initial);
  return { select };
}

// NavList — the vertical menu beside each split view (Sprints, disciplinas,
// semanas), built from data on top of Tablist.
// The visible label sits outside the tablist element, since a tablist may
// only contain tabs.
function navList(root, items, { label, getLabel, getColor, onSelect }) {
  root.appendChild(el('p', 'nav-label', label));
  const list = el('div', 'nav-items');
  root.appendChild(list);
  const buttons = items.map(item => {
    const b = el('button', null, getLabel(item));
    const color = getColor ? getColor(item) : null;
    if (color) {
      b.classList.add('has-dot');
      b.style.setProperty('--subject', color);
    }
    list.appendChild(b);
    return b;
  });
  return setupTablist(list, buttons, { label, orientation: 'vertical', onSelect: i => onSelect(items[i]) });
}

// Some tabs can only render once visible (makeExpandable measures layout),
// so they register here and the top-level tab switcher calls them once.
const firstShowHooks = {};
function onFirstShow(view, fn) { firstShowHooks[view] = fn; }
function runFirstShow(view) {
  const fn = firstShowHooks[view];
  if (!fn) return;
  delete firstShowHooks[view];
  fn();
}

document.getElementById('turma-name').textContent = DATA.turma;
document.getElementById('generated-at').textContent = DATA.generatedAt;

(function renderTurmaSwitcher() {
  const container = document.getElementById('turma-header-container');
  if (!container) return;
  const turmas = DATA.availableTurmas || [];
  if (turmas.length === 0) {
    const badgeSpan = el('span', 'badge neutral', DATA.turma);
    container.appendChild(badgeSpan);
    return;
  }

  const select = el('select', 'turma-select');
  select.title = 'Alternar turma';

  turmas.forEach(t => {
    const opt = document.createElement('option');
    opt.value = t.uuid || t.caption;
    opt.dataset.caption = t.caption;
    const statusLabel = t.status === 'open' ? ' (Aberta)' : '';
    opt.textContent = `${t.caption}${statusLabel} — ${t.projectCaption || ''}`;
    if (t.active || t.caption === DATA.turma) {
      opt.selected = true;
    }
    select.appendChild(opt);
  });

  select.addEventListener('change', () => {
    const selectedUuid = select.value;
    const selectedOpt = select.selectedOptions[0];
    const selectedCaption = selectedOpt ? selectedOpt.dataset.caption : '';

    if (window.location.protocol.startsWith('http')) {
      window.location.href = `/dashboard?section=${encodeURIComponent(selectedUuid)}`;
    } else if (selectedCaption && selectedCaption !== DATA.turma) {
      window.location.href = `../${selectedCaption}/dashboard.html`;
    }
  });

  container.appendChild(select);
})();


// ── Resumo do módulo (transposto: semanas viram linhas) ───────────────────
const SUBJECT_ABBR = {
  'Programação': 'Prog', 'Matemática': 'Mat', 'Negócios': 'Neg',
  'Liderança': 'Lid', 'UX': 'UX', 'Orientação': 'Orient',
};
const subjectAbbr = (name) => SUBJECT_ABBR[name] || name;

const _now = new Date();
const _pad = (n) => String(n).padStart(2, '0');
const TODAY_STR = `${_pad(_now.getDate())}/${_pad(_now.getMonth() + 1)}/${_now.getFullYear()}`;
// "dd/mm/yyyy" → "yyyymmdd", so dates compare as plain strings.
const dateKey = (s) => (s || '').split('/').reverse().join('');
const TODAY_KEY = dateKey(TODAY_STR);

// Human dates: "02/02/2026" → "seg · 02 fev". The year repeats on every row
// and carries no information inside a module, so it's dropped from display
// (the full date stays in the tooltip).
const WEEKDAYS = ['dom', 'seg', 'ter', 'qua', 'qui', 'sex', 'sáb'];
const MONTHS = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez'];
function parseBrDate(s) {
  const [d, m, y] = (s || '').split('/').map(Number);
  return d && m && y ? new Date(y, m - 1, d) : null;
}
function shortDate(s) {
  const d = parseBrDate(s);
  return d ? `${_pad(d.getDate())} ${MONTHS[d.getMonth()]}` : (s || '');
}
function friendlyDate(s) {
  const d = parseBrDate(s);
  return d ? `${WEEKDAYS[d.getDay()]} · ${shortDate(s)}` : (s || '');
}

// Where today falls in the module, derived from the encontro dates:
// 'before' it starts, 'running' (with the current week), 'done', or
// 'unknown' when there's no calendar at all.
const ALL_ENCONTROS = DATA.sprints
  .flatMap(s => s.encontros)
  .filter(e => parseBrDate(e.date))
  .sort((a, b) => dateKey(a.date).localeCompare(dateKey(b.date)));
const TOTAL_WEEKS = DATA.resumo.reduce((max, w) => Math.max(max, w.week), 0);
const MODULE = (() => {
  if (!ALL_ENCONTROS.length) return { status: 'unknown', next: null };
  const next = ALL_ENCONTROS.find(e => dateKey(e.date) > TODAY_KEY) || null;
  if (TODAY_KEY < dateKey(ALL_ENCONTROS[0].date)) return { status: 'before', next };
  if (!next && TODAY_KEY > dateKey(ALL_ENCONTROS[ALL_ENCONTROS.length - 1].date)) return { status: 'done', next };
  const past = ALL_ENCONTROS.filter(e => dateKey(e.date) <= TODAY_KEY);
  return { status: 'running', week: past[past.length - 1].week, next };
})();
const currentWeek = MODULE.status === 'running' ? MODULE.week : null;

(function renderModuleProgress() {
  const chip = document.getElementById('module-progress');
  const header = document.querySelector('header');
  let pct = 0;
  let text = '';
  if (MODULE.status === 'running' && TOTAL_WEEKS) {
    pct = Math.min(100, (MODULE.week / TOTAL_WEEKS) * 100);
    text = `Semana ${MODULE.week} de ${TOTAL_WEEKS}`;
  } else if (MODULE.status === 'done') {
    pct = 100;
    text = 'Módulo concluído';
  } else if (MODULE.status === 'before' && MODULE.next) {
    text = `Começa ${friendlyDate(MODULE.next.date)}`;
  }
  if (chip) chip.textContent = text;
  header.style.setProperty('--progress', `${pct}%`);
})();

(function renderResumo() {
  const root = document.getElementById('resumo-table');

  const header = el('div', 'week-summary-header');
  ['', 'Composição', 'Ponderadas'].forEach(h => header.appendChild(el('span', null, h)));
  root.appendChild(header);

  DATA.resumo.forEach(w => {
    const row = el('div', 'week-row');
    if (currentWeek !== null && w.week === currentWeek) {
      row.classList.add('current-week');
      row.title = 'Semana atual';
    }
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

    root.appendChild(row);
  });
})();

// ── Card de Hoje (Calendário) ──────────────────────────────────────────
(function renderHojeCard() {
  const card = document.getElementById('hoje-card');
  if (!card) return;

  // Today's encontro if there is one; otherwise the next one, so the card
  // always says something useful instead of "nothing today".
  const today = ALL_ENCONTROS.find(e => e.date === TODAY_STR);
  const encontro = today || MODULE.next;

  const head = el('div', 'hoje-card-head');

  if (!encontro) {
    head.appendChild(el('span', 'hoje-card-title', 'Hoje'));
    head.appendChild(el('span', 'hoje-date-muted', friendlyDate(TODAY_STR)));
    card.appendChild(head);
    card.appendChild(el('hr', 'hoje-divider'));
    if (MODULE.status === 'done') {
      const done = el('div', 'hoje-done');
      done.appendChild(el('span', null, '🎓'));
      const text = el('div', null, 'Módulo concluído');
      text.appendChild(el('small', null, 'Não há mais encontros no calendário.'));
      done.appendChild(text);
      card.appendChild(done);
    } else {
      card.appendChild(emptyState('Nenhum encontro no calendário.', { compact: true }));
    }
    return;
  }

  if (!today) card.classList.add('is-next');
  head.appendChild(el('span', 'hoje-card-title', today ? 'Hoje' : 'Próximo encontro'));
  head.appendChild(el('span', 'hoje-date-muted', friendlyDate(encontro.date)));
  card.appendChild(head);

  if (encontro.label || encontro.title) {
    const row = el('div', 'hoje-encontro-row');
    if (encontro.label) row.appendChild(badge(encontro.label, encontro.subject));
    if (encontro.title) {
      const subtitle = el('span', 'hoje-encontro-title', encontro.title);
      subtitle.title = encontro.title;
      row.appendChild(subtitle);
    }
    card.appendChild(row);
  }

  card.appendChild(el('hr', 'hoje-divider'));

  const autoestudos = encontro.autoestudos || [];
  const books = encontro.books || [];

  if (autoestudos.length === 0 && books.length === 0) {
    card.appendChild(emptyState('Nenhum autoestudo registrado.', { compact: true }));
    return;
  }

  if (autoestudos.length > 0) {
    card.appendChild(linkList(autoestudos));
  }

  if (books.length > 0) {
    const bookCount = books.length;
    const countLabel = bookCount === 1 ? "1 referência em livro" : (bookCount + " referências em livros");

    const details = el("details", "hoje-books-details");
    const summary = el("summary", "hoje-books-summary");
    summary.textContent = "\uD83D\uDCD6 " + countLabel;
    details.appendChild(summary);
    details.appendChild(linkList(books));
    card.appendChild(details);
  }
})();

// ── Sprints (Calendário) ────────────────────────────────────────────────
(function renderSprints() {
  const root = document.getElementById('sprints');
  DATA.sprints.forEach(sprint => {
    const section = el('div', 'panel sprint-card');
    const enc = sprint.encontros;
    const head = el('div', 'sprint-card-head');
    head.appendChild(el('h3', null, `Sprint ${sprint.number}`));
    if (enc.length) {
      const first = enc[0].date, last = enc[enc.length - 1].date;
      head.appendChild(el('span', 'meta', first === last ? shortDate(first) : `${shortDate(first)} – ${shortDate(last)}`));
      if (dateKey(last) < TODAY_KEY) section.classList.add('done');
    }
    section.appendChild(head);

    const list = el('ul', 'encontros');
    let prevWeek = null;
    enc.forEach(item => {
      if (item.week && item.week !== prevWeek) {
        list.appendChild(el('li', 'week-label', `Semana ${item.week}`));
      }
      prevWeek = item.week;
      const li = el('li');
      const color = subjectColor(item.subject);
      if (color) li.style.setProperty('--subject', color);
      const isToday = (item.date === TODAY_STR);
      if (isToday) {
        li.classList.add('today');
      } else if (item.date && dateKey(item.date) < TODAY_KEY) {
        li.classList.add('past');
      }
      const dateSpan = el('span', 'date', friendlyDate(item.date));
      dateSpan.title = item.date;
      li.appendChild(dateSpan);
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
    contentRoot.appendChild(emptyState('Nenhum artefato de projeto encontrado.'));
    return;
  }

  function renderContent(sprint) {
    contentRoot.innerHTML = '';
    sprint.artifacts.forEach(a => appendContentCard(contentRoot, { title: a.caption, html: a.html }));
  }

  navList(navRoot, DATA.projeto, {
    label: 'Sprints do projeto',
    getLabel: s => `Sprint ${s.sprint}`,
    onSelect: renderContent,
  });

  // The Projeto tab starts hidden (display:none), where scrollHeight reads
  // as 0 — makeExpandable's overflow check would always come up empty. Defer
  // the first render until the tab is actually visible, so the measurement
  // reflects real layout.
  onFirstShow('projeto', () => renderContent(DATA.projeto[0]));
})();

// ── Prova ────────────────────────────────────────────────────────────────
(function renderProva() {
  const navRoot = document.getElementById('prova-nav');
  const contentRoot = document.getElementById('prova-content');
  if (!DATA.prova.length) {
    document.querySelector('#view-prova .split-divider').style.display = 'none';
    document.querySelector('#view-prova .kind-filter').style.display = 'none';
    contentRoot.appendChild(emptyState('Nenhuma disciplina mapeada encontrada.'));
    document.getElementById('export-prova').style.display = 'none';
    return;
  }

  let currentSubject = DATA.prova[0];
  let currentKind = 'instrucoes';

  // Prova is browsed one subject at a time, so its export downloads just
  // the subject currently on screen — not the whole tab like the other
  // three buttons — matching the per-discipline files write_subject_links_md
  // already produces (matematica.md, programacao.md, ...).
  document.getElementById('export-prova').addEventListener('click', () => {
    const slug = currentSubject.name.toLowerCase().replace(/ /g, '-');
    downloadText(`prova-${slug}.md`, buildProvaSubjectMd(currentSubject));
  });

  function renderContent() {
    contentRoot.innerHTML = '';
    const subj = currentSubject;

    if (currentKind === 'instrucoes') {
      if (!subj.instrucoesBySprint.length) {
        contentRoot.appendChild(emptyState('Nenhuma instrução registrada.'));
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
        contentRoot.appendChild(emptyState('Nenhum autoestudo registrado.'));
      } else {
        const ul = el('ul', 'plain');
        subj.autoestudo.forEach(t => ul.appendChild(el('li', null, t)));
        contentRoot.appendChild(ul);
      }
    } else if (currentKind === 'links') {
      if (subj.links.length) {
        const head = el('div', 'card-head');
        head.appendChild(el('h4', null, 'Links'));
        head.appendChild(copyButton('Copiar todos', () => subj.links.join('\n')));
        contentRoot.appendChild(head);
        contentRoot.appendChild(linkList(subj.links.map(u => ({ title: prettyUrl(u), url: u, tooltip: u }))));
      } else {
        contentRoot.appendChild(emptyState('Nenhum link registrado.'));
      }
      if (subj.books.length) {
        contentRoot.appendChild(el('h4', 'list-heading', 'Referências a livros'));
        contentRoot.appendChild(linkList(subj.books.map(u => ({ title: prettyUrl(u), url: u, tooltip: u }))));
      }
    }
  }

  // The content panel takes the selected disciplina's color.
  const panel = contentRoot.closest('.panel');
  function tintPanel() {
    const color = subjectColor(currentSubject.name);
    panel.classList.toggle('subject-accent', !!color);
    if (color) panel.style.setProperty('--subject', color);
  }

  navList(navRoot, DATA.prova, {
    label: 'Disciplinas',
    getLabel: s => s.name,
    getColor: s => subjectColor(s.name),
    onSelect: subj => { currentSubject = subj; tintPanel(); renderContent(); },
  });
  tintPanel();

  const kindFilter = document.getElementById('prova-kind-filter');
  const kindButtons = [...kindFilter.querySelectorAll('button')];
  setupTablist(kindFilter, kindButtons, {
    label: 'Tipo de conteúdo',
    onSelect: i => { currentKind = kindButtons[i].dataset.kind; renderContent(); },
  });

  renderContent();
})();

// ── Ponderadas ───────────────────────────────────────────────────────────
(function renderPonderadas() {
  const navRoot = document.getElementById('ponderadas-nav');
  const contentRoot = document.getElementById('ponderadas-content');
  if (!DATA.ponderadas.length) {
    document.querySelector('#view-ponderadas .split-divider').style.display = 'none';
    contentRoot.appendChild(emptyState('Nenhuma ponderada encontrada.'));
    return;
  }

  function renderContent(week) {
    contentRoot.innerHTML = '';
    week.items.forEach(item => {
      const meta = [item.subject, item.professor].filter(Boolean).join(' · ');
      appendContentCard(contentRoot, {
        title: item.caption, meta, html: item.html, subject: item.subject, weight: item.weight,
      });
    });
  }

  navList(navRoot, DATA.ponderadas, {
    label: 'Semanas',
    getLabel: w => `Semana ${String(w.week).padStart(2, '0')}`,
    onSelect: renderContent,
  });

  // Same reasoning as Projeto: defer the first render until the tab is
  // actually visible, since makeExpandable's overflow check needs real layout.
  onFirstShow('ponderadas', () => renderContent(DATA.ponderadas[0]));
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
    ['Data da sessão', /^\d{4}-\d{2}-\d{2}$/.test(info.dataSessao || '')
      ? friendlyDate(info.dataSessao.split('-').reverse().join('/')) + ` de ${info.dataSessao.slice(0, 4)}`
      : info.dataSessao],
  ].forEach(([label, value]) => {
    if (!value) return;
    dl.appendChild(el('dt', null, label));
    dl.appendChild(el('dd', null, value));
  });

  const list = document.getElementById('turma-disciplinas');
  if (!info.disciplinas.length) {
    list.replaceWith(emptyState('Nenhuma disciplina mapeada encontrada.'));
  } else {
    info.disciplinas.forEach(d => {
      const li = el('li');
      li.appendChild(badge(d.subject, d.subject));
      const people = el('div', 'people');
      const color = subjectColor(d.subject);
      if (color) people.style.setProperty('--subject', color);
      d.professors.forEach(name => {
        const person = el('span', 'person');
        const avatar = el('span', 'avatar', initials(name));
        avatar.setAttribute('aria-hidden', 'true');
        person.appendChild(avatar);
        person.appendChild(el('span', null, name));
        people.appendChild(person);
      });
      li.appendChild(people);
      list.appendChild(li);
    });
  }
})();

// ── Tabs ─────────────────────────────────────────────────────────────────
const tabs = [...document.querySelectorAll('.tab')];
const views = document.querySelectorAll('.view');
const exportLinks = document.querySelectorAll('.export-link');
tabs.forEach(t => {
  t.id = `tab-${t.dataset.view}`;
  t.setAttribute('aria-controls', `view-${t.dataset.view}`);
});
views.forEach(v => {
  v.setAttribute('role', 'tabpanel');
  v.setAttribute('aria-labelledby', `tab-${v.id.replace(/^view-/, '')}`);
});
function showView(name) {
  views.forEach(v => v.classList.toggle('active', v.id === `view-${name}`));
  exportLinks.forEach(b => b.classList.toggle('active', b.dataset.tab === name));
  runFirstShow(name);
}
setupTablist(document.querySelector('.tabs'), tabs, {
  label: 'Seções do dashboard',
  onSelect: i => showView(tabs[i].dataset.view),
}).select(0);

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

function buildProvaSubjectMd(subj) {
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
}

document.getElementById('export-calendario').addEventListener('click', () => downloadText('calendario.md', buildCalendarioMd()));
document.getElementById('export-projeto').addEventListener('click', () => downloadText('projeto.md', buildProjetoMd()));
document.getElementById('export-ponderadas').addEventListener('click', () => downloadText('ponderadas.md', buildPonderadasMd()));
