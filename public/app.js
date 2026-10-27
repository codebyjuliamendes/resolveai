// ResolveAI — frontend sem dependências. Todo conteúdo vindo da API é tratado como não
// confiável e inserido via textContent/createElement, nunca como HTML.
'use strict';

const $ = (selector) => document.querySelector(selector);

const STATUS_LABEL = { novo: 'Novo', em_atendimento: 'Em atendimento', resolvido: 'Resolvido' };
const CATEGORIES = ['Pedido', 'Entrega', 'Pagamento', 'Segurança alimentar', 'Geral'];
const dateShort = new Intl.DateTimeFormat('pt-BR', { day: '2-digit', month: 'short' });
const dateLong = new Intl.DateTimeFormat('pt-BR', { dateStyle: 'short', timeStyle: 'short' });

const state = {
  tickets: [],
  articles: [],
  selected: null,
  filter: 'open',
  query: '',
  loading: true,
  loadError: null,
  drafts: new Map(), // ticketId -> texto em edição
  suggestions: new Map(), // ticketId -> última sugestão (fontes recuperadas)
  pending: new Set(), // ações em andamento (evita envio duplo)
};

/* ---------- utilitários ---------- */

function h(tag, props, ...children) {
  const el = document.createElement(tag);
  for (const [key, value] of Object.entries(props || {})) {
    if (value === null || value === undefined || value === false) continue;
    if (key === 'class') el.className = value;
    else if (key === 'dataset') Object.assign(el.dataset, value);
    else if (key.startsWith('on') && typeof value === 'function') el.addEventListener(key.slice(2), value);
    else if (key === 'value' || key === 'disabled' || key === 'selected') el[key] = value;
    else el.setAttribute(key, value === true ? '' : String(value));
  }
  for (const child of children.flat(Infinity)) {
    if (child === null || child === undefined || child === false) continue;
    el.append(child instanceof Node ? child : String(child));
  }
  return el;
}

// replaceChildren sem nós vazios (null/false viram texto "null" no DOM).
function fill(el, ...children) {
  el.replaceChildren(...children.flat(Infinity).filter((c) => c !== null && c !== undefined && c !== false));
}

function parseDate(value) {
  if (!value) return null;
  // Aceita ISO 8601 e o formato legado "AAAA-MM-DD HH:MM:SS" (UTC).
  const iso = /[zZ]|[+-]\d\d:?\d\d$/.test(value) ? value : `${value.replace(' ', 'T')}Z`;
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? null : date;
}

function formatDate(value, formatter) {
  const date = parseDate(value);
  return date ? formatter.format(date) : '';
}

function fold(value) {
  return String(value).normalize('NFD').replace(/[̀-ͯ]/g, '').toLocaleLowerCase('pt-BR');
}

class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

async function api(url, { method = 'GET', body } = {}) {
  const options = { method, headers: { Accept: 'application/json' } };
  if (body !== undefined) {
    options.headers['Content-Type'] = 'application/json';
    options.body = JSON.stringify(body);
  }
  let response;
  try {
    response = await fetch(url, options);
  } catch {
    throw new ApiError('Sem conexão com o servidor. Verifique a rede e tente novamente.', 0);
  }
  let data = null;
  try {
    data = await response.json();
  } catch {
    data = null;
  }
  if (!response.ok) {
    const fallback = response.status === 429
      ? 'Muitas solicitações em pouco tempo. Aguarde e tente novamente.'
      : 'Não foi possível concluir a ação.';
    throw new ApiError((data && data.error) || fallback, response.status);
  }
  return data;
}

let toastTimer;
function toast(message) {
  const el = $('#toast');
  el.textContent = message;
  el.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove('show'), 3200);
}

// Executa uma ação por vez para cada chave, desabilitando o controle enquanto roda.
async function once(key, control, busyLabel, action) {
  if (state.pending.has(key)) return;
  state.pending.add(key);
  const label = control ? control.textContent : '';
  if (control) {
    control.disabled = true;
    control.setAttribute('aria-busy', 'true');
    if (busyLabel) control.textContent = busyLabel;
  }
  try {
    await action();
  } finally {
    state.pending.delete(key);
    if (control && control.isConnected) {
      control.disabled = false;
      control.removeAttribute('aria-busy');
      if (busyLabel) control.textContent = label;
    }
  }
}

/* ---------- dados ---------- */

async function load() {
  try {
    const [tickets, articles] = await Promise.all([api('/api/tickets'), api('/api/articles')]);
    state.tickets = tickets;
    state.articles = articles;
    state.loadError = null;
    if (!tickets.some((t) => t.id === state.selected)) {
      const firstOpen = tickets.find((t) => t.status !== 'resolvido');
      state.selected = (firstOpen || tickets[0] || {}).id ?? null;
    }
  } catch (error) {
    state.loadError = error.message;
  } finally {
    state.loading = false;
  }
  render();
}

function visibleTickets() {
  if (state.filter === 'open') return state.tickets.filter((t) => t.status !== 'resolvido');
  if (state.filter === 'resolvido') return state.tickets.filter((t) => t.status === 'resolvido');
  return state.tickets;
}

/* ---------- renderização ---------- */

function render() {
  const open = state.tickets.filter((t) => t.status !== 'resolvido').length;
  $('#open-count').textContent = state.loading ? '—' : String(open);
  $('#tab-open').textContent = state.loading ? '—' : String(open);
  renderTickets();
  renderArticles();
  renderDetail();
}

function stateMessage(text, retry) {
  return h('div', { class: 'state' + (retry ? ' state-error' : ''), role: retry ? 'alert' : null },
    h('p', null, text),
    retry ? h('button', { type: 'button', class: 'ghost-button', onclick: retry }, 'Tentar novamente') : null);
}

function retryLoad() {
  state.loading = true;
  render();
  load();
}

function renderTickets() {
  const list = $('#ticket-list');
  list.setAttribute('aria-busy', String(state.loading));
  if (state.loading) return fill(list, stateMessage('Carregando chamados…'));
  if (state.loadError) return fill(list, stateMessage(state.loadError, retryLoad));
  const tickets = visibleTickets();
  if (!tickets.length) return fill(list, stateMessage('Nenhum chamado nesta fila.'));
  fill(list, h('ul', { class: 'ticket-items' }, tickets.map((t) => h('li', null,
    h('button', {
      type: 'button',
      class: 'ticket-card' + (state.selected === t.id ? ' active' : ''),
      'aria-current': state.selected === t.id ? 'true' : null,
      dataset: { ticket: String(t.id) },
    },
    h('span', { class: 'ticket-top' },
      h('span', { class: 'customer' }, t.customer),
      h('span', { class: 'ticket-date' }, formatDate(t.createdAt, dateShort))),
    h('span', { class: 'ticket-subject' }, t.subject),
    h('span', { class: 'ticket-snippet' }, t.message),
    h('span', { class: 'ticket-tags' },
      h('span', { class: 'tag' + (t.priority === 'Alta' ? ' high' : '') }, t.priority),
      h('span', { class: 'tag' }, t.category),
      h('span', { class: 'tag' + (t.status === 'novo' ? ' open' : '') }, STATUS_LABEL[t.status] || t.status)))))));
}

function renderArticles() {
  const list = $('#article-list');
  if (state.loading) return fill(list, stateMessage('Carregando artigos…'));
  if (state.loadError) return fill(list);
  const query = fold(state.query.trim());
  const rows = state.articles.filter((a) => !query || fold(`${a.title} ${a.category} ${a.body}`).includes(query));
  if (!rows.length) {
    return fill(list, stateMessage(state.articles.length ? 'Nenhum artigo encontrado.' : 'A base ainda não tem artigos.'));
  }
  fill(list, ...rows.map((a) => h('article', { class: 'article' },
    h('span', { class: 'article-category' }, a.category.toLocaleUpperCase('pt-BR')),
    h('h3', null, a.title),
    h('p', null, a.body),
    h('div', { class: 'article-actions' },
      h('button', { type: 'button', dataset: { editArticle: String(a.id) }, 'aria-label': `Editar artigo ${a.title}` }, 'Editar'),
      h('button', { type: 'button', dataset: { historyArticle: String(a.id) }, 'aria-label': `Histórico do artigo ${a.title}` }, 'Histórico')))));
}

function renderDetail() {
  const detail = $('#detail');
  if (state.loading) return fill(detail, stateMessage('Carregando…'));
  if (state.loadError) return fill(detail, stateMessage('Não foi possível carregar os chamados.'));
  const t = state.tickets.find((x) => x.id === state.selected);
  if (!t) {
    return fill(detail, h('div', { class: 'detail-empty' },
      h('b', null, 'Atendimento com contexto'),
      h('p', null, 'Selecione um chamado para revisar a mensagem e consultar artigos relacionados.')));
  }
  const resolved = t.status === 'resolvido';
  const statusSelect = h('select', { id: 'status', class: 'status-select' },
    Object.entries(STATUS_LABEL).map(([value, label]) => h('option', { value, selected: t.status === value }, label)));
  statusSelect.addEventListener('change', () => changeStatus(t, statusSelect));

  const reply = h('textarea', {
    id: 'reply',
    rows: '8',
    maxlength: '1600',
    placeholder: resolved ? 'Chamado resolvido.' : 'Escreva sua resposta ou gere uma sugestão para revisar…',
    disabled: resolved,
    'aria-describedby': 'review-note',
  });
  reply.value = state.drafts.get(t.id) || '';
  reply.addEventListener('input', () => {
    state.drafts.set(t.id, reply.value);
    renderSourceChips(t.id);
  });

  const generate = h('button', { type: 'button', class: 'generate', id: 'generate', disabled: resolved }, 'Sugerir com artigos');
  generate.addEventListener('click', () => requestSuggestion(t, generate));
  const send = h('button', { type: 'button', class: 'send', id: 'send', disabled: resolved }, 'Registrar resposta →');
  send.addEventListener('click', () => registerReply(t, send));

  fill(detail, 
    h('div', { class: 'detail-head' },
      h('div', { class: 'detail-meta' },
        h('span', { class: 'tag' }, t.category),
        h('span', { class: 'tag' + (t.priority === 'Alta' ? ' high' : '') }, `${t.priority} prioridade`),
        h('label', { for: 'status', class: 'visually-hidden' }, 'Status do chamado'),
        statusSelect),
      h('h2', { id: 'detail-title' }, t.subject),
      h('span', { class: 'detail-customer' }, `${t.customer} · ${t.email}`)),
    h('div', { class: 'message-block' },
      h('div', { class: 'message-label' }, 'MENSAGEM DO CLIENTE'),
      h('div', { class: 'customer-message' }, t.message)),
    t.replies.length ? h('div', { class: 'replies' },
      h('div', { class: 'message-label' }, 'RESPOSTAS REGISTRADAS'),
      t.replies.map((r) => h('div', { class: 'reply-saved' },
        h('p', null, r.body),
        h('small', null, `Resposta registrada · ${formatDate(r.createdAt, dateLong)}`)))) : null,
    h('div', { class: 'composer' },
      h('div', { class: 'composer-head' },
        h('label', { for: 'reply' }, h('strong', null, 'Rascunho de resposta')),
        generate),
      reply,
      h('div', { id: 'suggestion-info', class: 'suggestion-info', 'aria-live': 'polite' }),
      h('div', { class: 'composer-footer' },
        h('span', { class: 'review-note', id: 'review-note' }, 'Revise antes de enviar ao cliente.'),
        send)));
  renderSourceChips(t.id);
}

// Fontes citadas no texto atual: só marcadores [n] de artigos recuperados contam.
function citedSources(ticketId) {
  const suggestion = state.suggestions.get(ticketId);
  if (!suggestion) return [];
  const text = state.drafts.get(ticketId) || '';
  const cited = new Set([...text.matchAll(/\[(\d{1,3})\]/g)].map((m) => Number(m[1])));
  return suggestion.sources.filter((_, i) => cited.has(i + 1));
}

function renderSourceChips(ticketId) {
  const info = $('#suggestion-info');
  if (!info) return;
  const suggestion = state.suggestions.get(ticketId);
  if (!suggestion) return fill(info);
  if (!suggestion.sources.length) {
    return fill(info, h('p', { class: 'callout warn' },
      'Sem fonte correspondente na base · encaminhe para revisão de uma pessoa responsável.'));
  }
  const cited = new Set(citedSources(ticketId).map((s) => s.id));
  fill(info, 
    h('p', { class: 'sources-label' }, suggestion.mode === 'base-local'
      ? 'Fontes consultadas (rascunho montado com a base local):'
      : 'Fontes consultadas pelo modelo:'),
    h('ul', { class: 'source-list' }, suggestion.sources.map((s, i) => h('li', {
      class: 'source-chip' + (cited.has(s.id) ? ' cited' : ''),
      title: cited.has(s.id) ? 'Citada no texto' : 'Consultada, mas não citada no texto',
    }, `[${i + 1}] ${s.title}`))),
    cited.size ? null : h('p', { class: 'callout' }, 'O texto atual não cita nenhuma fonte. Confira as informações antes de registrar.'));
}

/* ---------- ações ---------- */

function changeStatus(ticket, select) {
  const previous = ticket.status;
  const next = select.value;
  once('status', select, null, async () => {
    try {
      await api(`/api/tickets/${ticket.id}/status`, { method: 'PATCH', body: { status: next } });
      await load();
      toast('Status atualizado.');
    } catch (error) {
      if (select.isConnected) select.value = previous;
      toast(error.message);
    }
  });
}

function requestSuggestion(ticket, button) {
  once(`suggest-${ticket.id}`, button, 'Preparando sugestão…', async () => {
    try {
      const result = await api('/api/suggest', { method: 'POST', body: { ticketId: ticket.id } });
      state.suggestions.set(ticket.id, result);
      state.drafts.set(ticket.id, result.draft);
      const reply = $('#reply');
      if (state.selected === ticket.id && reply) {
        reply.value = result.draft;
        renderSourceChips(ticket.id);
        reply.focus();
      }
      toast(result.mode === 'sem-fonte'
        ? 'Nenhum artigo correspondente. Encaminhe o caso para revisão.'
        : result.mode === 'base-local'
          ? 'Rascunho criado com a base local. Revise os artigos antes de usar.'
          : 'Sugestão gerada. Revise antes de usar.');
    } catch (error) {
      toast(error.message);
    }
  });
}

function registerReply(ticket, button) {
  const body = (state.drafts.get(ticket.id) || '').trim();
  if (body.length < 4) {
    toast('Escreva uma resposta antes de registrar.');
    const reply = $('#reply');
    if (reply) reply.focus();
    return;
  }
  once(`reply-${ticket.id}`, button, 'Registrando…', async () => {
    try {
      const sourceIds = citedSources(ticket.id).map((s) => s.id);
      await api('/api/replies', { method: 'POST', body: { ticketId: ticket.id, body, sourceIds } });
      state.drafts.delete(ticket.id);
      state.suggestions.delete(ticket.id);
      await load();
      toast('Resposta registrada e chamado resolvido.');
    } catch (error) {
      toast(error.message);
    }
  });
}

/* ---------- diálogos ---------- */

// Seletor estável do elemento que abriu o diálogo (a lista pode ser re-renderizada).
function selectorFor(el) {
  if (!el || el === document.body || !(el instanceof HTMLElement)) return null;
  if (el.id) return `#${CSS.escape(el.id)}`;
  for (const [key, attr] of [['editArticle', 'edit-article'], ['historyArticle', 'history-article'], ['ticket', 'ticket']]) {
    if (el.dataset[key]) return `[data-${attr}="${CSS.escape(el.dataset[key])}"]`;
  }
  return null;
}

function openDialog(title, eyebrow, content, origin) {
  const opener = origin || document.activeElement;
  const openerSelector = selectorFor(opener);
  const dialog = h('dialog', { class: 'modal', 'aria-labelledby': 'dialog-title' },
    h('div', { class: 'form' },
      h('button', { type: 'button', class: 'close', 'aria-label': 'Fechar' }, '×'),
      h('span', { class: 'eyebrow' }, eyebrow),
      h('h2', { id: 'dialog-title' }, title),
      content));
  dialog.querySelector('.close').addEventListener('click', () => dialog.close());
  dialog.addEventListener('click', (event) => { if (event.target === dialog) dialog.close(); });
  dialog.addEventListener('close', () => {
    dialog.remove();
    const target = opener && opener.isConnected ? opener : openerSelector && document.querySelector(openerSelector);
    if (target) target.focus();
  });
  document.body.append(dialog);
  dialog.showModal();
  return dialog;
}

function field(label, control) {
  return [h('label', { for: control.id }, label), control];
}

function formDialog({ key, title, eyebrow, fields, submitLabel, onSubmit }) {
  const error = h('p', { class: 'error', role: 'alert' });
  const submit = h('button', { type: 'submit', class: 'primary' }, submitLabel);
  const form = h('form', null, fields, error, submit);
  const dialog = openDialog(title, eyebrow, form);
  form.addEventListener('submit', (event) => {
    event.preventDefault();
    error.textContent = '';
    once(key, submit, 'Salvando…', async () => {
      try {
        await onSubmit(Object.fromEntries(new FormData(form)));
        dialog.close();
      } catch (err) {
        error.textContent = err.message;
      }
    });
  });
  const first = form.querySelector('input, textarea, select');
  if (first) first.focus();
}

function openArticleForm(article) {
  formDialog({
    key: article ? `article-${article.id}` : 'article-new',
    title: article ? 'Editar artigo' : 'Novo artigo',
    eyebrow: 'BASE DE CONHECIMENTO',
    submitLabel: article ? 'Salvar versão →' : 'Criar artigo →',
    fields: [
      field('Título', h('input', { id: 'f-title', name: 'title', required: true, minlength: '4', maxlength: '120', value: article ? article.title : '' })),
      field('Categoria', h('input', { id: 'f-category', name: 'category', required: true, minlength: '2', maxlength: '60', value: article ? article.category : '' })),
      field('Conteúdo de referência', h('textarea', { id: 'f-body', name: 'body', rows: '9', required: true, minlength: '20', maxlength: '12000', value: article ? article.body : '' })),
    ],
    onSubmit: async (data) => {
      await api(article ? `/api/articles/${article.id}` : '/api/articles', { method: article ? 'PUT' : 'POST', body: data });
      await load();
      toast(article ? 'Artigo atualizado; a versão anterior foi guardada.' : 'Artigo adicionado à base.');
    },
  });
}

function showArticleHistory(id, button) {
  once(`history-${id}`, button, null, async () => {
    try {
      const history = await api(`/api/articles/${id}/history`);
      const article = state.articles.find((a) => a.id === id);
      openDialog(article ? article.title : 'Histórico do artigo', 'HISTÓRICO DE VERSÕES',
        history.length
          ? h('ol', { class: 'versions' }, history.map((v) => h('li', { class: 'version' },
            h('strong', null, `Versão ${v.version}`),
            h('small', null, `${v.editor} · ${formatDate(v.createdAt, dateLong)}`),
            h('h3', null, v.title),
            h('p', null, v.body))))
          : h('p', null, 'Nenhuma edição registrada ainda.'), button);
    } catch (error) {
      toast(error.message);
    }
  });
}

function openTicketForm() {
  formDialog({
    key: 'ticket-new',
    title: 'Novo chamado',
    eyebrow: 'CENTRAL DE ATENDIMENTO',
    submitLabel: 'Criar chamado →',
    fields: [
      field('Nome do cliente', h('input', { id: 'f-customer', name: 'customer', required: true, minlength: '4', maxlength: '120', autocomplete: 'off' })),
      field('E-mail', h('input', { id: 'f-email', name: 'email', type: 'email', required: true, maxlength: '254', autocomplete: 'off' })),
      field('Assunto', h('input', { id: 'f-subject', name: 'subject', required: true, minlength: '4', maxlength: '100' })),
      field('Categoria', h('select', { id: 'f-category', name: 'category' }, CATEGORIES.map((c) => h('option', null, c)))),
      field('Prioridade', h('select', { id: 'f-priority', name: 'priority' }, h('option', null, 'Normal'), h('option', null, 'Alta'))),
      field('Mensagem', h('textarea', { id: 'f-message', name: 'message', rows: '4', required: true, minlength: '4', maxlength: '1200' })),
    ],
    onSubmit: async (data) => {
      const result = await api('/api/tickets', { method: 'POST', body: data });
      state.selected = result.id;
      setFilter('open');
      await load();
      toast('Chamado criado e incluído na fila.');
    },
  });
}

/* ---------- eventos ---------- */

function setFilter(filter) {
  state.filter = filter;
  document.querySelectorAll('.tab').forEach((tab) => {
    const active = tab.dataset.filter === filter;
    tab.classList.toggle('active', active);
    tab.setAttribute('aria-pressed', String(active));
  });
}

$('#ticket-list').addEventListener('click', (event) => {
  const card = event.target.closest('[data-ticket]');
  if (!card) return;
  state.selected = Number(card.dataset.ticket);
  render();
  if (window.matchMedia('(max-width: 760px)').matches) $('#detail').focus();
});

document.querySelector('.tabs').addEventListener('click', (event) => {
  const tab = event.target.closest('[data-filter]');
  if (!tab) return;
  setFilter(tab.dataset.filter);
  render();
});

$('#article-search').addEventListener('input', (event) => {
  state.query = event.target.value;
  renderArticles();
});

$('#article-list').addEventListener('click', (event) => {
  const edit = event.target.closest('[data-edit-article]');
  const history = event.target.closest('[data-history-article]');
  if (edit) openArticleForm(state.articles.find((a) => a.id === Number(edit.dataset.editArticle)));
  if (history) showArticleHistory(Number(history.dataset.historyArticle), history);
});

$('#knowledge-nav').addEventListener('click', () => {
  $('#knowledge').scrollIntoView({ behavior: 'smooth', block: 'start' });
  $('#article-search').focus({ preventScroll: true });
});
$('#tickets-nav').addEventListener('click', () => {
  $('#tickets').scrollIntoView({ behavior: 'smooth', block: 'start' });
});
$('#new-article').addEventListener('click', () => openArticleForm(null));
$('#new-ticket').addEventListener('click', openTicketForm);

render();
load();
