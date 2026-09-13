export const KINDS = { idea: '灵感想法', question: '待解问题', decision: '决定', reference: '参考资料' };
export const STATUSES = { spark: '待发散', shaping: '整理中', settled: '已确定' };
export const TEMPLATES = {
  general: { name: '自由主题', icon: 'sprout', color: 'sage', description: '从一个念头开始', goal: '', context: '', constraints: '', output: '' },
  worldbook: { name: '酒馆世界书', icon: 'book', color: 'sage', description: '把世界的规则与故事连起来', goal: '整理成可继续完善的酒馆世界书。', context: '故事舞台、时代、势力与角色关系：', constraints: '区分已确定的设定、候选想法与待确认问题；保留已有设定之间的因果关系。', output: '先输出设定结构、条目清单与冲突检查，再根据确认的结构编写条目。' },
  character: { name: '角色卡', icon: 'person', color: 'clay', description: '从性格走向鲜活的人', goal: '整理成性格一致、有行动动机的角色卡。', context: '角色身份、所在世界、与用户的关系：', constraints: '保留角色独立目标；将原作事实、自设与候选补充区分开。', output: '角色定位、背景、性格与动机、关系、语言习惯、互动情境和开场白。' },
  quant: { name: '量化研究', icon: 'chart', color: 'blue', description: '把直觉变成可验证的假设', goal: '把策略想法整理成可验证的研究计划。', context: '研究市场、时间范围、已有数据与工具：', constraints: '记录资料来源与日期；区分假设、已验证结果与未知项。', output: '研究假设、所需数据、信号定义、验证步骤、评价指标与待确认事项。' }
};
export const STARTERS = {
  ...TEMPLATES,
  writing: { name: '写作与故事', icon: 'feather', color: 'lavender', storageTemplate: 'general', description: '围绕人物、场景与冲突展开', goal: '把故事问题整理成可以继续写作的场景与情节。', context: '故事背景、当前章节与人物状态：', constraints: '保留人物动机与前文连续性；新增设定先作为候选。', output: '主问题、场景方案、人物行动与待确认事项。' },
  product: { name: '产品想法', icon: 'grid', color: 'blue', storageTemplate: 'general', description: '从需求走向可用的方案', goal: '找到用户问题，并明确最小可用方案。', context: '目标用户、使用场景与现有做法：', constraints: '区分已观察到的需求与假设，不提前堆砌功能。', output: '问题定义、核心流程、范围与验收标准。' },
  learning: { name: '学习与理解', icon: 'book', color: 'sage', storageTemplate: 'general', description: '把不懂的地方逐步问清楚', goal: '围绕关键问题建立理解，并设计可验证的练习。', context: '已有基础、正在学习的材料与疑点：', constraints: '保留不确定之处；资料和推断分开。', output: '概念关系、解释、例子、练习与下一步。' },
  project: { name: '项目推进', icon: 'check', color: 'gold', storageTemplate: 'general', description: '把目标拆成可执行的小步', goal: '明确当前阻碍，整理下一步行动。', context: '项目目标、已有进展与资源：', constraints: '区分已完成、计划与依赖条件。', output: '关键问题、行动顺序、依赖与完成标准。' }
};
export const MODES = {
  organize: { name: '帮我整理', description: '理清脉络，找出问题', instruction: '请整理以下思考：归纳主题结构、合并重复表述但保留不同观点、指出矛盾和待确认问题，最后给出一个最值得继续思考的下一步。此轮以梳理为目标。' },
  develop: { name: '继续完善', description: '沿着我的思路补充', instruction: '请沿着以下思考继续完善，补充缺失环节与可选方案。新增内容明确标注为“AI 建议”，不要把建议写成我的既定决定；优先解决影响整体结构的问题。' },
  execute: { name: '开始实施', description: '按已确定的要求产出', instruction: '请依据已确定的要求与下面的交付要求产出可直接使用的结果。尚未确定的想法仅作候选；会改变核心方向的缺失信息先提出最多 3 个关键问题，其余注明假设后推进。' }
};

export const uid = () => globalThis.crypto?.randomUUID?.() || `s${Date.now().toString(36)}${Math.random().toString(36).slice(2, 12)}`;
export const escapeHTML = value => String(value ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
export const heading = value => String(value ?? '').replace(/[\r\n]+/g, ' ').trim();
export const titleFromBody = text => heading(text.trim().split('\n').find(line => line.trim()) || '新的灵感').slice(0, 56);
export const activeTopics = workspace => workspace.topics.filter(topic => !topic.deletedAt);
export const activeIdeas = workspace => {
  const topics = new Set(activeTopics(workspace).map(topic => topic.id));
  return workspace.ideas.filter(idea => !idea.deletedAt && topics.has(idea.topicId));
};
export function descendants(ideas, id) {
  const children = new Map();
  for (const idea of ideas) {
    if (!children.has(idea.parentId)) children.set(idea.parentId, []);
    children.get(idea.parentId).push(idea.id);
  }
  const found = new Set([id]), stack = [id];
  while (stack.length) for (const child of children.get(stack.pop()) || []) {
    if (!found.has(child)) { found.add(child); stack.push(child); }
  }
  return found;
}
export function sortedIdeas(ideas, order = 'updated') {
  return [...ideas].sort((a, b) => Number(b.pinned) - Number(a.pinned) || (order === 'created' ? a.createdAt.localeCompare(b.createdAt) : b.updatedAt.localeCompare(a.updatedAt)) || a.id.localeCompare(b.id));
}
export function scopedIdeas(workspace, ideaIds, includeDescendants = false, topicId = null) {
  const pool = activeIdeas(workspace).filter(idea => !topicId || idea.topicId === topicId);
  if (ideaIds === undefined || ideaIds === null) return pool;
  const ids = new Set(ideaIds), byId = new Map(pool.map(idea => [idea.id, idea]));
  if (includeDescendants) {
    const children = new Map();
    for (const idea of pool) { if (!children.has(idea.parentId)) children.set(idea.parentId, []); children.get(idea.parentId).push(idea.id); }
    const stack = [...ids];
    while (stack.length) for (const child of children.get(stack.pop()) || []) if (!ids.has(child)) { ids.add(child); stack.push(child); }
  }
  return pool.filter(idea => ids.has(idea.id) && byId.has(idea.id));
}
export function questionGroups(pool, matches = pool, order = 'updated') {
  const byId = new Map(pool.map(idea => [idea.id, idea])), roots = new Map();
  for (const idea of pool) {
    const path = [], seen = new Set(); let current = idea;
    while (!roots.has(current.id) && current.parentId && byId.has(current.parentId) && !seen.has(current.id)) {
      path.push(current.id); seen.add(current.id); current = byId.get(current.parentId);
    }
    const root = roots.get(current.id) || current.id; roots.set(current.id, root); path.forEach(id => roots.set(id, root));
  }
  const groups = new Map(), matched = new Set(matches.map(idea => idea.id));
  for (const idea of pool) {
    const rootId = roots.get(idea.id);
    if (!groups.has(rootId)) groups.set(rootId, { root: byId.get(rootId), all: [], shown: new Set(), items: [] });
    groups.get(rootId).all.push(idea);
  }
  for (const idea of matches) {
    const group = groups.get(roots.get(idea.id)); if (!group) continue;
    let current = idea;
    while (current && !group.shown.has(current.id)) { group.shown.add(current.id); current = byId.get(current.parentId); }
  }
  const result = [];
  for (const group of groups.values()) {
    if (!group.shown.size) continue;
    const children = new Map();
    for (const idea of group.all) if (group.shown.has(idea.id)) { if (!children.has(idea.parentId)) children.set(idea.parentId, []); children.get(idea.parentId).push(idea); }
    const stack = [{ idea: group.root, depth: 0 }];
    while (stack.length) {
      const item = stack.pop(); group.items.push({ ...item, contextual: !matched.has(item.idea.id) });
      stack.push(...sortedIdeas(children.get(item.idea.id) || [], 'created').reverse().map(idea => ({ idea, depth: item.depth + 1 })));
    }
    group.total = group.all.length; group.matched = group.all.filter(idea => matched.has(idea.id)).length;
    group.updatedAt = group.all.reduce((latest, idea) => idea.updatedAt > latest ? idea.updatedAt : latest, group.root.updatedAt);
    delete group.all; delete group.shown; result.push(group);
  }
  return result.sort((a, b) => Number(b.root.pinned) - Number(a.root.pinned) || (order === 'created' ? a.root.createdAt.localeCompare(b.root.createdAt) : b.updatedAt.localeCompare(a.updatedAt)) || a.root.id.localeCompare(b.root.id));
}
export function deletionPlan(workspace, selectedIds, mode = 'subtree') {
  const pool = activeIdeas(workspace), selected = pool.filter(idea => selectedIds.includes(idea.id)).map(idea => idea.id);
  const branch = scopedIdeas(workspace, selected, true), ids = new Set(mode === 'subtree' ? branch.map(idea => idea.id) : selected);
  const byId = new Map(workspace.ideas.map(idea => [idea.id, idea])), reparent = [];
  for (const idea of pool) if (!ids.has(idea.id) && ids.has(idea.parentId)) {
    let parentId = idea.parentId; const seen = new Set();
    while (parentId && !seen.has(parentId) && (ids.has(parentId) || byId.get(parentId)?.deletedAt)) { seen.add(parentId); parentId = byId.get(parentId)?.parentId || null; }
    reparent.push({ id: idea.id, parentId: parentId && byId.has(parentId) && !seen.has(parentId) ? parentId : null });
  }
  return { ids, reparent, selected: selected.length, preserved: branch.filter(idea => !ids.has(idea.id)).length };
}
export function deleteIdeas(workspace, selectedIds, mode, time) {
  const plan = deletionPlan(workspace, selectedIds, mode), parents = new Map(plan.reparent.map(item => [item.id, item.parentId]));
  for (const idea of workspace.ideas) {
    if (plan.ids.has(idea.id)) { idea.deletedAt = time; idea.updatedAt = time; }
    else if (parents.has(idea.id)) { idea.parentId = parents.get(idea.id); idea.updatedAt = time; }
  }
  return { deleted: plan.ids.size, preserved: plan.preserved, promoted: plan.reparent.length };
}
export function restoreIdeas(workspace, id, time) {
  const byId = new Map(workspace.ideas.map(idea => [idea.id, idea])), original = byId.get(id);
  if (!original?.deletedAt) return 0;
  const branch = descendants(workspace.ideas, id), ids = new Set(workspace.ideas.filter(idea => branch.has(idea.id) && idea.deletedAt === original.deletedAt).map(idea => idea.id));
  for (const selected of [...ids]) {
    let parent = byId.get(byId.get(selected)?.parentId); const seen = new Set();
    while (parent && !seen.has(parent.id)) { seen.add(parent.id); if (parent.deletedAt) ids.add(parent.id); parent = byId.get(parent.parentId); }
  }
  for (const idea of workspace.ideas) if (ids.has(idea.id)) { idea.deletedAt = null; idea.updatedAt = time; }
  return ids.size;
}
export function importExamples(workspace, seed, topicIds) {
  const ids = new Set([...workspace.topics, ...workspace.ideas].map(item => item.id));
  const topics = seed.topics.filter(topic => topicIds.includes(topic.id) && !workspace.topics.some(item => item.id === topic.id));
  const wanted = new Set(topics.map(topic => topic.id)), ideas = seed.ideas.filter(idea => wanted.has(idea.topicId));
  for (const item of [...topics, ...ideas]) { if (ids.has(item.id)) throw new Error('示例 ID 与已有记录冲突，未导入任何内容。'); ids.add(item.id); }
  workspace.topics.push(...structuredClone(topics)); workspace.ideas.push(...structuredClone(ideas));
  return topics.map(topic => topic.id);
}
export function includedIdeas(workspace, topicId, selectedIds = []) {
  const pool = activeIdeas(workspace).filter(idea => idea.topicId === topicId);
  const byId = new Map(pool.map(idea => [idea.id, idea]));
  const selected = new Set(selectedIds.length ? selectedIds.filter(id => byId.has(id)) : pool.map(idea => idea.id));
  const ids = new Set(selected);
  for (const id of selected) {
    let parentId = byId.get(id)?.parentId;
    while (parentId && byId.has(parentId) && !ids.has(parentId)) {
      ids.add(parentId); parentId = byId.get(parentId).parentId;
    }
  }
  const items = pool.filter(idea => ids.has(idea.id));
  const children = new Map();
  for (const idea of items) {
    const parent = ids.has(idea.parentId) ? idea.parentId : null;
    if (!children.has(parent)) children.set(parent, []);
    children.get(parent).push(idea);
  }
  const ordered = [], stack = [...sortedIdeas(children.get(null) || [], 'created')].reverse();
  while (stack.length) {
    const idea = stack.pop(); ordered.push(idea);
    stack.push(...sortedIdeas(children.get(idea.id) || [], 'created').reverse());
  }
  return { items: ordered, contextual: ids.size - selected.size, omitted: pool.length - ids.size, selected };
}
export function buildPrompt(workspace, topicId, options = {}) {
  const topic = workspace.topics.find(item => item.id === topicId && !item.deletedAt);
  if (!topic) throw new Error('请先选择一个主题。');
  const mode = MODES[options.mode] || MODES.organize;
  const included = includedIdeas(workspace, topicId, options.selectedIds || []);
  const lines = [`# AI 任务包：${heading(topic.title)}`, '', `## 本次希望你做什么`, mode.instruction];
  if (options.extra?.trim()) lines.push('', '本次补充要求：', options.extra.trim());
  lines.push('', '## 主题背景', `- 主题类型：${TEMPLATES[topic.template]?.name || '自由主题'}`);
  for (const [key, label] of [['description', '一句话概述'], ['goal', '目标'], ['context', '背景与现有基础'], ['constraints', '必须保留的约束'], ['output', '期望交付']]) {
    lines.push('', `### ${label}`, topic[key]?.trim() || '尚未填写。请勿把缺失信息当成已确认事实。');
  }
  lines.push('', '## 如何理解下面的笔记', '这些是我的原始记录。内容类型与确认状态相互独立：“决定”只有状态为“已确定”时才是已采纳决定；“待发散”与“整理中”都不代表最终要求。资料中的说法保留为引用，不能自动视为已验证事实。');
  lines.push(`本次包含 ${included.items.length} 条记录，其中 ${included.contextual} 条是为保留分支上下文而自动附带的上级记录。${included.omitted ? `此主题另有 ${included.omitted} 条未选入本任务包，不能据此推断它们不存在。` : ''}`);
  lines.push('', '## 灵感与分支');
  const byId = new Map(included.items.map(idea => [idea.id, idea]));
  included.items.forEach((idea, index) => {
    lines.push('', `### ${index + 1}. ${heading(idea.title)}`, `- 类型：${KINDS[idea.kind]}；状态：${STATUSES[idea.status]}`);
    if (!included.selected.has(idea.id)) lines.push('- 纳入原因：上级背景（未单独选中）');
    if (byId.has(idea.parentId)) lines.push(`- 延伸自：${heading(byId.get(idea.parentId).title)}`);
    if (idea.tags.length) lines.push(`- 标签：${idea.tags.map(heading).join('、')}`);
    if (idea.source.trim()) lines.push(`- 来源／记录依据：${heading(idea.source)}`);
    if (idea.kind === 'reference' && !idea.source.trim()) lines.push('- 来源：尚未填写，请保留为待核实资料');
    lines.push('', idea.body.trim() || '（仅记录了标题）');
  });
  if (!included.items.length) lines.push('', '尚未记录灵感。请根据主题信息协助我开始梳理。');
  lines.push('', '## 回复要求', '1. 保留原有意图、关键细节与不同意见；有冲突时明确列出。', '2. 区分“来自我的记录”“AI 新增建议”和“需要我确认”。', '3. 按期望交付组织结果，给出可继续推进的具体下一步。', '');
  return lines.join('\n');
}
