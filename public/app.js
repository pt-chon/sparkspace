import { KINDS, STATUSES, TEMPLATES, STARTERS, MODES, uid, escapeHTML as esc, titleFromBody, activeTopics, activeIdeas, descendants, sortedIdeas, scopedIdeas, questionGroups, deletionPlan, deleteIdeas, restoreIdeas, importExamples, includedIdeas, buildPrompt } from './core.mjs';

const $ = selector => document.querySelector(selector);
const paths = {
  sprout: '<path d="M12 21V11M12 15C5 16 3 10 4 5c6 0 10 4 8 10Zm0-3c0-6 4-9 9-8 0 5-3 9-9 8Z"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  grid: '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
  search: '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
  devices: '<rect x="3" y="3" width="13" height="12" rx="2"/><path d="M6 20h7m-4-5v5"/><rect x="16" y="10" width="6" height="11" rx="1.5"/>',
  trash: '<path d="M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7m4-7v7"/>',
  settings: '<path d="m10 3-1 3-3 1-3 3 2 2-1 4 4 1 2 4 3-2 4 1 1-4 3-2-2-3 1-4-4-1-2-3Z"/><circle cx="12" cy="12" r="3"/>',
  'arrow-right': '<path d="M4 12h16m-6-6 6 6-6 6"/>',
  'arrow-up-right': '<path d="M6 18 18 6M6 6h12v12"/>',
  branch: '<rect x="3" y="3" width="6" height="6" rx="1.5"/><rect x="15" y="3" width="6" height="6" rx="1.5"/><rect x="15" y="15" width="6" height="6" rx="1.5"/><path d="M9 6h6M6 9v9h9"/>',
  columns: '<rect x="3" y="4" width="5" height="16" rx="1"/><rect x="10" y="4" width="5" height="11" rx="1"/><rect x="17" y="4" width="4" height="14" rx="1"/>',
  sparkles: '<path d="m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5L12 3ZM20 2v4m-2-2h4"/>',
  sliders: '<path d="M4 6h6m4 0h6M4 12h10m4 0h2M4 18h2m4 0h10"/><circle cx="12" cy="6" r="2"/><circle cx="16" cy="12" r="2"/><circle cx="8" cy="18" r="2"/>',
  book: '<path d="M12 5C8 2 4 3 2 4v16c3-2 7-1 10 1 3-2 7-3 10-1V4c-2-1-6-2-10 1Zm0 0v16"/>',
  person: '<circle cx="12" cy="8" r="4"/><path d="M4 21v-2a8 8 0 0 1 16 0v2"/>',
  chart: '<path d="M4 3v18h17M8 16l4-6 4 3 5-7"/>',
  question: '<circle cx="12" cy="12" r="9"/><path d="M9.5 9a2.5 2.5 0 0 1 5 0c0 2-2.5 2-2.5 4m0 3h.01"/>',
  check: '<path d="m5 12 4 4L19 6"/>',
  pin: '<path d="m9 3 6 0-1 6 4 4v2H6v-2l4-4-1-6ZM12 15v6"/>',
  close: '<path d="m6 6 12 12M6 18 18 6"/>',
  menu: '<path d="M4 6h16M4 12h16M4 18h16"/>',
  download: '<path d="M12 3v12m-5-5 5 5 5-5M4 15v6h16v-6"/>',
  upload: '<path d="M12 16V4m-5 5 5-5 5 5M4 16v5h16v-5"/>',
  copy: '<rect x="8" y="8" width="13" height="13" rx="2"/><path d="M16 8V3H3v13h5"/>',
  restore: '<path d="M3 10a9 9 0 1 1 1 8M3 4v6h6m3-4v6l4 2"/>',
  feather: '<path d="M20 3c-8-2-15 6-12 12 6 3 14-4 12-12ZM4 21 16 9m-8 6h6"/>',
  constellation: '<path d="m4 16 6-10 9 5-5 9M10 6l4 14"/><circle cx="4" cy="16" r="2"/><circle cx="10" cy="6" r="2"/><circle cx="19" cy="11" r="2"/><circle cx="14" cy="20" r="2"/>'
};
const icon = name => `<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name] || paths.sparkles}</svg>`;
document.querySelectorAll('[data-icon]').forEach(el => { el.innerHTML = icon(el.dataset.icon); });
const kindIcon = { idea: 'sparkles', question: 'question', decision: 'check', reference: 'book' };
const kindColor = { idea: 'sage', question: 'gold', decision: 'clay', reference: 'blue' };
let storageWarned = false;
function readLocal(key, fallback = null) { try { return JSON.parse(localStorage.getItem(`sparkspace:${key}`)) ?? fallback; } catch { return fallback; } }
function writeLocal(key, value) {
  try { value === null ? localStorage.removeItem(`sparkspace:${key}`) : localStorage.setItem(`sparkspace:${key}`, JSON.stringify(value)); return true; }
  catch { if (!storageWarned) { storageWarned = true; toast('此浏览器无法保存草稿。请及时点击保存或下载内容。', true); } return false; }
}
const S = { revision: 0, workspace: { schemaVersion: 1, topics: [], ideas: [] }, topicId: readLocal('topic', ''), page: 'topic', view: readLocal('view', 'cards') === 'tree' ? 'tree' : 'cards', focusId: null, collapsed: new Set(readLocal('collapsed', [])), filter: 'all', search: '', selected: new Set(), saving: false, online: false, loaded: false, sort: 'updated' };
let toastTimer, captureTimer, exportSession, editorSession, pendingQuick;
function toast(message, error = false) {
  clearTimeout(toastTimer); $('#toast').textContent = message; $('#toast').classList.toggle('error', error); $('#toast').hidden = false;
  toastTimer = setTimeout(() => { $('#toast').hidden = true; }, error ? 7000 : 3500);
}
function status(text, state = 'ok') { $('#save-status').textContent = text; $('#save-dot').className = `status-dot ${state}`; }
function banner(message = '') {
  $('#connection-banner').hidden = !message;
  $('#connection-banner').innerHTML = message ? `${esc(message)} <button class="text-button" data-action="reload">重新连接</button>` : '';
}
async function api(path, method = 'GET', body) {
  const response = await fetch(path, { method, headers: body ? { 'Content-Type': 'application/json' } : {}, body: body ? JSON.stringify(body) : undefined, cache: 'no-store', signal: AbortSignal.timeout(15000) });
  let data;
  try { data = await response.json(); } catch { throw new Error('服务返回了无法读取的内容，请检查电脑端是否仍在运行。'); }
  if (!response.ok) {
    const error = new Error(data.error || '操作未完成，请重试。'); error.code = data.code; error.status = response.status;
    if (response.status === 401) showPair();
    throw error;
  }
  return data;
}
function adopt(data) {
  if (S.loaded && data.revision < S.revision) return;
  const previousCapture = S.loaded ? captureKey() : null;
  if (S.loaded) stashCapture();
  S.workspace = data.workspace; S.revision = data.revision; S.loaded = true; S.online = true;
  if (!activeTopics(S.workspace).some(topic => topic.id === S.topicId)) S.topicId = activeTopics(S.workspace)[0]?.id || '';
  const live = new Set(activeIdeas(S.workspace).map(idea => idea.id));
  S.selected = new Set([...S.selected].filter(id => live.has(id)));
  if (!activeIdeas(S.workspace).some(idea => idea.id === S.focusId && idea.topicId === S.topicId)) S.focusId = null;
  if (previousCapture && previousCapture !== captureKey()) restoreCapture();
  banner(); status('已保存到电脑 · 设备间自动同步');
}
async function loadState(quiet = false) {
  try {
    const data = await api('/api/state'); const changed = data.revision !== S.revision || !S.loaded;
    const previousCapture = captureKey();
    if (S.loaded) stashCapture();
    adopt(data); if (changed || !quiet) render();
    if (previousCapture !== captureKey()) restoreCapture();
  } catch (error) {
    S.online = false; status('未连接电脑 · 草稿仍留在此设备', 'offline');
    if (error.status !== 401) banner('暂时无法连接电脑。请保持电脑服务运行；当前输入会保留为此设备的草稿。');
  }
}
const guard = (collection, item) => ({ collection, id: item.id, before: JSON.stringify(item) });
function guardsMatch(workspace, guards) { return guards.every(g => JSON.stringify(workspace[g.collection].find(item => item.id === g.id)) === g.before); }
async function mutate(change, guards = []) {
  if (S.saving) throw new Error('上一条记录正在保存，请稍候。');
  if (!S.loaded) throw new Error('请先连接电脑工作空间。');
  S.saving = true; status('正在保存…', 'busy');
  try {
    if (!guardsMatch(S.workspace, guards)) throw Object.assign(new Error('另一台设备已经修改了这条内容。你的编辑仍保留，请另存为新灵感或重新打开最新记录。'), { code: 'LOCAL_CONFLICT' });
    let next = structuredClone(S.workspace); change(next);
    let result;
    try { result = await api('/api/state', 'PUT', { revision: S.revision, workspace: next }); }
    catch (error) {
      if (error.status !== 409) throw error;
      const latest = await api('/api/state');
      if (!guardsMatch(latest.workspace, guards)) {
        adopt(latest); render();
        throw Object.assign(new Error('另一台设备已经修改了同一内容。你的编辑仍保留，请另存为新灵感或重新打开最新记录。'), { code: 'LOCAL_CONFLICT' });
      }
      next = structuredClone(latest.workspace); change(next);
      result = await api('/api/state', 'PUT', { revision: latest.revision, workspace: next });
    }
    adopt(result); render(); return result;
  } catch (error) {
    status(error.code === 'LOCAL_CONFLICT' || error.status === 409 ? '检测到同步冲突 · 编辑未被覆盖' : '保存未完成 · 请保留当前输入', 'offline');
    throw error;
  } finally { S.saving = false; }
}
function currentTopic() { return activeTopics(S.workspace).find(topic => topic.id === S.topicId); }
function topicItems(topicId = S.topicId) { return activeIdeas(S.workspace).filter(idea => idea.topicId === topicId); }
function focusedIdea() { return activeIdeas(S.workspace).find(idea => idea.id === S.focusId && idea.topicId === S.topicId); }
function currentPool() {
  const all = activeIdeas(S.workspace);
  if (S.search || S.page === 'all') return all;
  return scopedIdeas(S.workspace, S.focusId ? [S.focusId] : null, true, S.topicId);
}
function visibleIdeas() {
  let items = currentPool();
  if (S.filter !== 'all') items = items.filter(idea => idea.kind === S.filter);
  if (S.search) {
    const q = S.search.toLocaleLowerCase();
    items = items.filter(idea => [idea.title, idea.body, idea.source, ...idea.tags, S.workspace.topics.find(t => t.id === idea.topicId)?.title].join('\n').toLocaleLowerCase().includes(q));
  }
  return sortedIdeas(items, S.sort);
}
function selectTopic(id) {
  stashCapture(); S.topicId = id; S.focusId = null; S.page = 'topic'; S.search = ''; S.filter = 'all'; S.selected.clear();
  $('#search-input').value = ''; writeLocal('topic', id); render(); restoreCapture(); closeSidebar();
}
function focusQuestion(id) {
  const idea = activeIdeas(S.workspace).find(item => item.id === id); if (!idea) return;
  stashCapture(); S.topicId = idea.topicId; S.focusId = id; S.page = 'topic'; S.search = ''; S.filter = 'all'; S.selected.clear();
  $('#search-input').value = ''; writeLocal('topic', S.topicId); render(); restoreCapture(); closeSidebar();
}
function clearFocus() { stashCapture(); S.focusId = null; S.selected.clear(); render(); restoreCapture(); }
function render() {
  const topics = activeTopics(S.workspace), live = activeIdeas(S.workspace), topic = currentTopic();
  $('#topic-list').innerHTML = topics.map(t => `<button class="topic-button ${S.page === 'topic' && !S.search && S.topicId === t.id ? 'active' : ''}" data-topic="${esc(t.id)}" title="${esc(t.title)}"><span class="topic-icon color-${t.color}">${icon(TEMPLATES[t.template]?.icon || 'sprout')}</span><span class="topic-name">${esc(t.title)}</span><span class="topic-count">${live.filter(i => i.topicId === t.id).length}</span></button>`).join('');
  $('#all-count').textContent = live.length;
  $('#overview-button').classList.toggle('active', S.page === 'all');
  $('#trash-button').classList.toggle('active', S.page === 'trash');
  $('#trash-count').textContent = S.workspace.topics.filter(t => t.deletedAt).length + S.workspace.ideas.filter(i => i.deletedAt && topics.some(t => t.id === i.topicId)).length;
  const general = S.page !== 'topic' || S.search || !topic;
  $('#breadcrumb-topic').textContent = S.page === 'trash' ? '回收站' : S.search ? '搜索结果' : general ? '所有灵感' : topic.title;
  $('#page-title').textContent = S.page === 'trash' ? '让想法，有回来的路。' : S.search ? `找到与你有关的灵感` : general ? '让想法慢慢成形。' : topic.title;
  $('#page-eyebrow').textContent = S.page === 'trash' ? '暂时放下，不必丢失' : general ? 'EVERY IDEA STARTS SOMEWHERE' : `${TEMPLATES[topic.template]?.name || '自由主题'} / MY CREATIVE SPACE`;
  $('#page-description').textContent = S.page === 'trash' ? '移走的主题与灵感保留在这里，随时可以恢复。' : S.search ? `正在所有主题中搜索「${S.search}」` : general ? '给零碎的思考一个落点，把小小的念头连成新的可能。' : topic.description || '这个主题，正在等待你的下一条灵感。';
  $('#edit-topic-button').hidden = general; $('#export-button').hidden = general;
  $('#topic-brief').hidden = general; $('#quick-capture').hidden = general;
  const focused = !general && focusedIdea();
  $('#focus-banner').hidden = !focused;
  $('#focus-banner').innerHTML = focused ? `<div><span class="tiny-label">正在聚焦一个问题</span><strong>${esc(focused.title)}</strong><p>这里的新记录将延伸自此问题；AI 默认处理此问题及其分支。</p></div><button class="button secondary" data-action="clear-focus">${icon('arrow-right')}返回主题全部问题</button>` : '';
  $('#capture-scope').textContent = focused ? `延伸自：${focused.title}` : '作为这个主题下的新主问题';
  $('#quick-input').placeholder = focused ? '围绕这个问题，补充想法、细节或追问……' : '写下一个主问题，或一条准备继续展开的想法……';
  if (!general) {
    const items = topicItems();
    $('#topic-brief').innerHTML = `<span class="brief-icon">${icon('feather')}</span><div class="brief-copy"><span>这个主题，我想做到</span><p>${esc(topic.goal || '还没有明确目标也没关系，先把想法记录下来。')}</p>${topic.context.startsWith('【示例主题') ? '<span class="demo-badge">示例主题 · 可以自由修改或移入回收站</span>' : ''}</div><div class="brief-counts"><div class="brief-stat"><strong>${items.length.toString().padStart(2, '0')}</strong><span>条灵感</span></div><div class="brief-stat"><strong>${items.filter(i => i.parentId).length.toString().padStart(2, '0')}</strong><span>次延伸</span></div></div>`;
  }
  document.querySelectorAll('[data-view]').forEach(el => el.setAttribute('aria-selected', String(el.dataset.view === S.view)));
  $('.view-toolbar').hidden = S.page === 'trash'; $('.filter-toolbar').hidden = S.page === 'trash';
  $('#filter-chips').innerHTML = [['all', '全部'], ...Object.entries(KINDS)].map(([key, label]) => `<button class="filter-chip ${S.filter === key ? 'active' : ''}" data-filter="${key}">${esc(label)}</button>`).join('');
  if (S.page === 'trash') renderTrash(); else renderIdeas();
  renderSelection();
}
function card(idea, root = false) {
  const topic = S.workspace.topics.find(t => t.id === idea.topicId), parent = S.workspace.ideas.find(i => i.id === idea.parentId && !i.deletedAt);
  const children = topicItems(idea.topicId).filter(i => i.parentId === idea.id).length;
  return `<article class="idea-card color-${kindColor[idea.kind]} ${S.selected.has(idea.id) ? 'selected' : ''} ${idea.pinned ? 'pinned' : ''}" data-idea="${esc(idea.id)}">
    <div class="card-top"><span class="kind-label kind-${idea.kind}">${icon(kindIcon[idea.kind])}${KINDS[idea.kind]}</span><div class="card-actions"><button class="icon-button ${idea.pinned ? 'is-pinned' : ''}" data-action="pin" data-id="${esc(idea.id)}" aria-label="${idea.pinned ? '取消置顶' : '置顶'}：${esc(idea.title)}" title="${idea.pinned ? '取消置顶' : '置顶'}">${icon('pin')}</button><input type="checkbox" class="card-checkbox" data-select="${esc(idea.id)}" aria-label="选入 AI 任务包：${esc(idea.title)}" ${S.selected.has(idea.id) ? 'checked' : ''}></div></div>
    ${(S.page === 'all' || S.search) ? `<button class="card-parent text-button" data-topic="${esc(idea.topicId)}">${esc(topic?.title)}</button>` : parent ? `<div class="card-parent">${icon('branch')}延伸自 · ${esc(parent.title)}</div>` : ''}
    ${root ? '' : `<h3 class="card-title"><button data-action="edit" data-id="${esc(idea.id)}">${esc(idea.title)}</button></h3>`}<p class="card-body">${esc(idea.body)}</p>
    <div class="card-tags">${idea.tags.map(tag => `<button class="tag" data-tag="${esc(tag)}">${esc(tag)}</button>`).join('')}</div>
    <div class="card-footer"><span class="status-badge status-${idea.status}"><i></i>${STATUSES[idea.status]}</span><span class="card-meta">${children ? `${children} 个分支` : '点击标题编辑'}</span></div>
    <div class="card-bottom-actions"><button class="text-button" data-action="branch" data-id="${esc(idea.id)}">${icon('plus')}写下延伸</button><button class="text-button" data-action="ai-idea" data-mode="organize" data-id="${esc(idea.id)}">AI 完善</button><button class="text-button" data-action="ai-idea" data-mode="develop" data-id="${esc(idea.id)}">AI 发散</button><details class="card-more"><summary>更多</summary><div class="card-more-menu">${idea.parentId ? `<button class="text-button" data-action="promote-idea" data-id="${esc(idea.id)}">提为主问题</button>` : ''}<button class="text-button" data-action="edit" data-id="${esc(idea.id)}">编辑</button><button class="text-button danger-text" data-action="delete-idea" data-id="${esc(idea.id)}">删除</button></div></details></div>
  </article>`;
}
function renderIdeas() {
  const items = visibleIdeas(), groups = questionGroups(currentPool(), items, S.sort);
  $('#idea-count').textContent = `${groups.length} 个主问题 · ${items.length} 条${S.search || S.filter !== 'all' ? '匹配记录' : '记录'}`; $('#empty-state').hidden = !!items.length;
  $('#ideas-container').className = `question-groups${S.view === 'tree' ? ' compact-tree' : ''}`;
  if (!items.length) {
    $('#ideas-container').innerHTML = '';
    $('#empty-state').innerHTML = `${icon('sprout')}<h2>${S.search || S.filter !== 'all' ? '暂时没有匹配的灵感' : '第一条灵感，会从哪里开始？'}</h2><p>${S.search || S.filter !== 'all' ? '换个关键词，或者查看全部类型。' : '一个问题、一句设定，或者一个还说不清的想法。'}</p><button class="button secondary" data-action="${currentTopic() && S.page === 'topic' ? 'capture' : 'new-topic'}">${currentTopic() && S.page === 'topic' ? '写下第一条灵感' : '创建一个主题'}</button>`;
  } else {
    const groupHTML = group => {
    const collapsed = S.collapsed.has(group.root.id) && !S.search && S.filter === 'all' && !S.focusId;
    return `<section class="question-group"><header class="question-group-header"><button class="icon-button group-toggle" data-action="toggle-group" data-id="${esc(group.root.id)}" aria-expanded="${!collapsed}" aria-label="${collapsed ? '展开' : '折叠'}：${esc(group.root.title)}">${icon('arrow-right')}</button><div class="group-heading"><h2><button class="text-button" data-action="edit" data-id="${esc(group.root.id)}">${esc(group.root.title)}</button></h2><small>${group.total - 1} 条延伸${group.matched < group.total ? ` · 命中 ${group.matched} 条，附带上级背景` : ''}${S.search || S.page === 'all' ? ` · ${esc(S.workspace.topics.find(t => t.id === group.root.topicId)?.title)}` : ''}</small></div><div class="group-actions"><button class="text-button" data-action="select-group" data-id="${esc(group.root.id)}">选中整组</button><button class="button secondary" data-action="focus-question" data-id="${esc(group.root.id)}">聚焦这个问题</button></div></header><div class="question-group-body" ${collapsed ? 'hidden' : ''}>${group.items.map(({ idea, depth, contextual }) => `<div class="${depth ? 'branch-item' : 'root-card'}${contextual ? ' is-context' : ''}" style="--branch-depth:${Math.min(depth, 7)}">${depth ? `<div class="tree-label">${icon('branch')}第 ${depth} 层延伸${contextual ? ' · 上级背景' : ''}</div>` : ''}${card(idea, !depth)}</div>`).join('')}</div></section>`;
    };
    $('#ideas-container').innerHTML = S.view === 'board' ? Object.entries(STATUSES).map(([state, label]) => {
      const matching = groups.filter(group => group.root.status === state);
      return `<section class="group-status-section"><h2 class="board-heading"><span class="status-badge status-${state}">${label}</span><small>${matching.length} 个主问题 · 下级延伸完整保留</small></h2>${matching.map(groupHTML).join('') || '<p class="muted">这个状态还没有主问题。</p>'}</section>`;
    }).join('') : groups.map(groupHTML).join('');
  }
}
function renderSelection() {
  const count = S.selected.size; $('#selection-bar').hidden = !count || S.page === 'trash'; $('#clear-selection').hidden = !count;
  const topics = new Set(activeIdeas(S.workspace).filter(i => S.selected.has(i.id)).map(i => i.topicId));
  $('#selection-bar').innerHTML = `<span>${icon('check')}已选 ${count} 条记录${topics.size > 1 ? ' · AI 与导出请按主题分别处理' : ''}</span><button class="text-button" data-action="clear-selection">取消</button><button class="button secondary danger-text" data-action="delete-selected">${icon('trash')}删除所选</button><button class="button secondary" data-action="ai-selected" ${topics.size > 1 ? 'disabled' : ''}>${icon('sparkles')}AI 处理所选</button><button class="button primary" data-action="export-selected" ${topics.size > 1 ? 'disabled' : ''}>导出所选 ${icon('arrow-right')}</button>`;
}
function captureKey() { return `capture:${S.topicId}${S.focusId ? `:${S.focusId}` : ''}`; }
function stashCapture() { if (S.topicId && !$('#quick-capture').hidden) writeLocal(captureKey(), $('#quick-input').value || null); }
function restoreCapture() { $('#quick-input').value = readLocal(captureKey(), ''); pendingQuick = readLocal(`pending-${captureKey()}`) || (!S.focusId ? readLocal(`pending-quick:${S.topicId}`) : null); $('#draft-indicator').textContent = $('#quick-input').value ? '已恢复此设备的草稿 · 点击「记下来」后同步' : ''; }
async function saveQuick() {
  const body = $('#quick-input').value.trim(), topic = currentTopic(), parent = focusedIdea(), savedKey = captureKey();
  if (!body) { $('#quick-input').focus(); return; }
  if (!topic) return;
  const now = new Date().toISOString();
  const idea = pendingQuick?.body === body && pendingQuick.topicId === topic.id && pendingQuick.parentId === (parent?.id || null) ? pendingQuick : { id: uid(), topicId: topic.id, parentId: parent?.id || null, title: titleFromBody(body), body, kind: $('#quick-kind').value, status: 'spark', tags: [], pinned: false, source: '', createdAt: now, updatedAt: now, deletedAt: null };
  pendingQuick = idea; writeLocal(`pending-${savedKey}`, idea);
  $('#quick-save').disabled = true;
  try {
    await mutate(ws => { if (!ws.ideas.some(i => i.id === idea.id)) ws.ideas.push(idea); }, [guard('topics', topic), ...(parent ? [guard('ideas', parent)] : [])]);
    writeLocal(`pending-${savedKey}`, null);
    if (!idea.parentId) writeLocal(`pending-quick:${topic.id}`, null);
    if (captureKey() === savedKey && $('#quick-input').value.trim() === body) { pendingQuick = null; $('#quick-input').value = ''; $('#draft-indicator').textContent = ''; }
    if (readLocal(savedKey, '').trim() === body) writeLocal(savedKey, null);
    toast('这条灵感，已经留下来了。');
  }
  catch (error) { toast(error.message, true); stashCapture(); }
  finally { $('#quick-save').disabled = false; }
}
function closeSidebar() { $('#sidebar').classList.remove('open'); $('#sidebar-scrim').hidden = true; $('#sidebar').inert = matchMedia('(max-width: 760px)').matches; }
function confirmAction(title, message, label = '确认') {
  $('#confirm-title').textContent = title; $('#confirm-message').textContent = message; $('#confirm-ok').textContent = label;
  return new Promise(resolve => { const dialog = $('#confirm-dialog'); dialog.returnValue = ''; dialog.addEventListener('close', () => resolve(dialog.returnValue === 'confirm'), { once: true }); dialog.showModal(); });
}
function options(values, selected) { return Object.entries(values).map(([key, label]) => `<option value="${key}" ${key === selected ? 'selected' : ''}>${esc(typeof label === 'string' ? label : label.name)}</option>`).join(''); }
function field(label, name, value = '', multiline = false, help = '', max = 50000) {
  return `<label class="field ${multiline ? 'field-full' : ''}"><span class="form-label">${label}</span>${multiline ? `<textarea class="form-input" name="${name}" rows="3" maxlength="${max}">${esc(value)}</textarea>` : `<input class="form-input" name="${name}" value="${esc(value)}" maxlength="${max}" ${name === 'title' ? 'required' : ''}>`}${help ? `<span class="form-help">${help}</span>` : ''}</label>`;
}
function dialogHead(kicker, title, close) { return `<div class="dialog-header"><div><span class="dialog-kicker">${kicker}</span><h2 id="${close === 'editor' ? 'editor-title' : close === 'topic' ? 'topic-dialog-title' : `${close}-title`}">${title}</h2></div><button class="icon-button" type="button" data-close="${close}-dialog" aria-label="关闭">${icon('close')}</button></div>`; }
function formValues(form) { return Object.fromEntries(new FormData(form)); }
function openEditor(id = null, parentId = null) {
  if (!id && !parentId) parentId = focusedIdea()?.id || null;
  const existing = S.workspace.ideas.find(i => i.id === id), topic = existing ? S.workspace.topics.find(t => t.id === existing.topicId) : currentTopic();
  if (!topic) { openTopic(); return; }
  const parent = S.workspace.ideas.find(i => i.id === parentId), draftKey = `editor:${id || `new:${topic.id}:${parentId || ''}`}`;
  const initial = existing || { title: '', body: '', kind: 'idea', status: 'spark', source: '', tags: [], parentId };
  const savedDraft = readLocal(draftKey), value = savedDraft?.values || initial;
  editorSession = { existing: existing ? structuredClone(existing) : null, topic: structuredClone(topic), draftKey, parentId };
  const blocked = existing ? descendants(S.workspace.ideas, existing.id) : new Set();
  const parentOptions = topicItems(topic.id).filter(i => !blocked.has(i.id));
  $('#editor-content').innerHTML = `${dialogHead(parent ? '沿着一个想法，再走一步' : '给想法多一点空间', existing ? '整理这条灵感' : '记下一条新灵感', 'editor')}
    <form id="editor-form"><div class="dialog-body">${parent ? `<div class="branch-callout">${icon('branch')}延伸自 <strong>${esc(parent.title)}</strong><p>${esc(parent.body.slice(0, 150))}</p></div>` : ''}${savedDraft ? '<p class="form-help">已恢复此设备上次未保存的编辑。保存前会检查设备间冲突。</p>' : ''}
    ${field('给它一个标题', 'title', value.title, false, '', 200)}<div class="editor-content-area">${field('思考、细节与还没想清楚的部分', 'body', value.body, true, '原样记录就好，不需要先组织成完美的表达。', 100000)}</div>
    <div class="form-grid"><label class="field"><span class="form-label">内容类型</span><select class="form-input" name="kind">${options(KINDS, value.kind)}</select></label><label class="field"><span class="form-label">整理状态</span><select class="form-input" name="status">${options(STATUSES, value.status)}</select></label>
    ${field('标签', 'tags', Array.isArray(value.tags) ? value.tags.join('，') : value.tags, false, '逗号分隔，最多 12 个，每个最多 100 字。', 500)}<label class="field"><span class="form-label">延伸自</span><select class="form-input" name="parentId"><option value="">独立灵感 · 没有上级</option>${parentOptions.map(i => `<option value="${esc(i.id)}" ${i.id === (value.parentId ?? parentId) ? 'selected' : ''}>${esc(i.title)}</option>`).join('')}</select></label></div>
    ${field('资料来源／记录依据（选填）', 'source', value.source, false, '可以写链接、日期，或注明“原作事实／自设／待核实”。', 2000)}
    <p class="form-error" id="editor-error" role="alert"></p><p class="form-help" id="editor-draft-status">输入会暂存为此设备的草稿，点击保存后同步。</p><button class="text-button" type="button" id="discard-editor-draft">放弃此草稿，载入已保存的内容</button></div>
    <div class="dialog-footer">${existing ? `<button class="text-button danger-text" type="button" data-action="delete-idea" data-id="${esc(existing.id)}">${icon('trash')}移入回收站</button><button class="button secondary" type="button" id="save-copy-button">另存为新灵感</button>` : '<button class="button secondary" type="button" data-close="editor-dialog">稍后继续</button>'}<button class="button primary" type="submit" id="editor-save">${icon('check')}保存灵感</button></div></form>`;
  const form = $('#editor-form');
  form.addEventListener('input', () => { if (writeLocal(draftKey, { values: formValues(form), base: editorSession.existing })) $('#editor-draft-status').textContent = '草稿已暂存于此设备 · 尚未同步'; });
  form.addEventListener('submit', event => { event.preventDefault(); saveEditor(false); });
  $('#save-copy-button')?.addEventListener('click', () => saveEditor(true));
  $('#discard-editor-draft').addEventListener('click', async () => {
    if (!await confirmAction('放弃当前未保存的编辑？', '原始记录保持不变。此设备的当前编辑稿会被清除，再载入电脑上的最新内容。', '载入最新内容')) return;
    try { const latest = await api('/api/state'); adopt(latest); writeLocal(draftKey, null); $('#editor-dialog').close(); render(); openEditor(id, parentId); }
    catch (error) { $('#editor-error').textContent = error.message; }
  });
  if (savedDraft?.base && existing) editorSession.existing = savedDraft.base;
  $('#editor-dialog').showModal();
}
async function saveEditor(asCopy) {
  if (S.saving) return;
  const session = editorSession, values = formValues($('#editor-form'));
  if (!values.title.trim()) { $('#editor-form [name=title]').focus(); return; }
  const tags = [...new Set(values.tags.split(/[,，\n]/).map(t => t.trim()).filter(Boolean))];
  if (tags.length > 12 || tags.some(t => t.length > 100)) { $('#editor-error').textContent = '最多 12 个标签，每个最多 100 字。'; return; }
  const now = new Date().toISOString(), item = { id: asCopy || !session.existing ? uid() : session.existing.id, topicId: session.topic.id, parentId: values.parentId || null, title: values.title.trim(), body: values.body, kind: values.kind, status: values.status, source: values.source, tags, pinned: session.existing?.pinned || false, createdAt: asCopy ? now : session.existing?.createdAt || now, updatedAt: now, deletedAt: null };
  $('#editor-save').disabled = true; $('#editor-error').textContent = ''; $('#editor-form').inert = true;
  try {
    if (asCopy) await loadState(true);
    await mutate(ws => { const index = ws.ideas.findIndex(i => i.id === item.id); index < 0 ? ws.ideas.push(item) : ws.ideas.splice(index, 1, item); }, session.existing && !asCopy ? [guard('ideas', session.existing), guard('topics', session.topic)] : [guard('topics', session.topic)]);
    writeLocal(session.draftKey, null); $('#editor-dialog').close(); toast(asCopy ? '已另存为新灵感，原记录保留。' : '灵感已保存。');
  } catch (error) { $('#editor-error').textContent = error.message; }
  finally { $('#editor-save').disabled = false; $('#editor-form').inert = false; }
}
function openTopic(id = null) {
  const existing = S.workspace.topics.find(t => t.id === id), draftKey = `topic-editor:${id || 'new'}`;
  const draft = readLocal(draftKey), base = draft?.values || existing || { title: '', description: '', ...TEMPLATES.general, template: 'general' };
  let template = base.template || 'general', color = base.color || 'sage';
  $('#topic-dialog-content').innerHTML = `${dialogHead('给一组想法，一个共同的方向', existing ? '主题设定' : '开启一个新主题', 'topic')}<form id="topic-form"><div class="dialog-body">${draft ? '<p class="form-help">已恢复此设备未保存的主题草稿。</p>' : ''}<div class="template-grid">${Object.entries(STARTERS).map(([key, t]) => `<button class="template-option ${key === template ? 'active' : ''}" type="button" data-template="${key}"><span class="template-icon color-${t.color}">${icon(t.icon)}</span><strong>${t.name}</strong><small>${t.description}</small></button>`).join('')}</div>${!existing ? '<section class="example-library"><h3>添加一个完整示例</h3><p class="form-help">示例按主问题与延伸组织。只添加缺少的示例主题，已有或已删除的内容不会被覆盖或恢复。</p><div class="example-options" id="example-options">正在读取示例…</div></section>' : ''}
    ${field('主题名称', 'title', base.title, false, '世界书、某个角色、一个研究问题……都可以成为主题。', 200)}${field('一句话描述（选填）', 'description', base.description, false, '', 1000)}
    <div class="field"><span class="form-label">主题颜色</span><div class="color-picker">${['sage', 'clay', 'blue', 'lavender', 'gold'].map((c, i) => `<button type="button" class="color-swatch color-${c} ${color === c ? 'selected' : ''}" data-color="${c}" aria-label="${['鼠尾草绿', '陶土', '雾蓝', '薰衣草', '暖金'][i]}">${color === c ? icon('check') : ''}</button>`).join('')}</div></div>
    <details ${existing ? 'open' : ''}><summary>补充主题背景，让 AI 更懂你的意图 <span class="muted">（选填）</span></summary><div class="context-fields">${field('我想做到什么', 'goal', base.goal, true)}${field('背景与已有基础', 'context', base.context, true)}${field('需要保留的约束', 'constraints', base.constraints, true)}${field('最后希望得到什么', 'output', base.output, true)}</div></details>
    <p class="form-error" id="topic-error" role="alert"></p><button class="text-button" type="button" id="discard-topic-draft">放弃此草稿，载入已保存的内容</button></div><div class="dialog-footer">${existing ? `<button class="text-button danger-text" type="button" data-action="delete-topic" data-id="${esc(existing.id)}">移入回收站</button>` : '<span class="form-help">先起个名字，其他的可以慢慢补充。</span>'}<button class="button primary" type="submit" id="topic-save">${existing ? '保存主题' : '创建主题'} ${icon('arrow-right')}</button></div></form>`;
  const form = $('#topic-form');
  const stash = () => writeLocal(draftKey, { values: { ...formValues(form), template, color }, base: draft?.base || existing || null });
  form.addEventListener('input', stash);
  $('#discard-topic-draft').addEventListener('click', async () => {
    if (!await confirmAction('放弃当前主题草稿？', '清除此设备尚未保存的编辑，并载入电脑上的最新主题设定。', '载入最新内容')) return;
    try { const latest = await api('/api/state'); adopt(latest); writeLocal(draftKey, null); $('#topic-dialog').close(); render(); openTopic(id); }
    catch (error) { $('#topic-error').textContent = error.message; }
  });
  form.querySelectorAll('[data-template]').forEach(button => button.addEventListener('click', () => {
    template = button.dataset.template; const t = STARTERS[template];
    for (const key of ['goal', 'context', 'constraints', 'output']) { if (!form.elements[key].value.trim() || Object.values(STARTERS).some(x => x[key] === form.elements[key].value)) form.elements[key].value = t[key]; }
    form.querySelectorAll('[data-template]').forEach(el => el.classList.toggle('active', el === button)); stash();
  }));
  form.querySelectorAll('[data-color]').forEach(button => button.addEventListener('click', () => { color = button.dataset.color; form.querySelectorAll('[data-color]').forEach(el => { el.classList.toggle('selected', el === button); el.innerHTML = el === button ? icon('check') : ''; }); stash(); }));
  form.addEventListener('submit', async event => {
    event.preventDefault(); if (S.saving) return; const v = formValues(form); if (!v.title.trim()) return;
    const now = new Date().toISOString(), item = { id: existing?.id || uid(), title: v.title.trim(), description: v.description, goal: v.goal, context: v.context, constraints: v.constraints, output: v.output, template: STARTERS[template]?.storageTemplate || template, color, createdAt: existing?.createdAt || now, updatedAt: now, archived: existing?.archived || false, deletedAt: null };
    $('#topic-save').disabled = true; form.inert = true;
    try {
      await mutate(ws => { const index = ws.topics.findIndex(t => t.id === item.id); index < 0 ? ws.topics.push(item) : ws.topics.splice(index, 1, item); }, existing ? [guard('topics', draft?.base || existing)] : []);
      writeLocal(draftKey, null); $('#topic-dialog').close(); selectTopic(item.id); toast(existing ? '主题设定已保存。' : '新的主题，已经准备好了。');
    } catch (error) { $('#topic-error').textContent = error.message; }
    finally { $('#topic-save').disabled = false; form.inert = false; }
  });
  $('#topic-dialog').showModal();
  if (!existing) loadExamples($('#example-options'));
}

async function loadExamples(container) {
  try {
    const seed = await api('/seed.json'); if (!container.isConnected) return;
    const missing = seed.topics.filter(topic => !S.workspace.topics.some(existing => existing.id === topic.id));
    container.innerHTML = missing.length ? missing.map(topic => `<article class="example-card"><div><strong>${esc(topic.title)}</strong><p>${esc(topic.description)}</p><small>${seed.ideas.filter(idea => idea.topicId === topic.id).length} 条示例记录</small></div><button class="button secondary" type="button" data-import-example="${esc(topic.id)}">添加示例主题</button></article>`).join('') : '<p class="form-help">当前示例已添加过；删除过的示例不会重新出现。</p>';
    container.querySelectorAll('[data-import-example]').forEach(button => button.addEventListener('click', async () => {
      button.disabled = true;
      try { await mutate(ws => importExamples(ws, seed, [button.dataset.importExample])); $('#topic-dialog').close(); selectTopic(button.dataset.importExample); toast('示例主题已添加，可以逐条修改。'); }
      catch (error) { toast(error.message, true); if (button.isConnected) button.disabled = false; }
    }));
  } catch (error) { if (container.isConnected) container.textContent = `示例暂时无法读取：${error.message}`; }
}
function chooseDeletion(selectedIds) {
  const dialog = $('#delete-dialog');
  const update = () => {
    const subtree = deletionPlan(S.workspace, selectedIds, 'subtree'), selected = deletionPlan(S.workspace, selectedIds, 'selected');
    $('#delete-description').textContent = `已选 ${selected.selected} 条记录。删除后仍可在回收站恢复。`;
    $('#delete-subtree-count').textContent = `共移入回收站 ${subtree.ids.size} 条（含 ${subtree.ids.size - selected.selected} 条未单独选择的后代）。`;
    $('#delete-selected-count').textContent = `删除 ${selected.ids.size} 条，保留 ${selected.preserved} 条延伸，重新连接 ${selected.reparent.length} 条分支起点。`;
    const mode = dialog.querySelector('[name=delete-mode]:checked').value;
    $('#delete-confirm').textContent = `移入回收站（${mode === 'subtree' ? subtree.ids.size : selected.ids.size} 条）`;
  };
  dialog.querySelector('[value=subtree]').checked = true; dialog.returnValue = ''; dialog.onchange = update; update();
  return new Promise(resolve => { dialog.addEventListener('close', () => resolve(dialog.returnValue === 'confirm' ? dialog.querySelector('[name=delete-mode]:checked').value : null), { once: true }); dialog.showModal(); });
}
async function deleteSelection(selectedIds) {
  const chosen = activeIdeas(S.workspace).filter(idea => selectedIds.includes(idea.id)); if (!chosen.length) return;
  const mode = await chooseDeletion(chosen.map(idea => idea.id)); if (!mode) return;
  try {
    let result;
    await mutate(ws => { result = deleteIdeas(ws, chosen.map(idea => idea.id), mode, new Date().toISOString()); }, chosen.map(idea => guard('ideas', idea)));
    $('#editor-dialog').close(); restoreCapture(); toast(`已将 ${result.deleted} 条记录移入回收站${result.preserved ? `，保留 ${result.preserved} 条延伸` : ''}。`);
  } catch (error) { toast(error.message, true); }
}
async function promoteIdea(id) {
  const idea = activeIdeas(S.workspace).find(item => item.id === id); if (!idea?.parentId) return;
  try { await mutate(ws => { const item = ws.ideas.find(item => item.id === id); item.parentId = null; item.updatedAt = new Date().toISOString(); }, [guard('ideas', idea)]); toast('已提为独立主问题，原文与下级延伸完整保留。'); }
  catch (error) { toast(error.message, true); }
}
async function deleteTopic(id) {
  const topic = S.workspace.topics.find(t => t.id === id);
  if (!topic || !await confirmAction('把整个主题移入回收站？', `「${topic.title}」和主题下的灵感会一起收起，恢复主题即可找回。`, '移入回收站')) return;
  try { await mutate(ws => { const t = ws.topics.find(t => t.id === id); t.deletedAt = new Date().toISOString(); t.updatedAt = t.deletedAt; }, [guard('topics', topic)]); $('#topic-dialog').close(); restoreCapture(); toast('主题已移入回收站。'); }
  catch (error) { toast(error.message, true); }
}
function renderTrash() {
  const topics = S.workspace.topics.filter(t => t.deletedAt), liveTopics = new Set(activeTopics(S.workspace).map(t => t.id));
  const ideas = S.workspace.ideas.filter(i => i.deletedAt && liveTopics.has(i.topicId));
  $('#ideas-container').className = 'ideas-grid'; $('#empty-state').hidden = !!(topics.length + ideas.length);
  $('#ideas-container').innerHTML = topics.map(t => `<article class="idea-card"><span class="kind-label">${icon('book')}主题</span><h3>${esc(t.title)}</h3><p class="card-body">${S.workspace.ideas.filter(i => i.topicId === t.id && !i.deletedAt).length} 条灵感随主题保留</p><button class="button secondary" data-action="restore-topic" data-id="${esc(t.id)}">${icon('restore')}恢复主题</button></article>`).join('') + ideas.map(i => `<article class="idea-card"><span class="kind-label">${icon(kindIcon[i.kind])}${KINDS[i.kind]}</span><h3>${esc(i.title)}</h3><p class="card-body">${esc(i.body)}</p><button class="button secondary" data-action="restore-idea" data-id="${esc(i.id)}">${icon('restore')}恢复灵感</button></article>`).join('');
  if (!topics.length && !ideas.length) $('#empty-state').innerHTML = `${icon('sprout')}<h2>这里空空的，刚刚好。</h2><p>移入回收站的主题与灵感会出现在这里。</p>`;
}
async function restoreItem(collection, id) {
  try {
    const item = S.workspace[collection].find(i => i.id === id);
    if (collection === 'ideas') {
      await mutate(ws => restoreIdeas(ws, id, new Date().toISOString()), [guard('ideas', item)]);
    } else await mutate(ws => { ws.topics.find(t => t.id === id).deletedAt = null; }, [guard(collection, item)]);
    toast('已经找回来了。');
  } catch (error) { toast(error.message, true); }
}
async function copyText(text, element) {
  try {
    if (navigator.clipboard && window.isSecureContext) await navigator.clipboard.writeText(text);
    else {
      const area = document.createElement('textarea'); area.value = text; area.style.position = 'fixed'; area.style.opacity = '0'; (element?.closest('dialog') || document.body).append(area); area.select();
      const copied = document.execCommand('copy'); area.remove(); if (!copied) throw new Error('请在预览中全选复制，或下载文件。');
    }
    toast('已复制，可以粘贴给 AI 了。');
  } catch { toast('自动复制未成功。请全选预览手动复制，或点击下载。', true); }
}
function download(text, name, type = 'text/markdown;charset=utf-8') {
  const url = URL.createObjectURL(new Blob([text], { type })), link = document.createElement('a');
  link.href = url; link.download = name.replace(/[<>:"/\\|?*\x00-\x1F]/g, '_'); document.body.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 2000);
}
function openExport(selectedOnly = false) {
  const selected = selectedOnly ? [...S.selected] : S.focusId ? scopedIdeas(S.workspace, [S.focusId], true).map(idea => idea.id) : [], selectedTopic = activeIdeas(S.workspace).find(i => selected.includes(i.id))?.topicId;
  if (new Set(activeIdeas(S.workspace).filter(i => selected.includes(i.id)).map(i => i.topicId)).size > 1) { toast('选中的灵感来自多个主题。请按主题分别生成任务包，避免丢失各自的背景。', true); return; }
  const topicId = selectedTopic || S.topicId, topic = activeTopics(S.workspace).find(t => t.id === topicId);
  if (!topic) { toast('先选择一个主题，再生成任务包。'); return; }
  const snapshot = structuredClone(S.workspace), included = includedIdeas(snapshot, topicId, selected);
  exportSession = { topicId, snapshot, selected, mode: 'organize', dirty: false, extra: '' };
  const previous = readLocal(`export:${topicId}`);
  $('#export-content').innerHTML = `${dialogHead('把思考变成一次清晰的协作', '交给 AI，接着往前走', 'export')}<div class="export-layout"><div class="export-options"><h3>${esc(topic.title)}</h3><p class="muted">主题背景与约束会一并保留。</p><span class="form-label">这一次，希望 AI 怎么帮你？</span><div class="export-modes">${Object.entries(MODES).map(([key, mode]) => `<label class="export-mode"><input type="radio" name="export-mode" value="${key}" ${key === 'organize' ? 'checked' : ''}><span><strong>${mode.name}</strong><small>${mode.description}</small></span></label>`).join('')}</div><label class="field"><span class="form-label">本次补充要求（选填）</span><textarea class="form-input" id="export-extra" rows="4" placeholder="例如：先帮我检查设定之间有没有矛盾。"></textarea></label><div class="export-note">${icon('branch')}带出 ${included.items.length} 条记录${included.contextual ? `，包含 ${included.contextual} 条上级背景` : ''}。${included.omitted ? `其余 ${included.omitted} 条未选入。` : ''}</div><button class="button secondary" id="regenerate-export">重新生成预览</button>${previous ? '<button class="text-button" id="restore-export-draft">恢复上次编辑稿</button>' : ''}</div><div class="export-preview"><div class="preview-heading"><span class="form-label">AI 任务包 · Markdown</span><span class="export-stat" id="export-length"></span></div><textarea class="prompt-preview" id="prompt-preview" aria-label="AI 任务包预览，可直接编辑" spellcheck="false"></textarea><p class="form-help" id="export-edit-status">可直接修改预览；这里的编辑不会改变原始灵感。</p></div></div><div class="dialog-footer"><span class="form-help">复制到任意 AI，或下载保存。</span><button class="button secondary" id="download-export">${icon('download')}下载 .md</button><button class="button primary" id="copy-export">${icon('copy')}复制任务包</button></div>`;
  const generate = () => {
    exportSession.extra = $('#export-extra').value;
    $('#prompt-preview').value = buildPrompt(snapshot, topicId, { mode: exportSession.mode, selectedIds: selected, extra: exportSession.extra });
    exportSession.dirty = false; updateExportLength(); $('#export-edit-status').textContent = '预览已生成。可直接编辑，原始灵感不受影响。';
  };
  generate();
  $('#export-content').querySelectorAll('[name=export-mode]').forEach(input => input.addEventListener('change', async () => {
    if (exportSession.dirty && !await confirmAction('根据新目的重新生成？', '当前编辑稿会保留在此设备，可用「恢复上次编辑稿」找回。', '重新生成')) { $('#export-content').querySelector(`[value="${exportSession.mode}"]`).checked = true; return; }
    exportSession.mode = input.value; generate();
  }));
  $('#regenerate-export').addEventListener('click', async () => { if (!exportSession.dirty || await confirmAction('重新生成预览？', '会根据原始灵感重新生成。手工编辑稿仍保存在此设备。', '重新生成')) generate(); });
  $('#prompt-preview').addEventListener('input', () => { exportSession.dirty = true; updateExportLength(); writeLocal(`export:${topicId}`, $('#prompt-preview').value); $('#export-edit-status').textContent = '编辑稿已暂存于此设备 · 原始灵感未改变'; });
  $('#restore-export-draft')?.addEventListener('click', () => { $('#prompt-preview').value = readLocal(`export:${topicId}`, ''); exportSession.dirty = true; updateExportLength(); $('#export-edit-status').textContent = '已恢复上次手工编辑稿，可能包含不同的选取范围。'; });
  $('#copy-export').addEventListener('click', event => copyText($('#prompt-preview').value, event.currentTarget));
  $('#download-export').addEventListener('click', () => download($('#prompt-preview').value, `${topic.title}-AI任务包.md`));
  $('#export-dialog').showModal();
}
function updateExportLength() { $('#export-length').textContent = `${$('#prompt-preview').value.length.toLocaleString()} 字符`; }
function modelControl(id, label, value = '') {
  return `<label class="field"><span class="form-label">${label}</span><input class="form-input" id="${id}" name="model" list="${id}-options" maxlength="200" value="${esc(value)}" placeholder="选择或手动填写模型；留空沿用默认" aria-describedby="${id}-note"><datalist id="${id}-options"></datalist><small class="form-help" id="${id}-note">模型候选不会被当作可用性保证。</small></label>`;
}
async function loadModels(provider, id) {
  const input = $(`#${id}`), note = $(`#${id}-note`), list = $(`#${id}-options`); if (!input || !note) return;
  note.textContent = '正在读取模型候选…';
  try {
    const result = await api(`/api/ai/models?provider=${encodeURIComponent(provider)}`); if (!input.isConnected) return;
    list.innerHTML = result.models.map(model => `<option value="${esc(model.id)}">${esc(model.name || model.id)}</option>`).join('');
    note.textContent = `${result.warning ? `${result.warning} ` : ''}候选来源：${result.source || '服务返回'}；可手输，是否可用以实际任务结果为准。`;
  } catch (error) { if (note.isConnected) note.textContent = `候选暂不可读，仍可手动填写：${error.message}`; }
}
async function openSettings() {
  $('#settings-content').innerHTML = `${dialogHead('数据留在电脑，灵感流向每个设备', '数据与设备', 'settings')}<div class="dialog-body"><p>正在读取连接信息…</p></div>`;
  $('#settings-dialog').showModal();
  try {
    const [connection, ai] = await Promise.all([api('/api/connection'), api('/api/ai/settings')]);
    $('#settings-content').innerHTML = `${dialogHead('数据留在电脑，灵感流向每个设备', '数据与设备', 'settings')}<div class="dialog-body">
    <section class="settings-section"><h3>${icon('devices')}连接手机与其他设备</h3><p class="muted">让设备连上同一 Wi-Fi，访问下面的地址，然后输入电脑生成的配对码。电脑服务需要保持运行。</p>${connection.addresses?.length ? connection.addresses.map(address => `<div class="connection-address"><a href="${esc(address)}" target="_blank" rel="noreferrer">${esc(address)}</a><button class="icon-button" data-copy-address="${esc(address)}" aria-label="复制连接地址">${icon('copy')}</button></div>`).join('') : '<p class="form-help">未找到局域网地址。请检查电脑的 Wi-Fi 或网线连接。</p>'}
    ${connection.localOwner ? '<div class="settings-row"><button class="button secondary" id="generate-pair">生成配对码</button><span class="form-help">10 分钟有效，使用一次后失效。</span></div><div id="pair-result" class="pair-code-display" hidden></div>' : '<p class="form-help">已作为配对设备连接。配对码只能在电脑本机生成。</p>'}
    <div class="settings-row"><span class="muted">${connection.pairedDevices || 0} 台已配对设备</span>${connection.localOwner ? '<button class="text-button danger-text" id="revoke-devices">断开全部配对设备</button>' : '<button class="text-button" id="logout-device">断开此设备</button>'}</div></section>
    <section class="settings-section"><h3>${icon('sparkles')}AI 助手</h3><p class="muted">先生成整理与完善建议，采纳后保留为新灵感或分支。你的原始记录始终保留。</p><form id="ai-settings-form"><div class="form-grid"><label class="field"><span class="form-label">调用方式</span><select class="form-input" name="provider" ${connection.localOwner ? '' : 'disabled'}><option value="codex" ${ai.provider === 'codex' ? 'selected' : ''}>本地 Codex${ai.codexAvailable ? ' · 已检测到' : ' · 尚未检测到'}</option><option value="api" ${ai.provider === 'api' ? 'selected' : ''}>OpenAI 兼容 API</option></select></label><label class="field"><span class="form-label">自动帮助</span><select class="form-input" name="autoMode" ${connection.localOwner ? '' : 'disabled'}><option value="off" ${ai.autoMode === 'off' ? 'selected' : ''}>关闭 · 由我手动触发</option><option value="organize" ${ai.autoMode === 'organize' ? 'selected' : ''}>记录后自动整理</option><option value="develop" ${ai.autoMode === 'develop' ? 'selected' : ''}>记录后自动发散完善</option></select></label></div><div id="api-settings-fields">${field('API 地址（以 /v1 结尾，或完整接口地址）', 'apiBase', ai.apiBase || '', false, '支持 OpenAI 兼容的 Chat Completions 接口。', 2000)}<label class="field"><span class="form-label">API Key</span><input type="password" class="form-input" name="apiKey" autocomplete="new-password" placeholder="${ai.hasApiKey ? '已保存；留空保留现有密钥' : '只保存在电脑端，不会回显'}" ${connection.localOwner ? '' : 'disabled'}></label></div><div class="ai-model-row">${modelControl('settings-model', '默认模型', ai.model || '')}${field('默认 AI 提示词（选填）', 'customPrompt', ai.customPrompt || '', true, '手动任务可单次修改；自动帮助会使用这里的默认要求。', 12000)}</div><button class="text-button" type="button" id="refresh-settings-models">刷新模型候选（使用已保存的接口设置）</button><p class="form-help">自动模式会在停止输入一段时间后生成建议，会使用已选服务的额度；不会自动采纳或覆盖原文。</p>${connection.localOwner ? '<button class="button secondary" type="submit" id="save-ai-settings">保存 AI 设置</button>' : '<p class="form-help">请在电脑本机修改 AI 设置。</p>'}<p class="form-error" id="ai-settings-error" role="alert"></p></form></section>
    <section class="settings-section"><h3>${icon('download')}备份与恢复</h3><div class="data-stats"><span><strong>${S.workspace.topics.length}</strong> 个主题</span><span><strong>${S.workspace.ideas.length}</strong> 条记录（含回收站）</span></div><p class="muted">完整备份包括主题、灵感、分支关系和回收站，不包含 API 密钥或 AI 任务历史。恢复前会自动保留当前版本。</p><div class="settings-row"><button class="button secondary" id="download-backup">${icon('download')}下载完整备份</button><label class="button secondary" for="restore-file">${icon('upload')}从备份恢复</label><input id="restore-file" type="file" accept=".json,application/json" hidden></div><div id="restore-result" class="restore-preview" hidden></div><p class="form-help">电脑关机时无法同步；手机未提交的文字会作为本机草稿保留。跨网络访问方式见项目使用说明。</p></section></div>`;
    $('#settings-content').querySelectorAll('[data-copy-address]').forEach(button => button.addEventListener('click', () => copyText(button.dataset.copyAddress, button)));
    $('#generate-pair')?.addEventListener('click', async () => {
      try { const result = await api('/api/pair-code', 'POST', {}); $('#pair-result').hidden = false; $('#pair-result').innerHTML = `<span class="form-label">在手机上输入</span><strong class="pair-code-value">${esc(result.code)}</strong><span class="form-help">有效至 ${new Date(result.expiresAt).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })} · 请只分享给自己的设备</span>`; }
      catch (error) { toast(error.message, true); }
    });
    $('#revoke-devices')?.addEventListener('click', async () => { if (await confirmAction('断开全部配对设备？', '其他设备需要重新输入配对码才能连接；电脑上的数据保留。', '断开')) { try { await api('/api/revoke-devices', 'POST', {}); toast('配对设备已断开。'); $('#settings-dialog').close(); } catch (error) { toast(error.message, true); } } });
    $('#logout-device')?.addEventListener('click', async () => { await api('/api/logout', 'POST', {}); $('#settings-dialog').close(); showPair(); });
    const aiForm = $('#ai-settings-form');
    if (!connection.localOwner) aiForm.querySelectorAll('input, select, textarea').forEach(input => { input.disabled = true; });
    const toggleAPI = () => { $('#api-settings-fields').hidden = aiForm.elements.provider.value !== 'api'; };
    toggleAPI();
    const refreshModels = () => loadModels(aiForm.elements.provider.value, 'settings-model'); refreshModels();
    aiForm.elements.provider.addEventListener('change', () => { toggleAPI(); refreshModels(); });
    $('#refresh-settings-models').addEventListener('click', refreshModels);
    aiForm.addEventListener('submit', async event => {
      event.preventDefault(); if (!connection.localOwner) return;
      const values = formValues(aiForm); if (!values.apiKey) delete values.apiKey;
      $('#save-ai-settings').disabled = true;
      try { await api('/api/ai/settings', 'PUT', values); aiForm.elements.apiKey.value = ''; refreshModels(); toast('AI 设置已保存。'); }
      catch (error) { $('#ai-settings-error').textContent = error.message; }
      finally { $('#save-ai-settings').disabled = false; }
    });
    $('#download-backup').addEventListener('click', async () => { try { download(JSON.stringify(await api('/api/backup'), null, 2), `灵感屿-完整备份-${new Date().toISOString().slice(0, 10)}.json`, 'application/json'); } catch (error) { toast(error.message, true); } });
    $('#restore-file').addEventListener('change', restoreBackup);
  } catch (error) { $('#settings-content').innerHTML = `${dialogHead('数据与设备', '暂时无法读取设置', 'settings')}<div class="dialog-body"><p class="form-error">${esc(error.message)}</p></div>`; }
}
async function restoreBackup(event) {
  const file = event.target.files[0]; if (!file) return;
  try {
    if (file.size > 20 * 1024 * 1024) throw new Error('备份文件超过 20 MB，暂时无法读取。工作空间正文上限为 6 MB。');
    const backup = JSON.parse(await file.text());
    if (backup.format !== 'sparkspace-backup' || backup.workspace?.schemaVersion !== 1 || !Array.isArray(backup.workspace.topics) || !Array.isArray(backup.workspace.ideas)) throw new Error('这不是受支持的灵感屿完整备份，当前数据未改变。');
    const accepted = await confirmAction('从这份备份恢复？', `备份含 ${backup.workspace.topics.length} 个主题和 ${backup.workspace.ideas.length} 条灵感。恢复将替换当前工作空间；电脑会保留恢复前的快照。`, '备份当前并恢复');
    if (!accepted) return;
    const result = await api('/api/restore', 'POST', { revision: S.revision, workspace: backup.workspace });
    adopt(result); S.selected.clear(); render(); restoreCapture(); toast('备份已恢复，恢复前的数据已留存。'); $('#settings-dialog').close();
  } catch (error) { toast(error instanceof SyntaxError ? '备份 JSON 格式错误，当前数据未改变。' : error.message, true); }
  finally { event.target.value = ''; }
}

let aiJobs = [], aiPolling = false, aiScope = null;
function scopeForAI(options = {}) {
  const ideaIds = Object.hasOwn(options, 'ideaIds') ? options.ideaIds : S.selected.size ? [...S.selected] : S.focusId && !S.search && S.page === 'topic' ? [S.focusId] : null;
  if (ideaIds && (!ideaIds.length || ideaIds.length > 80)) throw new Error('请选 1–80 条记录；也可以聚焦一个主问题并包含后代。');
  const selected = ideaIds ? scopedIdeas(S.workspace, ideaIds) : [], topics = new Set(selected.map(idea => idea.topicId));
  if (ideaIds && (selected.length !== ideaIds.length || topics.size !== 1)) throw new Error('AI 处理所选需来自同一主题，且记录仍然存在。请按主题分别选择。');
  return { ideaIds, topicId: ideaIds ? selected[0].topicId : Object.hasOwn(options, 'topicId') ? options.topicId : S.page === 'all' || S.search ? null : S.topicId || null, includeDescendants: !!ideaIds && (options.includeDescendants ?? ideaIds.length === 1), mode: options.mode || 'organize' };
}
function renderAIScope() {
  if (!aiScope || !$('#ai-scope-summary')) return;
  const items = scopedIdeas(S.workspace, aiScope.ideaIds, aiScope.includeDescendants, aiScope.topicId);
  const topic = S.workspace.topics.find(item => item.id === aiScope.topicId);
  $('#ai-scope-summary').textContent = aiScope.ideaIds ? `仅处理选中的 ${aiScope.ideaIds.length} 条${aiScope.includeDescendants ? '及其后代' : '，不包含未选后代'}，当前共 ${items.length} 条。上级背景只用于理解，不会成为改写目标。` : `处理${topic ? `主题「${topic.title}」` : '所有主题'}的 ${items.length} 条记录。`;
  $('#ai-scope-titles').textContent = aiScope.ideaIds ? scopedIdeas(S.workspace, aiScope.ideaIds).slice(0, 3).map(idea => idea.title).join(' ／ ') + (aiScope.ideaIds.length > 3 ? ' …' : '') : '';
  $('#ai-include-descendants').disabled = !aiScope.ideaIds;
  $('#ai-include-descendants').checked = aiScope.includeDescendants;
  $('#ai-whole-topic').hidden = !aiScope.ideaIds;
  $('#ai-topic').disabled = !!aiScope.ideaIds;
}
async function openAI(options = {}) {
  try { aiScope = scopeForAI(options); } catch (error) { toast(error.message, true); return; }
  const session = aiScope;
  $('#ai-content').innerHTML = `${dialogHead('围绕当前问题，让思路再向前一步', 'AI 灵感助手', 'ai')}<div class="dialog-body"><div class="ai-toolbar"><div class="ai-run-options"><label class="field"><span class="form-label">所属主题</span><select class="form-input" id="ai-topic"><option value="">所有主题</option>${activeTopics(S.workspace).map(topic => `<option value="${esc(topic.id)}" ${topic.id === aiScope.topicId ? 'selected' : ''}>${esc(topic.title)}</option>`).join('')}</select></label><label class="field"><span class="form-label">请 AI 帮我</span><select class="form-input" id="ai-mode"><option value="organize">整理与完善表达</option><option value="develop">继续发散 · 完善细节</option><option value="classify">推荐主题 · 帮我归类</option></select></label></div><div class="ai-scope-summary"><strong id="ai-scope-summary"></strong><p id="ai-scope-titles"></p><label><input type="checkbox" id="ai-include-descendants"> 包含所选记录的后代</label><button class="text-button" type="button" id="ai-whole-topic">改为处理整个主题</button></div><p class="form-help" id="ai-provider-note">正在读取调用设置…</p><div class="ai-model-row">${modelControl('ai-model', '本次模型')}${field('本次提示词（可修改；清空则不附加）', 'prompt', '', true, '这里只影响本次任务；默认提示词可在设置中保存。', 12000)}</div><div class="settings-row"><button class="text-button" id="refresh-ai-models">刷新模型候选</button><button class="button primary" id="run-ai" disabled>${icon('sparkles')}按以上范围开始</button></div><p class="form-help">整理稿会另存为所属问题的新分支，原始记录保留。</p><p class="form-error" id="ai-run-error" role="alert"></p></div><div class="settings-row"><h3>与当前范围相关的任务</h3><label class="form-help"><input type="checkbox" id="ai-history-all"> 显示全部历史（含旧版未记录范围的任务）</label></div><div class="ai-job-list" id="ai-job-list"><p class="muted">正在读取 AI 记录…</p></div></div><div class="dialog-footer"><span class="form-help">自动帮助使用设置中的默认模型与提示词。</span><button class="button secondary" id="ai-open-settings">${icon('settings')}设置 AI</button></div>`;
  const panel = $('#ai-content'); $('#ai-mode').value = aiScope.mode; $('#ai-dialog').showModal(); renderAIScope();
  $('#ai-topic').addEventListener('change', () => { aiScope.topicId = $('#ai-topic').value || null; renderAIScope(); renderJobs(); });
  $('#ai-include-descendants').addEventListener('change', () => { aiScope.includeDescendants = $('#ai-include-descendants').checked; renderAIScope(); renderJobs(); });
  $('#ai-whole-topic').addEventListener('click', () => { aiScope.ideaIds = null; aiScope.includeDescendants = false; renderAIScope(); renderJobs(); });
  $('#ai-history-all').addEventListener('change', renderJobs);
  $('#ai-open-settings').addEventListener('click', () => { $('#ai-dialog').close(); openSettings(); });
  await refreshJobs();
  let settings;
  try {
    settings = await api('/api/ai/settings'); if (!panel.isConnected || !$('#ai-dialog').open || aiScope !== session) return;
    $('#ai-model').value = settings.model || ''; panel.querySelector('[name=prompt]').value = settings.customPrompt || '';
    $('#ai-provider-note').textContent = `调用方式：${settings.provider === 'api' ? 'OpenAI 兼容 API' : '本地 Codex'}。留空模型使用已保存的默认配置。`;
    $('#run-ai').disabled = false; loadModels(settings.provider, 'ai-model');
  } catch (error) { $('#ai-run-error').textContent = `无法读取调用设置：${error.message}`; return; }
  $('#refresh-ai-models').addEventListener('click', () => loadModels(settings.provider, 'ai-model'));
  $('#run-ai').addEventListener('click', async () => {
    const scope = structuredClone(aiScope), request = { mode: $('#ai-mode').value, topicId: scope.topicId, prompt: panel.querySelector('[name=prompt]').value };
    if (scope.ideaIds) { request.ideaIds = scope.ideaIds; request.includeDescendants = scope.includeDescendants; }
    if ($('#ai-model').value.trim()) request.model = $('#ai-model').value.trim();
    $('#run-ai').disabled = true; $('#ai-run-error').textContent = '';
    try {
      const job = await api('/api/ai/jobs', 'POST', request);
      if (!job.id) throw new Error('服务未返回任务编号，请先查看任务记录，避免重复提交。');
      toast('AI 已按指定范围开始处理，可以继续记录。'); await refreshJobs();
    } catch (error) { $('#ai-run-error').textContent = error.message; }
    finally { if ($('#run-ai')) $('#run-ai').disabled = false; }
  });
}
async function refreshJobs() {
  if (aiPolling || !S.loaded) return;
  aiPolling = true;
  try {
    const data = await api('/api/ai/jobs'); aiJobs = data.jobs;
    if ($('#ai-dialog').open) renderJobs();
    const running = aiJobs.some(job => job.status === 'running' || job.status === 'queued');
    $('#ai-button').innerHTML = `${icon('sparkles')}${running ? 'AI 正在整理…' : 'AI 帮我整理'}`;
  } catch (error) { if ($('#ai-dialog').open && $('#ai-job-list')) $('#ai-job-list').innerHTML = `<p class="form-error">${esc(error.message)}</p>`; }
  finally { aiPolling = false; }
}
function suggestionSource(jobId, index) { return `[AI 建议 · ${jobId} / ${index}]`; }
function renderJobs() {
  if (!$('#ai-job-list')) return;
  const scopeIds = new Set(aiScope ? scopedIdeas(S.workspace, aiScope.ideaIds, aiScope.includeDescendants, aiScope.topicId).map(idea => idea.id) : []);
  const jobs = aiJobs.filter(job => {
    if ($('#ai-history-all')?.checked || !aiScope) return true;
    if (aiScope.ideaIds) return Array.isArray(job.ideaIds) && (job.targetIdeaIds || job.ideaIds).some(id => scopeIds.has(id));
    return !aiScope.topicId || job.topicId === aiScope.topicId || (job.targetIdeaIds || []).some(id => scopeIds.has(id));
  }).sort((a, b) => b.createdAt.localeCompare(a.createdAt));
  $('#ai-job-list').innerHTML = jobs.length ? jobs.map(job => {
    const name = { organize: '整理灵感', develop: '发散完善', classify: '推荐归类' }[job.mode] || 'AI 帮助';
    const label = { queued: '等待中', running: '正在思考', completed: '建议已生成', failed: '未完成' }[job.status] || job.status;
    const topicName = S.workspace.topics.find(t => t.id === job.topicId)?.title || '所有主题';
    const range = job.ideaIds ? `选中 ${job.ideaIds.length} 条${job.includeDescendants ? '及后代' : '，不含未选后代'}${job.targetIdeaIds ? ` · 实际目标 ${job.targetIdeaIds.length} 条` : ''}` : job.targetIdeaIds ? `完整主题范围 · 实际目标 ${job.targetIdeaIds.length} 条` : '旧版任务 · 未记录精确范围';
    return `<section class="ai-job"><div class="ai-job-header"><div><h3>${name} <span class="muted">· ${esc(topicName)}</span></h3><small class="muted">${new Date(job.createdAt).toLocaleString('zh-CN')} · ${job.provider === 'api' ? 'API' : '本地 Codex'}</small><p class="form-help">${range}；模型配置：${esc(job.model || '当时的默认配置，具体模型未记录')}</p></div><span class="ai-job-status status-${job.status}">${label}</span></div>
    ${job.error ? `<p class="form-error">${esc(job.error)}</p>` : ''}${job.status === 'running' || job.status === 'queued' ? '<p class="ai-summary">你的原始笔记会保持原样。AI 完成后，建议会出现在这里。</p>' : ''}
    ${job.result ? `<p class="ai-summary">${esc(job.result.summary)}</p>${job.baseRevision !== S.revision ? '<p class="form-help">生成后工作空间已有更新，请检查建议是否仍适用。</p>' : ''}${job.contextStats?.omittedIdeas ? `<p class="form-help">本次有 ${job.contextStats.omittedIdeas} 条未放入上下文。可缩小到单个主题再次整理。</p>` : ''}<div class="ai-suggestions">${job.result.suggestions.map((suggestion, index) => {
      const target = S.workspace.topics.find(t => t.id === suggestion.topicId), adopted = S.workspace.ideas.some(i => i.source?.includes(suggestionSource(job.id, index)));
      return `<article class="ai-suggestion"><span class="kind-label">${icon(suggestion.type === 'move' ? 'branch' : 'sparkles')}${suggestion.type === 'move' ? `建议归入 ${esc(target?.title || '主题')}` : suggestion.type === 'rewrite' ? '整理与完善建议' : '新的发散方向'}</span><h3>${esc(suggestion.title)}</h3><p class="ai-suggestion-body">${esc(suggestion.body)}</p><p class="ai-reason">${esc(suggestion.reason)}</p><div class="ai-suggestion-actions"><button class="button secondary" data-action="adopt-ai" data-job="${esc(job.id)}" data-index="${index}" ${adopted ? 'disabled' : ''}>${adopted ? '已采纳并保留原文' : suggestion.type === 'move' ? '采用这个归类' : suggestion.ideaId || suggestion.parentId ? '保留为新分支' : '保存为新灵感'}</button></div></article>`;
    }).join('')}</div>` : ''}</section>`;
  }).join('') : `<div class="ai-empty empty-state">${icon('sparkles')}<h2>一起，把思路再理清一点。</h2><p>选择一个主题，AI 会给出整理稿、追问或新的方向。<br>也可以在设置中开启记录后的自动帮助。</p></div>`;
}
async function adoptSuggestion(jobId, index, button) {
  const job = aiJobs.find(j => j.id === jobId), suggestion = job?.result?.suggestions[index]; if (!suggestion) return;
  button.disabled = true;
  try {
    await loadState(true);
    if (S.workspace.ideas.some(i => i.source?.includes(suggestionSource(jobId, index)))) { toast('这条建议已经采纳过了。'); return; }
    const parentId = suggestion.parentId || suggestion.ideaId || (job.ideaIds?.length === 1 ? job.ideaIds[0] : null);
    const original = activeIdeas(S.workspace).find(i => i.id === suggestion.ideaId), parent = activeIdeas(S.workspace).find(i => i.id === parentId);
    const targetId = suggestion.type === 'rewrite' && original ? original.topicId : suggestion.topicId || parent?.topicId || job.topicId || S.topicId;
    const target = activeTopics(S.workspace).find(t => t.id === targetId);
    if (!target) throw new Error('建议对应的主题已不存在，请先恢复主题。');
    const now = new Date().toISOString();
    if (suggestion.type === 'move') {
      if (!original) throw new Error('原始灵感已被移走，请先恢复或重新整理。');
      const branch = descendants(S.workspace.ideas, original.id);
      const scopeTargets = new Set(job.targetIdeaIds || job.ideaIds || []), additional = [...branch].filter(id => !scopeTargets.has(id)).length;
      if (!await confirmAction('采用这个归类？', `将「${original.title}」及其整支共 ${branch.size} 条记录（含回收站记录）归入「${target.title}」。${scopeTargets.size && additional ? `其中 ${additional} 条未纳入本次 AI 处理，移动整支会一并带走。` : ''}原文内容保持不变。`, '确认移动整支')) return;
      const affected = S.workspace.ideas.filter(i => branch.has(i.id));
      await mutate(ws => {
        const currentBranch = descendants(ws.ideas, original.id);
        ws.ideas.filter(i => currentBranch.has(i.id)).forEach(i => { i.topicId = target.id; i.updatedAt = now; });
        const moved = ws.ideas.find(i => i.id === original.id); moved.parentId = null; moved.source = `${moved.source ? `${moved.source}\n` : ''}${suggestionSource(jobId, index)}（归类建议已采纳）`;
      }, [...affected.map(i => guard('ideas', i)), guard('topics', target)]);
    } else {
      if (suggestion.ideaId && !original) throw new Error('原始灵感已移入回收站，请先恢复后再采纳这个整理稿。');
      if (parentId && !parent) throw new Error('建议所属的主问题或上级记录已被删除，请恢复后再采纳。');
      if (job.ideaIds?.length && !parent) throw new Error('建议缺少所属问题，未将它保存为无关联的新卡片。请重新整理这个问题。');
      const item = { id: uid(), topicId: target.id, parentId: parent?.topicId === target.id ? parent.id : null, title: suggestion.title, body: suggestion.body, kind: suggestion.kind, status: 'shaping', tags: suggestion.tags, pinned: false, source: suggestionSource(jobId, index), createdAt: now, updatedAt: now, deletedAt: null };
      await mutate(ws => { if (!ws.ideas.some(i => i.source?.includes(item.source))) ws.ideas.push(item); }, [guard('topics', target), ...(parent ? [guard('ideas', parent)] : [])]);
    }
    toast('建议已采纳，原始表达完整保留。'); renderJobs();
  } catch (error) { toast(error.message, true); }
  finally { if (button.isConnected) button.disabled = false; }
}
function showPair() {
  S.online = false;
  document.querySelectorAll('dialog[open]').forEach(dialog => { if (dialog.id !== 'pair-dialog') dialog.close(); });
  if (!$('#pair-dialog').open) $('#pair-dialog').showModal();
}
$('#pair-dialog').addEventListener('cancel', event => event.preventDefault());
$('#pair-form').addEventListener('submit', async event => {
  event.preventDefault(); $('#pair-error').textContent = '';
  const button = $('#pair-form button'); button.disabled = true;
  try { await api('/api/pair', 'POST', { code: $('#pair-code').value.trim() }); $('#pair-code').value = ''; $('#pair-dialog').close(); await loadState(); restoreCapture(); toast('已连接你的电脑工作空间。'); }
  catch (error) { $('#pair-error').textContent = error.message; }
  finally { button.disabled = false; }
});
document.addEventListener('click', async event => {
  const close = event.target.closest('[data-close]'); if (close) { if ($('#editor-form')?.inert || $('#topic-form')?.inert) { toast('正在保存，请稍候。'); return; } $(`#${close.dataset.close}`).close(); return; }
  const topic = event.target.closest('[data-topic]'); if (topic) { selectTopic(topic.dataset.topic); return; }
  const filter = event.target.closest('[data-filter]'); if (filter) { S.filter = filter.dataset.filter; render(); return; }
  const view = event.target.closest('[data-view]'); if (view) { S.view = view.dataset.view; writeLocal('view', S.view); render(); return; }
  const tag = event.target.closest('[data-tag]'); if (tag) { S.search = tag.dataset.tag; $('#search-input').value = S.search; render(); return; }
  const action = event.target.closest('[data-action]'); if (!action) return;
  const id = action.dataset.id;
  switch (action.dataset.action) {
    case 'edit': openEditor(id); break;
    case 'branch': { const item = S.workspace.ideas.find(i => i.id === id); if (S.topicId !== item.topicId) selectTopic(item.topicId); openEditor(null, id); break; }
    case 'pin': { const item = S.workspace.ideas.find(i => i.id === id); try { await mutate(ws => { ws.ideas.find(i => i.id === id).pinned = !item.pinned; }, [guard('ideas', item)]); } catch (error) { toast(error.message, true); } break; }
    case 'delete-idea': deleteSelection([id]); break;
    case 'delete-selected': deleteSelection([...S.selected]); break;
    case 'promote-idea': promoteIdea(id); break;
    case 'focus-question': focusQuestion(id); break;
    case 'clear-focus': clearFocus(); break;
    case 'toggle-group': S.collapsed.has(id) ? S.collapsed.delete(id) : S.collapsed.add(id); writeLocal('collapsed', [...S.collapsed]); renderIdeas(); break;
    case 'select-group': scopedIdeas(S.workspace, [id], true).forEach(idea => S.selected.add(idea.id)); render(); break;
    case 'ai-idea': openAI({ ideaIds: [id], includeDescendants: true, mode: action.dataset.mode }); break;
    case 'ai-selected': openAI({ ideaIds: [...S.selected], includeDescendants: false }); break;
    case 'delete-topic': deleteTopic(id); break;
    case 'restore-topic': restoreItem('topics', id); break;
    case 'restore-idea': restoreItem('ideas', id); break;
    case 'clear-selection': S.selected.clear(); render(); break;
    case 'export-selected': openExport(true); break;
    case 'reload': loadState(); break;
    case 'new-topic': openTopic(); break;
    case 'capture': $('#quick-input').focus(); break;
    case 'adopt-ai': adoptSuggestion(action.dataset.job, Number(action.dataset.index), action); break;
  }
});
document.addEventListener('change', event => {
  if (event.target.matches('[data-select]')) {
    const id = event.target.dataset.select; event.target.checked ? S.selected.add(id) : S.selected.delete(id);
    event.target.closest('.idea-card').classList.toggle('selected', event.target.checked); renderSelection();
  }
});
$('#new-topic-small').onclick = $('#new-topic-button').onclick = $('#template-button').onclick = () => openTopic();
$('#edit-topic-button').onclick = () => openTopic(S.topicId);
$('#export-button').onclick = () => openExport(S.selected.size > 0);
$('#ai-button').onclick = () => openAI();
$('#settings-button').onclick = $('#connection-button').onclick = openSettings;
$('#quick-window-button').onclick = async () => { try { await api('/api/quick-window', 'POST', {}); toast('已请求打开悬浮速记窗。'); } catch (error) { toast(error.message, true); } };
$('#quick-save').onclick = saveQuick;
$('#brand-link').onclick = event => { event.preventDefault(); $('#overview-button').click(); };
$('#overview-button').onclick = () => { stashCapture(); S.focusId = null; S.page = 'all'; S.search = ''; S.filter = 'all'; $('#search-input').value = ''; render(); closeSidebar(); };
$('#trash-button').onclick = () => { stashCapture(); S.focusId = null; S.page = 'trash'; S.search = ''; $('#search-input').value = ''; render(); closeSidebar(); };
$('#menu-button').onclick = () => { $('#sidebar').inert = false; $('#sidebar').classList.add('open'); $('#sidebar-scrim').hidden = false; };
$('#sidebar-scrim').onclick = closeSidebar;
$('#select-visible').onclick = () => { visibleIdeas().forEach(i => S.selected.add(i.id)); render(); };
$('#clear-selection').onclick = () => { S.selected.clear(); render(); };
$('#sort-select').onchange = event => { S.sort = event.target.value; renderIdeas(); };
$('#search-input').addEventListener('input', event => { stashCapture(); S.search = event.target.value.trim(); if (S.page === 'trash') S.page = 'all'; render(); });
$('#quick-input').addEventListener('input', () => {
  clearTimeout(captureTimer); captureTimer = setTimeout(() => { if (writeLocal(captureKey(), $('#quick-input').value || null)) $('#draft-indicator').textContent = $('#quick-input').value ? '草稿已暂存于此设备 · 记下来后同步' : ''; }, 250);
});
document.addEventListener('keydown', event => {
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') { event.preventDefault(); if (!document.querySelector('dialog[open]')) $('#search-input').focus(); }
  if ((event.ctrlKey || event.metaKey) && event.key === 'Enter' && !event.isComposing) {
    if (event.target === $('#quick-input')) { event.preventDefault(); saveQuick(); }
    else if ($('#editor-dialog').open) { event.preventDefault(); $('#editor-form').requestSubmit(); }
  }
});
window.addEventListener('beforeunload', event => {
  stashCapture();
  if (S.saving) { event.preventDefault(); event.returnValue = ''; }
});
window.addEventListener('online', () => loadState(true));
matchMedia('(max-width: 760px)').addEventListener('change', closeSidebar);
closeSidebar();
for (const id of ['editor-dialog', 'topic-dialog']) $(`#${id}`).addEventListener('cancel', event => { if ($('#editor-form')?.inert || $('#topic-form')?.inert) event.preventDefault(); });
setInterval(() => {
  if (!S.saving && !$('#editor-dialog').open && !$('#topic-dialog').open && !$('#pair-dialog').open) loadState(true);
  if (S.online && ($('#ai-dialog').open || document.visibilityState === 'visible')) refreshJobs();
}, 4500);
await loadState(); restoreCapture();
api('/api/connection').then(connection => { $('#quick-window-button').hidden = !connection.localOwner; }).catch(() => {});
