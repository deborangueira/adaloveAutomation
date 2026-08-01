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
  ['', 'Composição', 'Ponderadas'].forEach(h => header.appendChild(el('span', null, h)));
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

  function renderContent(sprint) {
    contentRoot.innerHTML = '';
    sprint.artifacts.forEach(a => {
      const item = el('article', 'list-item');
      const head = el('div', 'list-item-head');
      head.appendChild(el('h3', null, a.caption));
      const copyBtn = el('button', 'copy-btn', 'Copiar');
      copyBtn.type = 'button';
      copyBtn.addEventListener('click', () => {
        const text = a.html ? `${a.caption}\n\n${plainText(a.html)}` : a.caption;
        copyText(text, copyBtn);
      });
      head.appendChild(copyBtn);
      item.appendChild(head);

      const body = el('div', 'list-item-body');
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
  const navRoot = document.getElementById('ponderadas-nav');
  const contentRoot = document.getElementById('ponderadas-content');
  if (!DATA.ponderadas.length) {
    document.querySelector('#view-ponderadas .split-divider').style.display = 'none';
    contentRoot.appendChild(el('div', 'empty-state', 'Nenhuma ponderada encontrada.'));
    return;
  }

  function renderContent(week) {
    contentRoot.innerHTML = '';
    week.items.forEach(item => {
      const ponderadaItem = el('article', 'list-item');
      const head = el('div', 'list-item-head');
      head.appendChild(el('h3', null, item.caption));
      const copyBtn = el('button', 'copy-btn', 'Copiar');
      copyBtn.type = 'button';
      copyBtn.addEventListener('click', () => {
        const text = item.html ? `${item.caption}\n\n${plainText(item.html)}` : item.caption;
        copyText(text, copyBtn);
      });
      head.appendChild(copyBtn);
      ponderadaItem.appendChild(head);

      const metaParts = [];
      if (item.professor) metaParts.push(item.professor);
      metaParts.push(`${item.weight} pontos`);
      ponderadaItem.appendChild(el('p', 'meta', metaParts.join(' — ')));

      const body = el('div', 'list-item-body');
      richHtml(body, item.html);
      ponderadaItem.appendChild(body);
      contentRoot.appendChild(ponderadaItem);
      makeExpandable(body);
    });
  }

  DATA.ponderadas.forEach((week, i) => {
    const btn = el('button', i === 0 ? 'active' : null, `Semana ${String(week.week).padStart(2, '0')}`);
    btn.type = 'button';
    btn.addEventListener('click', () => {
      navRoot.querySelectorAll('button').forEach(b => b.classList.toggle('active', b === btn));
      renderContent(week);
    });
    navRoot.appendChild(btn);
  });

  // Same reasoning as Projeto: defer the first render until the tab is
  // actually visible, since makeExpandable's overflow check needs real layout.
  let initialized = false;
  document.querySelector('.tab[data-view="ponderadas"]').addEventListener('click', () => {
    if (!initialized) {
      initialized = true;
      renderContent(DATA.ponderadas[0]);
    }
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
const exportLinks = document.querySelectorAll('.export-link');
function activateTab(name) {
  tabs.forEach(t => t.classList.toggle('active', t.dataset.view === name));
  views.forEach(v => v.classList.toggle('active', v.id === `view-${name}`));
  exportLinks.forEach(b => b.classList.toggle('active', b.dataset.tab === name));
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
