const state = {
  environments: [], interfaceOptions: [], interfaces: [], cases: [], caseOptions: [], suites: [], runs: [],
  interfacePage: { page: 1, pages: 1 }, casePage: { page: 1, pages: 1 }, poll: null,
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

const badge = status => `<span class="status ${escapeHtml(status)}">${escapeHtml(status)}</span>`;
const elapsed = run => (!run.started_at || !run.finished_at)
  ? '-'
  : `${Math.max(0, new Date(run.finished_at) - new Date(run.started_at))}ms`;

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
    return `<div class="stack-item"><header><b>#${suite.id} ${escapeHtml(suite.name)}</b><span>${suite.enabled ? '启用' : '停用'}</span></header>
      <small>${escapeHtml(suite.description || '暂无说明')}</small>
      <small>用例 ${suite.case_ids.length} · 近 ${trend.run_count} 次执行 · ${latest}</small>
      <p><button class="primary" onclick="runSuite(${suite.id})">立即回归</button> <button class="ghost danger" onclick="deleteSuite(${suite.id})">删除</button></p></div>`;
  }).join('') || '<div class="empty">暂无回归套件</div>';
}

async function loadRuns() {
  const page = await api('/runs?limit=30');
  state.runs = page.items;
  $('run-list').innerHTML = state.runs.map(run => `
    <tr><td>#${run.id}</td><td>${badge(run.status)}</td><td>${run.passed}/${run.failed}</td><td>${elapsed(run)}</td>
    <td><button class="ghost" onclick="showResults(${run.id})">查看</button>${['queued', 'running'].includes(run.status) ? ` <button class="ghost" onclick="cancelRun(${run.id})">取消</button>` : ''}</td></tr>
  `).join('') || '<tr><td colspan="5">暂无任务</td></tr>';
  const active = state.runs.some(run => ['queued', 'running'].includes(run.status));
  if (active && !state.poll) state.poll = setInterval(loadRuns, 2500);
  if (!active && state.poll) { clearInterval(state.poll); state.poll = null; }
}

async function showResults(runId) {
  try {
    const page = await api(`/runs/${runId}/results?limit=500`);
    $('result-title').textContent = `任务 #${runId} · ${page.total} 条结果`;
    $('result-list').className = 'result-list';
    $('result-list').innerHTML = page.items.map(result => `
      <div class="result ${result.status}"><header><b>#${result.case_id} ${escapeHtml(result.case_name)}</b>${badge(result.status)}</header>
      <pre>HTTP ${result.status_code ?? '-'} · ${result.duration_ms ?? '-'}ms · 第${result.attempt}次执行\n${escapeHtml(result.assertion_message || result.ai_analysis || '断言全部通过')}</pre>
      <details><summary>请求与响应</summary><pre>请求：${escapeHtml(JSON.stringify(result.request_data, null, 2))}\n响应：${escapeHtml(JSON.stringify(result.response_data, null, 2))}</pre></details></div>
    `).join('') || '<div class="empty">暂无结果，任务可能仍在执行</div>';
  } catch (error) { message(error.message, 'error'); }
}

async function cancelRun(id) {
  try { await api(`/runs/${id}/cancel`, { method: 'POST' }); message(`任务 #${id} 已请求取消`); await loadRuns(); }
  catch (error) { message(error.message, 'error'); }
}

async function runSuite(id) {
  try {
    const environmentId = $('run-environment').value;
    const run = await api(`/suites/${id}/runs/async`, {
      method: 'POST', body: JSON.stringify({ environment_id: environmentId ? Number(environmentId) : null, variables: {} }),
    });
    message(`回归套件任务 #${run.run_id} 已提交`);
    await Promise.all([loadRuns(), loadSystemInfo(), loadSuites()]);
  } catch (error) { message(error.message, 'error'); }
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
  button.onclick = () => {
    document.querySelectorAll('.tabs button').forEach(item => item.classList.toggle('active', item === button));
    document.querySelectorAll('.tab-panel').forEach(panel => panel.classList.toggle('active', panel.id === `tab-${button.dataset.tab}`));
  };
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
    message(`异步任务 #${run.run_id} 已提交`); await Promise.all([loadRuns(), loadSystemInfo()]);
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
