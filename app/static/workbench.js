const state = {
  environments: [], interfaceOptions: [], interfaces: [], cases: [], caseOptions: [], suites: [], runs: [],
  interfacePage: { page: 1, pages: 1 }, casePage: { page: 1, pages: 1 }, poll: null,
  activeRun: null, watchTimer: null,
};

const $ = id => document.getElementById(id);
const parseJSON = (id, fallback) => {
  const text = $(id).value.trim();
  return text ? JSON.parse(text) : fallback;
};
const apiKey = () => localStorage.getItem('platformApiKey') || '';

async function api(path, options = {}) {
  const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) };
  if (apiKey()) headers['X-API-Key'] = apiKey();
  const response = await fetch(path, { ...options, headers });
  if (response.status === 204) return null;
  const data = await response.json().catch(() => ({ detail: response.statusText }));
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail || data));
  return data;
}

function message(text, type = 'ok') {
  const element = $('message');
  element.textContent = text;
  element.className = `show ${type}`;
  clearTimeout(element.timer);
  element.timer = setTimeout(() => { element.className = ''; }, 5000);
}

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>'"]/g, character => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;',
  }[character]));
}

const statusLabels = {
  queued: '排队中', running: '执行中', passed: '通过', failed: '失败',
  cancelled: '已取消', interrupted: '已中断', skipped: '未执行',
};
const terminalStatuses = new Set(['passed', 'failed', 'cancelled', 'interrupted']);
const badge = status => `<span class="status ${escapeHtml(status)}">${escapeHtml(statusLabels[status] || status)}</span>`;
const elapsed = run => (!run.started_at || !run.finished_at)
  ? '-'
  : `${(Math.max(0, new Date(run.finished_at) - new Date(run.started_at)) / 1000).toFixed(2)}s`;

function activateTab(name) {
  document.querySelectorAll('.tabs button').forEach(item => item.classList.toggle('active', item.dataset.tab === name));
  document.querySelectorAll('.tab-panel').forEach(panel => panel.classList.toggle('active', panel.id === `tab-${name}`));
}

function fillSelect(id, items, emptyLabel = '') {
  const select = $(id);
  const previous = select.value;
  const empty = emptyLabel ? `<option value="">${escapeHtml(emptyLabel)}</option>` : '';
  select.innerHTML = empty + items.map(item => `<option value="${item.id}">#${item.id} ${escapeHtml(item.name)}</option>`).join('');
  if ([...select.options].some(option => option.value === previous)) select.value = previous;
}

function renderPager(prefix, data) {
  const select = $(`${prefix}-page`);
  select.innerHTML = Array.from({ length: data.pages }, (_, index) => `<option value="${index + 1}">${index + 1}</option>`).join('');
  select.value = String(Math.min(data.page, data.pages));
  $(`${prefix}-prev`).disabled = data.page <= 1;
  $(`${prefix}-next`).disabled = data.page >= data.pages;
  $(`${prefix}-page-summary`).textContent = `共 ${data.pages} 页 · ${data.total} 条`;
  $(`${prefix}-total`).textContent = `${data.total} 条`;
}

async function health() {
  try {
    await api('/health');
    $('health-dot').className = 'good';
    $('health-text').textContent = '服务运行正常';
    $('health-detail').textContent = '数据库与API已连接';
  } catch (error) {
    $('health-dot').className = 'bad';
    $('health-text').textContent = '服务不可用';
    $('health-detail').textContent = error.message;
  }
}

async function loadSystemInfo() {
  const info = await api('/system/info');
  $('storage-detail').textContent = `当前数据库：${info.storage} / ${info.database}${info.persistent ? '（持久化）' : '（临时）'}`;
  $('metric-env').textContent = info.counts.environments;
  $('metric-interface').textContent = info.counts.interfaces;
  $('metric-case').textContent = info.counts.cases;
  $('metric-suite').textContent = info.counts.suites;
  $('metric-run').textContent = info.counts.runs;
}

async function loadEnvironments() {
  state.environments = await api('/environments');
  fillSelect('run-environment', state.environments, '不使用环境');
  if (!$('run-environment').value) {
    const demo = state.environments.find(item => item.name === '内置订单服务' && item.enabled);
    if (demo) $('run-environment').value = String(demo.id);
  }
  $('environment-list').innerHTML = state.environments.map(item => `
    <div class="stack-item"><header><b>${escapeHtml(item.name)}</b><span>${item.enabled ? '启用' : '停用'}</span></header>
    <small>${escapeHtml(item.base_url || '未配置 Base URL')}</small>
    <small>变量 ${Object.keys(item.variables || {}).length} · 加密密钥 ${(item.secret_keys || []).map(escapeHtml).join(', ') || '无'} · 公共请求头 ${Object.keys(item.headers || {}).length}</small></div>
  `).join('') || '<div class="empty">暂无环境</div>';
}

async function loadInterfaceOptions() {
  state.interfaceOptions = await api('/interfaces?limit=500');
  fillSelect('run-interface', state.interfaceOptions);
  fillSelect('case-interface', state.interfaceOptions);
  fillSelect('ai-interface', state.interfaceOptions);
  fillSelect('case-filter-interface', state.interfaceOptions, '全部接口');
}

async function loadCaseOptions() {
  state.caseOptions = await api('/cases?enabled=true&limit=500');
  const select = $('suite-cases');
  const selected = new Set([...select.selectedOptions].map(option => option.value));
  select.innerHTML = state.caseOptions.map(item => `<option value="${item.id}">#${item.id} ${escapeHtml(item.case_name)}</option>`).join('');
  [...select.options].forEach(option => { option.selected = selected.has(option.value); });
}

async function loadInterfaces() {
  const params = new URLSearchParams({
    page: String(state.interfacePage.page), page_size: String(Number($('interface-page-size').value)),
  });
  if ($('interface-keyword').value.trim()) params.set('keyword', $('interface-keyword').value.trim());
  if ($('interface-filter-method').value) params.set('method', $('interface-filter-method').value);
  const data = await api(`/interfaces/page?${params}`);
  state.interfaces = data.items;
  state.interfacePage = { page: data.page, pages: data.pages };
  $('interface-list').innerHTML = data.items.map(item => `
    <div class="stack-item"><header><b>#${item.id} ${escapeHtml(item.name)}</b><span class="status running">${item.method}</span></header><small>${escapeHtml(item.url)}</small></div>
  `).join('') || '<div class="empty">没有符合筛选条件的接口</div>';
  renderPager('interface', data);
}

async function loadCases() {
  const params = new URLSearchParams({
    page: String(state.casePage.page), page_size: String(Number($('case-page-size').value)),
  });
  if ($('case-keyword').value.trim()) params.set('keyword', $('case-keyword').value.trim());
  if ($('case-filter-interface').value) params.set('interface_id', $('case-filter-interface').value);
  if ($('case-filter-enabled').value) params.set('enabled', $('case-filter-enabled').value);
  const data = await api(`/cases/page?${params}`);
  state.cases = data.items;
  state.casePage = { page: data.page, pages: data.pages };
  const interfaceNames = Object.fromEntries(state.interfaceOptions.map(item => [item.id, item.name]));
  $('case-list').innerHTML = data.items.map(item => `
    <div class="stack-item"><header><b>#${item.id} ${escapeHtml(item.case_name)}</b><span>${item.enabled ? '启用' : '停用'}</span></header>
    <small>接口 #${item.interface_id} ${escapeHtml(interfaceNames[item.interface_id] || '')} · 预期 ${item.expected_status_code} · 重试 ${item.retry_count}</small>
    <small>断言 ${(item.assertions || []).length} · 提取器 ${(item.extractors || []).length} · 依赖 [${(item.dependencies || []).join(', ')}]</small></div>
  `).join('') || '<div class="empty">没有符合筛选条件的测试用例</div>';
  renderPager('case', data);
}

async function loadSuites() {
  state.suites = await api('/suites');
  fillSelect('run-suite', state.suites);
  const trends = await Promise.all(state.suites.map(async suite => {
    try { return await api(`/suites/${suite.id}/trends?limit=10`); }
    catch (_) { return { run_count: 0, latest_pass_rate: null }; }
  }));
  $('suite-list').innerHTML = state.suites.map((suite, index) => {
    const trend = trends[index];
    const latest = trend.latest_pass_rate == null ? '尚未执行' : `最近通过率 ${trend.latest_pass_rate}%`;
    const caseNames = Object.fromEntries(state.caseOptions.map(item => [item.id, item.case_name]));
    const flow = suite.case_ids.slice(0, 6).map((caseId, stepIndex) =>
      `${stepIndex ? '<i>→</i>' : ''}<span>${stepIndex + 1}. ${escapeHtml(caseNames[caseId] || `用例 #${caseId}`)}</span>`
    ).join('');
    const more = suite.case_ids.length > 6 ? `<span>还有 ${suite.case_ids.length - 6} 步</span>` : '';
    return `<div class="stack-item"><header><b>#${suite.id} ${escapeHtml(suite.name)}</b><span>${suite.enabled ? '启用' : '停用'}</span></header>
      <small>${escapeHtml(suite.description || '暂无说明')}</small>
      <small>用例 ${suite.case_ids.length} · 近 ${trend.run_count} 次执行 · ${latest}</small>
      <div class="suite-flow">${flow}${more}</div>
      <div class="suite-actions"><button class="primary" onclick="runSuite(${suite.id}, this)">开始执行并查看过程</button><button class="ghost danger" onclick="deleteSuite(${suite.id})">删除</button></div></div>`;
  }).join('') || '<div class="empty">暂无回归套件</div>';
}

async function loadRuns() {
  const page = await api('/runs?limit=30');
  state.runs = page.items;
  const suiteNames = Object.fromEntries(state.suites.map(suite => [suite.id, suite.name]));
  $('run-list').innerHTML = state.runs.map(run => {
    const scope = run.suite_id ? suiteNames[run.suite_id] || `套件 #${run.suite_id}` : `接口 #${run.interface_id}`;
    return `
    <tr><td><b>#${run.id}</b><small>${escapeHtml(scope)}</small></td><td>${badge(run.status)}</td><td>${run.passed}/${run.failed}</td><td>${elapsed(run)}</td>
    <td><button class="ghost" onclick="showResults(${run.id})">查看</button>${['queued', 'running'].includes(run.status) ? ` <button class="ghost" onclick="cancelRun(${run.id})">取消</button>` : ''}</td></tr>
  `; }).join('') || '<tr><td colspan="5">暂无任务</td></tr>';
  const active = state.runs.some(run => ['queued', 'running'].includes(run.status));
  if (active && !state.poll) state.poll = setInterval(loadRuns, 2500);
  if (!active && state.poll) { clearInterval(state.poll); state.poll = null; }
}

function renderResults(run, results) {
  $('result-title').textContent = `任务 #${run.id} · ${statusLabels[run.status] || run.status} · ${results.length} 条结果`;
  $('result-list').className = 'result-list';
  $('result-list').innerHTML = results.map((result, index) => `
    <div class="result ${result.status}"><header><b>第 ${index + 1} 步 · ${escapeHtml(result.case_name)}</b>${badge(result.status)}</header>
    <pre>HTTP ${result.status_code ?? '-'} · ${result.duration_ms ?? '-'}ms · 第${result.attempt}次执行\n${escapeHtml(result.assertion_message || result.ai_analysis || '全部断言通过')}</pre>
    <details><summary>展开本步骤的请求与响应</summary><pre>请求：${escapeHtml(JSON.stringify(result.request_data, null, 2))}\n响应：${escapeHtml(JSON.stringify(result.response_data, null, 2))}</pre></details></div>
  `).join('') || '<div class="empty">任务刚刚开始，正在等待第一步结果…</div>';
}

function renderRunFocus(run, results) {
  const suite = state.activeRun.suite || state.suites.find(item => item.id === run.suite_id);
  const caseIds = state.activeRun.caseIds?.length
    ? state.activeRun.caseIds
    : (suite?.case_ids || results.map(item => item.case_id));
  const caseMap = Object.fromEntries(state.caseOptions.map(item => [item.id, item]));
  const resultMap = new Map(results.map(result => [result.case_id, result]));
  const terminal = terminalStatuses.has(run.status);
  const firstPending = caseIds.findIndex(caseId => !resultMap.has(caseId));
  const total = Math.max(caseIds.length, run.total || 0, results.length);
  const completed = terminal ? total : results.length;
  const percentage = total ? Math.min(100, Math.round(completed / total * 100)) : 0;
  const skipped = Math.max(0, total - results.length);

  $('run-focus').hidden = false;
  $('run-focus-title').textContent = `${suite?.name || state.activeRun.label || '接口回归'} · 任务 #${run.id}`;
  $('run-focus-status').className = `status ${run.status}`;
  $('run-focus-status').textContent = statusLabels[run.status] || run.status;
  $('run-progress-count').textContent = terminal
    ? `执行完成：通过 ${run.passed}，失败 ${run.failed}`
    : `正在执行：已完成 ${results.length}/${total || '?'} 步`;
  $('run-progress-detail').textContent = run.status === 'passed'
    ? `整条业务链通过，共 ${results.length} 步`
    : run.status === 'failed'
      ? `发现 ${run.failed} 个失败${skipped ? `，后续 ${skipped} 步未执行` : ''}`
      : run.status === 'running' ? '平台正在按依赖顺序调用接口' : `当前状态：${statusLabels[run.status] || run.status}`;
  $('run-progress-bar').style.width = `${percentage}%`;

  $('run-steps').innerHTML = caseIds.map((caseId, index) => {
    const testCase = caseMap[caseId];
    const result = resultMap.get(caseId);
    let stepStatus = result?.status || 'queued';
    if (!result && terminal) stepStatus = 'skipped';
    else if (!result && run.status === 'running' && index === firstPending) stepStatus = 'running';
    const interfaceName = state.interfaceOptions.find(item => item.id === testCase?.interface_id)?.name || '';
    const detail = result
      ? (result.status === 'passed' ? `HTTP ${result.status_code} · ${result.duration_ms}ms` : result.assertion_message || '执行失败')
      : (stepStatus === 'running' ? '正在请求接口…' : stepStatus === 'skipped' ? '因前序失败未执行' : '等待前置步骤');
    return `<div class="run-step ${stepStatus}"><span class="step-index">${result?.status === 'passed' ? '✓' : result?.status === 'failed' ? '!' : index + 1}</span><div><b>${escapeHtml(testCase?.case_name || `用例 #${caseId}`)}</b><small>${escapeHtml(interfaceName)}</small><small>${escapeHtml(detail)}</small></div></div>`;
  }).join('') || '<div class="empty">该任务没有可显示的步骤</div>';
}

async function refreshActiveRun() {
  if (!state.activeRun) return;
  try {
    const [run, page] = await Promise.all([
      api(`/runs/${state.activeRun.id}`),
      api(`/runs/${state.activeRun.id}/results?limit=500`),
    ]);
    renderRunFocus(run, page.items);
    renderResults(run, page.items);
    await loadRuns();
    if (terminalStatuses.has(run.status)) {
      clearTimeout(state.watchTimer); state.watchTimer = null;
      message(run.status === 'passed' ? `任务 #${run.id}：整条回归链路通过` : `任务 #${run.id}：执行${statusLabels[run.status] || run.status}`, run.status === 'passed' ? 'ok' : 'error');
      await Promise.all([loadSystemInfo(), loadSuites()]);
    } else {
      state.watchTimer = setTimeout(refreshActiveRun, 800);
    }
  } catch (error) {
    clearTimeout(state.watchTimer); state.watchTimer = null;
    message(error.message, 'error');
  }
}

async function watchRun(runId, options = {}) {
  clearTimeout(state.watchTimer);
  state.watchTimer = null;
  state.activeRun = { id: runId, suite: options.suite || null, caseIds: options.caseIds || [], label: options.label || '' };
  activateTab('overview');
  $('run-focus').hidden = false;
  $('run-focus-title').textContent = `任务 #${runId} · 正在读取执行过程`;
  $('run-steps').innerHTML = '<div class="empty">正在读取业务步骤…</div>';
  await refreshActiveRun();
  if (options.scroll !== false) $('run-focus').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

async function showResults(runId) {
  const run = state.runs.find(item => item.id === runId);
  const suite = run?.suite_id ? state.suites.find(item => item.id === run.suite_id) : null;
  await watchRun(runId, { suite, scroll: true });
}

async function cancelRun(id) {
  try { await api(`/runs/${id}/cancel`, { method: 'POST' }); message(`任务 #${id} 已请求取消`); await loadRuns(); }
  catch (error) { message(error.message, 'error'); }
}

async function runSuite(id, button) {
  const originalText = button?.textContent;
  try {
    if (button) { button.disabled = true; button.textContent = '正在启动…'; }
    const environmentId = $('run-environment').value;
    const suite = state.suites.find(item => item.id === id);
    const run = await api(`/suites/${id}/runs/async`, {
      method: 'POST', body: JSON.stringify({ environment_id: environmentId ? Number(environmentId) : null, variables: {} }),
    });
    message(`任务 #${run.run_id} 已开始，正在展示执行过程`);
    await watchRun(run.run_id, { suite, caseIds: suite?.case_ids || [] });
  } catch (error) { message(error.message, 'error'); }
  finally { if (button) { button.disabled = false; button.textContent = originalText; } }
}

async function deleteSuite(id) {
  if (!window.confirm(`确认删除回归套件 #${id}？`)) return;
  try {
    await api(`/suites/${id}`, { method: 'DELETE' });
    message(`回归套件 #${id} 已删除`);
    await Promise.all([loadSuites(), loadSystemInfo()]);
  } catch (error) { message(error.message, 'error'); }
}

Object.assign(window, { showResults, cancelRun, runSuite, deleteSuite });

async function refreshAll() {
  try {
    await Promise.all([loadInterfaceOptions(), loadCaseOptions()]);
    await Promise.all([loadSystemInfo(), loadEnvironments(), loadInterfaces(), loadCases(), loadRuns(), loadSuites()]);
  } catch (error) { message(error.message, 'error'); }
}

document.querySelectorAll('.tabs button').forEach(button => {
  button.onclick = () => activateTab(button.dataset.tab);
});

$('api-key').value = apiKey();
$('save-key').onclick = () => { localStorage.setItem('platformApiKey', $('api-key').value.trim()); message('API Key 已保存在当前浏览器'); refreshAll(); };
$('refresh-runs').onclick = loadRuns;
$('refresh-suites').onclick = loadSuites;
$('run-scope').onchange = event => {
  const suiteMode = event.target.value === 'suite';
  $('run-suite-field').hidden = !suiteMode;
  $('run-interface-field').hidden = suiteMode;
};

$('interface-filter-form').onsubmit = event => { event.preventDefault(); state.interfacePage.page = 1; loadInterfaces().catch(error => message(error.message, 'error')); };
$('interface-page-size').onchange = () => { state.interfacePage.page = 1; loadInterfaces().catch(error => message(error.message, 'error')); };
$('interface-page').onchange = event => { state.interfacePage.page = Number(event.target.value); loadInterfaces().catch(error => message(error.message, 'error')); };
$('interface-prev').onclick = () => { if (state.interfacePage.page > 1) { state.interfacePage.page -= 1; loadInterfaces(); } };
$('interface-next').onclick = () => { if (state.interfacePage.page < state.interfacePage.pages) { state.interfacePage.page += 1; loadInterfaces(); } };
$('case-filter-form').onsubmit = event => { event.preventDefault(); state.casePage.page = 1; loadCases().catch(error => message(error.message, 'error')); };
$('case-page-size').onchange = () => { state.casePage.page = 1; loadCases().catch(error => message(error.message, 'error')); };
$('case-page').onchange = event => { state.casePage.page = Number(event.target.value); loadCases().catch(error => message(error.message, 'error')); };
$('case-prev').onclick = () => { if (state.casePage.page > 1) { state.casePage.page -= 1; loadCases(); } };
$('case-next').onclick = () => { if (state.casePage.page < state.casePage.pages) { state.casePage.page += 1; loadCases(); } };

$('environment-form').onsubmit = async event => {
  event.preventDefault();
  try {
    await api('/environments', { method: 'POST', body: JSON.stringify({ name: $('env-name').value, base_url: $('env-base-url').value, variables: parseJSON('env-variables', {}), secrets: parseJSON('env-secrets', {}), headers: parseJSON('env-headers', {}) }) });
    message('环境已创建并写入数据库');
    event.target.reset(); $('env-variables').value = '{}'; $('env-secrets').value = '{}'; $('env-headers').value = '{}';
    await Promise.all([loadEnvironments(), loadSystemInfo()]);
  } catch (error) { message(error.message, 'error'); }
};

$('interface-form').onsubmit = async event => {
  event.preventDefault();
  try {
    await api('/interfaces', { method: 'POST', body: JSON.stringify({ name: $('interface-name').value, url: $('interface-url').value, method: $('interface-method').value, headers: parseJSON('interface-headers', {}), body: parseJSON('interface-body', {}) }) });
    message('接口已创建并写入数据库');
    event.target.reset(); $('interface-headers').value = '{}'; $('interface-body').value = '{}'; state.interfacePage.page = 1;
    await loadInterfaceOptions(); await Promise.all([loadInterfaces(), loadSystemInfo()]);
  } catch (error) { message(error.message, 'error'); }
};

$('case-form').onsubmit = async event => {
  event.preventDefault();
  try {
    const dependencies = $('case-dependencies').value.split(',').map(value => value.trim()).filter(Boolean).map(Number);
    await api('/cases', { method: 'POST', body: JSON.stringify({ interface_id: Number($('case-interface').value), case_name: $('case-name').value, data: parseJSON('case-data', {}), expected_status_code: Number($('case-status').value), assertions: parseJSON('case-assertions', []), extractors: parseJSON('case-extractors', []), dependencies, retry_count: Number($('case-retry').value) }) });
    message('测试用例已创建并写入数据库'); state.casePage.page = 1;
    await Promise.all([loadCases(), loadCaseOptions(), loadSystemInfo()]);
  } catch (error) { message(error.message, 'error'); }
};

$('ai-case-form').onsubmit = async event => {
  event.preventDefault(); const button = event.submitter;
  try {
    button.disabled = true; button.textContent = 'AI正在生成，请稍候…';
    const expected = $('ai-status').value.trim();
    const generated = await api(`/ai/interfaces/${Number($('ai-interface').value)}/cases`, { method: 'POST', body: JSON.stringify({ input_data: parseJSON('ai-input', {}), expected_status_code: expected ? Number(expected) : null }) });
    message(`生成完成：${generated.length} 条候选用例已保存`); state.casePage.page = 1; $('case-filter-interface').value = $('ai-interface').value;
    await Promise.all([loadCases(), loadCaseOptions(), loadSystemInfo()]);
  } catch (error) { message(error.message, 'error'); }
  finally { button.disabled = false; button.textContent = '生成并保存测试用例'; }
};

$('run-form').onsubmit = async event => {
  event.preventDefault();
  try {
    const body = { environment_id: $('run-environment').value ? Number($('run-environment').value) : null, variables: parseJSON('run-variables', {}), analyze_by_ai: $('run-ai').checked, fail_fast: $('run-fail-fast').checked };
    const suiteMode = $('run-scope').value === 'suite';
    if (!suiteMode) body.interface_id = Number($('run-interface').value);
    const path = suiteMode ? `/suites/${Number($('run-suite').value)}/runs/async` : '/runs/async';
    const run = await api(path, { method: 'POST', body: JSON.stringify(body) });
    const suite = suiteMode ? state.suites.find(item => item.id === Number($('run-suite').value)) : null;
    const caseIds = suiteMode ? (suite?.case_ids || []) : state.caseOptions.filter(item => item.interface_id === body.interface_id).map(item => item.id);
    message(`任务 #${run.run_id} 已开始，正在展示执行过程`);
    await watchRun(run.run_id, { suite, caseIds, label: suiteMode ? '' : `接口 #${body.interface_id}` });
  } catch (error) { message(error.message, 'error'); }
};

$('suite-form').onsubmit = async event => {
  event.preventDefault();
  try {
    const caseIds = [...$('suite-cases').selectedOptions].map(option => Number(option.value));
    await api('/suites', { method: 'POST', body: JSON.stringify({ name: $('suite-name').value, description: $('suite-description').value, case_ids: caseIds, fail_fast: $('suite-fail-fast').checked, analyze_by_ai: $('suite-ai').checked }) });
    message('回归套件已创建'); event.target.reset(); await Promise.all([loadSuites(), loadSystemInfo()]);
  } catch (error) { message(error.message, 'error'); }
};

$('openapi-form').onsubmit = async event => {
  event.preventDefault();
  try {
    const result = await api('/openapi/import', { method: 'POST', body: JSON.stringify({ document: parseJSON('openapi-document', {}), overwrite_existing: $('openapi-overwrite').value === 'true', generate_schema_cases: $('openapi-cases').value === 'true' }) });
    message(`导入完成：新增接口 ${result.created_interfaces}，生成用例 ${result.generated_cases}`); await refreshAll();
  } catch (error) { message(error.message, 'error'); }
};

health();
refreshAll();
