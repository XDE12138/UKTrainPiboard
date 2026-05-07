/* PiBoard 控制台 — 原生 JS，低开销运行在 Pi Zero 2 W 上。 */
/* global DEFAULT_APP_ID */

let ws = null;
let reconnectTimer = null;
let settingsTimer = null;
let statusTimer = null;

let state = {};
let sources = {};
let deviceStatus = {};
let activePage = 'content';
let wsConnected = false;
let autoWeatherLocationTried = false;

const openSources = new Set();
const dirtyForms = new Set();

const PAGE_CARDS = [
  { id: 'overview', title: '概览', source: 'mock', preset: 'overview',
    desc: '跨日程、天气、交通的综合摘要。' },
  { id: 'train', title: '列车', source: 'train',
    desc: '配置车站 CRS、目的地和实时数据来源。' },
  { id: 'weather', title: '天气', source: 'weather',
    desc: '配置城市、单位和天气 API。' },
  { id: 'calendar', title: '日程', source: 'calendar',
    desc: '配置 iCal 地址和未来事件范围。' },
  { id: 'custom', title: '自定义', source: 'custom',
    desc: '手工编辑标题、内容行、状态和底部文字。' },
];

const SOURCE_META = {
  mock:     { title: '演示 / 轮播', desc: '内置展示数据，无需 API。' },
  train:    { title: '列车数据', desc: '车站出发信息，可用 mock 或实时 API。' },
  weather:  { title: '天气数据', desc: '城市天气和预报。' },
  calendar: { title: '日程数据', desc: 'iCal / 日历事件。' },
  custom:   { title: '自定义文本', desc: '完全手动编辑的一页内容。' },
};

const FIELD_LABELS = {
  preset: '预设内容',
  cycle_presets: '低功耗轮播页面',
  refresh_interval_sec: '刷新 / 轮播间隔（秒）',
  station_crs: '出发站 CRS',
  destination_crs: '目的地 CRS（可选）',
  data_source: '数据来源',
  api_key: 'API Key',
  city: '城市',
  units: '单位',
  ical_url: 'iCal 地址',
  lookahead_days: '未来天数',
  header_left: '左上角',
  header_right: '右上角',
  title: '主标题',
  title_color: '标题颜色',
  subtitle: '副标题',
  rows: '内容行',
  footer: '底部来源',
  status_text: '状态文字',
  status_color: '状态颜色',
  ticker: '底部信息栏',
};

const OPTION_LABELS = {
  overview: '概览',
  train: '列车',
  weather: '天气',
  calendar: '日程',
  cycle: '低功耗轮播',
  auto: '当前位置',
  manual: '手动城市',
  mock: 'Mock',
  huxley2: 'Huxley2',
  transportapi: 'TransportAPI',
  metric: '摄氏 / 公制',
  imperial: '华氏 / 英制',
  amber: '琥珀色',
  green: '绿色',
  white: '白色',
  orange: '橙色',
  red: '红色',
};

// ---------------------------------------------------------------------------
// State helpers
// ---------------------------------------------------------------------------

function getActiveApp() {
  return state.current_app || DEFAULT_APP_ID || 'uk_station';
}

function getUkState() {
  return (state.apps || {}).uk_station || {};
}

function getActiveAppState() {
  return (state.apps || {})[getActiveApp()] || {};
}

function getLayout() {
  return getUkState().layout || 'single';
}

function getSlots() {
  return getUkState().slots || [];
}

function getAppSettings() {
  return getUkState().app_settings || {};
}

function getDeviceSettings() {
  return state.device_settings || {};
}

function formKey(scope, sid) {
  return `${scope}:${sid}`;
}

function sourceTitle(sid) {
  return SOURCE_META[sid]?.title || sources[sid]?.display_name || sid;
}

function layoutLabel(layout) {
  return { single: '单页', dual: '双栏', carousel: '轮播' }[layout] || layout;
}

function slotLabel(sid) {
  const map = { mock: '演示', train: '列车', weather: '天气', calendar: '日程', custom: '自定义' };
  return map[sid] || sid || '-';
}

function optionLabel(option) {
  if (typeof option === 'object') return option.label || option.value;
  return OPTION_LABELS[option] || option;
}

function optionValue(option) {
  return typeof option === 'object' ? option.value : option;
}

function fieldLabel(key, def) {
  return FIELD_LABELS[key] || def.label || key;
}

function hasDirtyForms(prefix = '') {
  return Array.from(dirtyForms).some(k => !prefix || k.startsWith(prefix));
}

function markDirtyFromElement(el) {
  const key = el?.dataset?.formKey;
  if (key) dirtyForms.add(key);
}

// ---------------------------------------------------------------------------
// API and notifications
// ---------------------------------------------------------------------------

async function apiRequest(url, options = {}) {
  const opts = {...options};
  opts.headers = {...(opts.headers || {})};
  if (opts.body && typeof opts.body !== 'string') {
    opts.headers['Content-Type'] = 'application/json';
    opts.body = JSON.stringify(opts.body);
  }
  const resp = await fetch(url, opts);
  const text = await resp.text();
  let data = {};
  if (text) {
    try { data = JSON.parse(text); }
    catch (_) { data = {message: text}; }
  }
  if (!resp.ok || data.error) {
    throw new Error(data.error || data.message || `请求失败：${resp.status}`);
  }
  return data;
}

let notifTimer = null;
function showNotif(message, type = '') {
  const el = document.getElementById('notif');
  if (!el) return;
  el.textContent = message;
  el.className = type;
  el.style.display = 'block';
  clearTimeout(notifTimer);
  notifTimer = setTimeout(() => { el.style.display = 'none'; }, 3000);
}

async function runButtonAction(button, loadingText, action) {
  const oldText = button?.textContent;
  if (button) {
    button.disabled = true;
    button.textContent = loadingText;
  }
  try {
    await action();
  } catch (err) {
    showNotif(err.message || '操作失败', 'error');
  } finally {
    if (button) {
      button.disabled = false;
      button.textContent = oldText;
    }
  }
}

// ---------------------------------------------------------------------------
// Navigation
// ---------------------------------------------------------------------------

function navigate(pageId) {
  activePage = pageId;
  document.querySelectorAll('.page').forEach(page => {
    page.classList.toggle('active', page.id === `page-${pageId}`);
  });
  document.querySelectorAll('.nav-item[data-page]').forEach(item => {
    item.classList.toggle('active', item.dataset.page === pageId);
  });
  if (pageId === 'status') loadDeviceStatus();
}

// ---------------------------------------------------------------------------
// Loading and websocket
// ---------------------------------------------------------------------------

async function bootstrap() {
  try {
    const [stateData, sourcesData, statusData] = await Promise.all([
      apiRequest('/api/state'),
      apiRequest('/api/sources'),
      apiRequest('/api/device-status'),
    ]);
    state = stateData;
    sources = sourcesData;
    deviceStatus = statusData;
    renderAll();
    ensureAutoWeatherLocation();
  } catch (err) {
    showNotif(err.message || '初始化失败', 'error');
  }
  connectWS();
  statusTimer = setInterval(loadDeviceStatus, 10000);
}

async function loadSources(render = true) {
  if (hasDirtyForms()) {
    showNotif('有未保存的修改，保存后再重新加载。', 'warn');
    return;
  }
  sources = await apiRequest('/api/sources');
  if (render) {
    renderCyclePanel();
    renderPageCards();
    renderSourceList();
    renderSlots();
  }
  ensureAutoWeatherLocation();
}

async function loadDeviceStatus() {
  try {
    deviceStatus = await apiRequest('/api/device-status');
    renderStatus();
  } catch (err) {
    showNotif(err.message || '设备状态读取失败', 'error');
  }
}

function connectWS() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  ws = new WebSocket(`${proto}://${location.host}/ws`);

  ws.onopen = () => {
    wsConnected = true;
    setBadge(true);
    clearTimeout(reconnectTimer);
  };
  ws.onclose = () => {
    wsConnected = false;
    setBadge(false);
    reconnectTimer = setTimeout(connectWS, 3000);
  };
  ws.onerror = () => ws.close();
  ws.onmessage = evt => {
    try {
      const msg = JSON.parse(evt.data);
      handleWSMessage(msg);
    } catch (_) {}
  };
}

function handleWSMessage(msg) {
  if (msg.type === 'state') {
    state = msg.data || {};
    applyStateToUI();
    return;
  }
  if (msg.type === 'current_app_changed') {
    state.current_app = msg.current_app;
    applyStateToUI();
    return;
  }
  if (msg.type === 'app_layout_changed') {
    const appSt = (state.apps || {})[msg.app_id];
    if (appSt) {
      appSt.layout = msg.layout;
      appSt.slots = msg.slots;
    }
    applyStateToUI();
    return;
  }
  if (msg.type === 'app_settings_changed') {
    const appSt = (state.apps || {})[msg.app_id];
    if (appSt) appSt.app_settings = {...(appSt.app_settings || {}), ...msg.app_settings};
    applyStateToUI();
    return;
  }
  if (msg.type === 'device_settings_changed') {
    state.device_settings = {...(state.device_settings || {}), ...msg.device_settings};
    applyStateToUI();
    return;
  }
  if (msg.type === 'source_config_changed') {
    if (!hasDirtyForms()) loadSources(true).catch(() => {});
    else showNotif('后台数据已更新，当前编辑内容未被打断。', 'warn');
  }
}

function setBadge(connected) {
  const badge = document.getElementById('ws-badge');
  const label = document.getElementById('ws-label');
  badge?.classList.toggle('ok', connected);
  if (label) label.textContent = connected ? '已连接' : '已断开';
  renderStatus();
}

// ---------------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------------

function renderAll() {
  renderDisplaySummary();
  renderCyclePanel();
  renderPageCards();
  renderSourceList();
  renderSettings();
  renderSlots();
  renderStatus();
  updateAppSwitcher();
}

function applyStateToUI() {
  renderDisplaySummary();
  renderSettings();
  renderSlots();
  renderStatus();
  updateAppSwitcher();
}

function renderDisplaySummary() {
  const el = document.getElementById('display-summary');
  if (!el) return;
  const mockCfg = sources.mock?.config || {};
  const appSettings = getAppSettings();
  const device = getDeviceSettings();
  const slotText = getSlots().map(slotLabel).join(' / ') || '-';
  const power = appSettings.animations_enabled === false ? '低功耗静态' : '动画开启';

  el.innerHTML = [
    metricHTML('当前 App', getActiveApp() === 'uk_station' ? '展示看板' : getActiveApp()),
    metricHTML('显示布局', `${layoutLabel(getLayout())} · ${slotText}`),
    metricHTML('轮播预设', `${optionLabel(mockCfg.preset || 'overview')} · ${mockCfg.refresh_interval_sec || 60}s`),
    metricHTML('设备', `${device.orientation === 'portrait' ? '竖屏' : '横屏'} · ${power}`),
  ].join('');
}

function metricHTML(label, value) {
  return `<div class="metric"><div class="metric-label">${esc(label)}</div><div class="metric-value">${esc(value)}</div></div>`;
}

function renderCyclePanel() {
  const el = document.getElementById('cycle-panel');
  if (!el || dirtyForms.has(formKey('cycle', 'mock'))) return;
  const info = sources.mock || {};
  const schema = info.schema || {};
  const cfg = info.config || {};
  el.innerHTML = `
    <div class="panel">
      <div class="card-head">
        <div>
          <div class="card-title">低功耗轮播</div>
          <div class="card-subtitle">关闭连续动画，只按间隔切换静态页面。</div>
        </div>
        <div class="btn-row">
          <button class="btn btn-outline btn-sm" data-action="save-cycle">保存设置</button>
          <button class="btn btn-primary btn-sm" data-action="enable-cycle">启用轮播</button>
        </div>
      </div>
      <div class="card-body">
        <div class="field-row">
          ${renderField('mock', 'refresh_interval_sec', schema.refresh_interval_sec || {type:'number', default:60}, cfg, 'cycle')}
          ${renderField('mock', 'cycle_presets', schema.cycle_presets || {type:'multi_select', options:['overview','train','weather','calendar']}, cfg, 'cycle')}
        </div>
      </div>
    </div>`;
}

function renderPageCards() {
  const el = document.getElementById('page-cards');
  if (!el || hasDirtyForms('page:')) return;
  el.innerHTML = PAGE_CARDS.map(card => renderPageCard(card)).join('');
}

function renderPageCard(card) {
  const info = sources[card.source] || {};
  const cfg = info.config || {};
  const schema = info.schema || {};
  const current = isCurrentPage(card);
  const form = renderPageForm(card, schema, cfg);
  return `
    <article class="page-card" data-card="${card.id}">
      <div class="card-head">
        <div>
          <div class="card-title">${esc(card.title)}${current ? ' · 当前显示' : ''}</div>
          <div class="card-subtitle">${esc(card.desc)}</div>
        </div>
        <div class="btn-row">
          <button class="btn btn-outline btn-sm" data-action="set-current-page" data-page-card="${card.id}">设为当前页面</button>
          <button class="btn btn-primary btn-sm" data-action="save-page" data-page-card="${card.id}">保存并刷新</button>
        </div>
      </div>
      <div class="card-body">${form}</div>
    </article>`;
}

function renderPageForm(card, schema, cfg) {
  if (card.id === 'overview') {
    return `
      <p class="page-desc" style="margin-bottom:12px;">概览页由内置 mock 摘要生成。需要单独显示概览时会自动把 Mock 预设切到“概览”。</p>
      ${renderField('mock', 'refresh_interval_sec', schema.refresh_interval_sec || {type:'number', default:60}, cfg, 'page')}`;
  }
  if (card.source === 'weather') {
    return renderWeatherForm(card.source, schema, cfg, 'page');
  }
  const fields = Object.keys(schema);
  if (!fields.length) {
    return '<p class="page-desc">这个页面没有可编辑配置。</p>';
  }
  return fields.map(key => renderField(card.source, key, schema[key], cfg, 'page')).join('');
}

function renderSourceList() {
  const el = document.getElementById('source-list');
  if (!el || hasDirtyForms('source:')) return;
  el.innerHTML = Object.entries(sources).map(([sid, info]) => {
    const meta = SOURCE_META[sid] || {title: info.display_name || sid, desc: ''};
    const open = openSources.has(sid) ? ' open' : '';
    return `
      <article class="source-card${open}" data-source="${sid}">
        <div class="card-head source-toggle" data-action="toggle-source" data-source="${sid}">
          <div>
            <div class="card-title">${esc(meta.title)}</div>
            <div class="card-subtitle">${esc(meta.desc)}</div>
          </div>
          <span class="chevron">›</span>
        </div>
        <div class="source-body">
          ${renderSourceForm(sid, info)}
          <div class="btn-row">
            <button class="btn btn-primary btn-sm" data-action="save-source" data-source="${sid}">保存并刷新</button>
            <button class="btn btn-outline btn-sm" data-action="refresh-source" data-source="${sid}">只刷新</button>
          </div>
        </div>
      </article>`;
  }).join('');
}

function renderSourceForm(sid, info) {
  const schema = info.schema || {};
  const cfg = info.config || {};
  if (sid === 'weather') {
    return renderWeatherForm(sid, schema, cfg, 'source');
  }
  const fields = Object.keys(schema);
  if (!fields.length) return '<p class="page-desc">这个数据源没有可编辑配置。</p>';
  return fields.map(key => renderField(sid, key, schema[key], cfg, 'source')).join('');
}

function renderWeatherForm(sid, schema, cfg, scope) {
  const mode = cfg.location_mode || 'auto';
  return `
    <div class="panel" style="background:var(--panel-2);border-color:var(--border);margin-bottom:12px;">
      <div class="card-body">
        <div class="field-row">
          ${renderField(sid, 'location_mode', schema.location_mode || {type:'select', options:['auto','manual'], default:'auto'}, cfg, scope)}
          ${renderField(sid, 'city', schema.city || {type:'string', default:''}, cfg, scope)}
        </div>
        <div class="field-row">
          ${renderField(sid, 'latitude', schema.latitude || {type:'string', default:''}, cfg, scope)}
          ${renderField(sid, 'longitude', schema.longitude || {type:'string', default:''}, cfg, scope)}
        </div>
        <div class="btn-row">
          <button class="btn btn-outline btn-sm" data-action="use-current-location" data-scope="${scope}" data-source="${sid}">⌖ 使用当前位置</button>
          <span class="page-desc">${mode === 'auto' ? '自动模式会优先使用经纬度；未授权时显示“当前位置”。' : '手动模式会使用城市名。'}</span>
        </div>
      </div>
    </div>
    ${renderField(sid, 'api_key', schema.api_key || {type:'string', secret:true, default:''}, cfg, scope)}
    ${renderField(sid, 'units', schema.units || {type:'select', options:['metric','imperial'], default:'metric'}, cfg, scope)}
  `;
}

async function ensureAutoWeatherLocation() {
  const cfg = sources.weather?.config || {};
  if (autoWeatherLocationTried) return;
  if ((cfg.location_mode || 'auto') !== 'auto') return;
  if (cfg.latitude && cfg.longitude) return;
  if (!navigator.geolocation) return;

  autoWeatherLocationTried = true;
  try {
    const pos = await getBrowserPosition();
    const config = {
      ...cfg,
      location_mode: 'auto',
      latitude: Number(pos.coords.latitude).toFixed(5),
      longitude: Number(pos.coords.longitude).toFixed(5),
      city: '当前位置',
    };
    await saveSource('weather', config, null, '');
    showNotif('已自动使用当前位置天气。', 'success');
    renderPageCards();
    renderSourceList();
  } catch (_) {
    showNotif('浏览器未提供定位；可手动填城市或点击“使用当前位置”。', 'warn');
  }
}

function renderSettings() {
  const activeId = document.activeElement?.id;
  const appSettings = getAppSettings();
  const device = getDeviceSettings();
  setInputValue('brightness', device.brightness ?? 1, activeId);
  setInputValue('color_theme', appSettings.color_theme || 'amber', activeId);
  setInputValue('animations_enabled', String(appSettings.animations_enabled !== false), activeId);
  setInputValue('orientation', device.orientation || 'portrait', activeId);
  document.querySelectorAll('.layout-card').forEach(card => {
    card.classList.toggle('active', card.dataset.layout === getLayout());
  });
}

function setInputValue(id, value, activeId) {
  const el = document.getElementById(id);
  if (el && activeId !== id) el.value = value;
}

function renderSlots() {
  const el = document.getElementById('slots-container');
  if (!el) return;
  const layout = getSelectedLayout();
  const count = layout === 'dual' ? 2 : (layout === 'carousel' ? 3 : 1);
  const sourceIds = Object.keys(sources);
  el.innerHTML = Array.from({length: count}, (_, i) => {
    const current = getSlots()[i] || sourceIds[0] || 'mock';
    const options = sourceIds.map(sid =>
      `<option value="${esc(sid)}" ${sid === current ? 'selected' : ''}>${esc(slotLabel(sid))}</option>`
    ).join('');
    const label = layout === 'dual' ? (i === 0 ? '左侧 / 上方' : '右侧 / 下方')
      : (layout === 'carousel' ? `轮播槽 ${i + 1}` : '显示页面');
    return `<div class="slot-box"><div class="field"><label>${label}</label><select id="slot_${i}">${options}</select></div></div>`;
  }).join('');
}

function renderStatus() {
  const el = document.getElementById('status-grid');
  if (!el) return;
  const appSettings = getAppSettings();
  const device = getDeviceSettings();
  const temp = deviceStatus.temp_c == null ? '本地不可用' : `${deviceStatus.temp_c}°C`;
  const throttled = deviceStatus.throttled == null ? '本地不可用' : deviceStatus.throttled;
  const updated = deviceStatus.time ? new Date(deviceStatus.time * 1000).toLocaleTimeString('zh-CN', {hour12:false}) : '-';
  const power = appSettings.animations_enabled === false ? '低功耗' : '动画开启';

  el.innerHTML = [
    statusHTML('WebSocket', wsConnected ? '已连接' : '已断开', wsConnected ? 'status-good' : 'status-bad'),
    statusHTML('主机', deviceStatus.hostname || '-', ''),
    statusHTML('设备类型', deviceStatus.is_pi ? 'Raspberry Pi' : 'Mac / 本地预览', ''),
    statusHTML('当前 App', getActiveApp(), ''),
    statusHTML('布局 / 槽位', `${layoutLabel(getLayout())} · ${(getSlots().map(slotLabel).join(' / ') || '-')}`, ''),
    statusHTML('功耗模式', power, appSettings.animations_enabled === false ? 'status-good' : 'status-warn'),
    statusHTML('方向', device.orientation === 'portrait' ? '竖屏' : '横屏', ''),
    statusHTML('亮度', `${Math.round((device.brightness ?? 1) * 100)}%`, ''),
    statusHTML('温度', temp, deviceStatus.temp_c && deviceStatus.temp_c > 70 ? 'status-warn' : ''),
    statusHTML('Throttled', throttled, throttled === '0x0' ? 'status-good' : (throttled === '本地不可用' ? '' : 'status-warn')),
    statusHTML('状态更新时间', updated, ''),
  ].join('');
}

function statusHTML(label, value, klass) {
  return `<div class="status-card"><div class="status-label">${esc(label)}</div><div class="status-value ${klass || ''}">${esc(value)}</div></div>`;
}

function updateAppSwitcher() {
  const current = getActiveApp();
  document.querySelectorAll('.app-switch-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.app === current);
  });
}

// ---------------------------------------------------------------------------
// Field rendering and collection
// ---------------------------------------------------------------------------

function renderField(sid, key, def, cfg, scope) {
  const keyName = formKey(scope, sid);
  const id = fieldId(scope, sid, key);
  const value = cfg[key] !== undefined ? cfg[key] : (def.default ?? '');
  const label = fieldLabel(key, def);

  if (def.type === 'rows') {
    return `
      <div class="field">
        <label>${esc(label)}</label>
        ${renderRowsEditor(scope, sid, value || [])}
        <div class="btn-row" style="margin-top:8px;">
          <button class="btn btn-ghost btn-sm" data-action="add-row" data-scope="${scope}" data-source="${sid}">＋ 添加一行</button>
        </div>
      </div>`;
  }

  if (def.type === 'multi_select') {
    const current = Array.isArray(value) ? value : (def.default || []);
    const boxes = (def.options || []).map(option => {
      const optValue = optionValue(option);
      return `<label class="check-item">
        <input type="checkbox" name="${id}" value="${esc(optValue)}" data-form-key="${keyName}" ${current.includes(optValue) ? 'checked' : ''}>
        <span>${esc(optionLabel(option))}</span>
      </label>`;
    }).join('');
    return `<div class="field"><label>${esc(label)}</label><div class="check-grid">${boxes}</div></div>`;
  }

  if (def.type === 'select') {
    const options = (def.options || []).map(option => {
      const optValue = optionValue(option);
      return `<option value="${esc(optValue)}" ${String(value) === String(optValue) ? 'selected' : ''}>${esc(optionLabel(option))}</option>`;
    }).join('');
    return `<div class="field"><label for="${id}">${esc(label)}</label><select id="${id}" data-form-key="${keyName}">${options}</select></div>`;
  }

  const type = def.secret ? 'password' : (def.type === 'number' ? 'number' : 'text');
  return `<div class="field"><label for="${id}">${esc(label)}</label><input type="${type}" id="${id}" data-form-key="${keyName}" value="${esc(String(value))}" placeholder="${esc(String(def.default ?? ''))}"></div>`;
}

function renderRowsEditor(scope, sid, rows) {
  const items = (rows || []).map(row => renderRowItem(row)).join('');
  return `<div class="rows-editor" data-scope="${scope}" data-source="${sid}">${items}</div>`;
}

function renderRowItem(row) {
  const left = typeof row === 'string' ? row : (row.left || '');
  const right = typeof row === 'string' ? '' : (row.right || '');
  return `
    <div class="row-editor-item">
      <input type="text" class="row-left" value="${esc(left)}" placeholder="左侧文字">
      <input type="text" class="row-right" value="${esc(right)}" placeholder="右侧">
      <button class="btn btn-ghost del" data-action="delete-row">×</button>
    </div>`;
}

function addRow(scope, sid) {
  const editor = document.querySelector(`.rows-editor[data-scope="${scope}"][data-source="${sid}"]`);
  if (!editor) return;
  editor.insertAdjacentHTML('beforeend', renderRowItem({left: '', right: ''}));
  dirtyForms.add(formKey(scope, sid));
}

function fieldId(scope, sid, key) {
  return `field_${scope}_${sid}_${key}`;
}

function collectSourceConfig(sid, scope) {
  const schema = sources[sid]?.schema || {};
  const config = {};
  Object.entries(schema).forEach(([key, def]) => {
    const id = fieldId(scope, sid, key);
    if (def.type === 'rows') {
      const editor = document.querySelector(`.rows-editor[data-scope="${scope}"][data-source="${sid}"]`);
      if (editor) config[key] = collectRows(editor);
      return;
    }
    if (def.type === 'multi_select') {
      const boxes = Array.from(document.querySelectorAll(`input[name="${id}"]:checked`));
      if (boxes.length || document.querySelector(`input[name="${id}"]`)) {
        config[key] = boxes.map(box => box.value);
      }
      return;
    }
    const el = document.getElementById(id);
    if (!el) return;
    config[key] = def.type === 'number' ? Number(el.value) : el.value;
  });
  return config;
}

function collectRows(editor) {
  return Array.from(editor.querySelectorAll('.row-editor-item')).map(item => ({
    left: item.querySelector('.row-left')?.value || '',
    right: item.querySelector('.row-right')?.value || '',
  }));
}

// ---------------------------------------------------------------------------
// Actions
// ---------------------------------------------------------------------------

function isCurrentPage(card) {
  const slots = getSlots();
  if (card.id === 'overview') {
    return getLayout() === 'single' && slots[0] === 'mock' && (sources.mock?.config?.preset || 'overview') === 'overview';
  }
  return getLayout() === 'single' && slots[0] === card.source;
}

async function savePage(cardId, silent = false) {
  const card = PAGE_CARDS.find(item => item.id === cardId);
  if (!card) return;
  const config = collectSourceConfig(card.source, 'page');
  if (card.id === 'overview') config.preset = 'overview';
  await saveSource(card.source, config, formKey('page', card.source), silent ? '' : `${card.title}已保存并刷新`);
}

async function setCurrentPage(cardId) {
  const card = PAGE_CARDS.find(item => item.id === cardId);
  if (!card) return;
  await savePage(cardId, true);
  await ensureStationApp();
  await apiRequest('/api/app/uk_station/layout', {
    method: 'POST',
    body: {layout: 'single', slots: [card.id === 'overview' ? 'mock' : card.source]},
  });
  updateLocalLayout('single', [card.id === 'overview' ? 'mock' : card.source]);
  renderAll();
  showNotif(`已切换到${card.title}`, 'success');
}

async function saveCycle(enable) {
  const config = collectSourceConfig('mock', 'cycle');
  if (enable) config.preset = 'cycle';
  await saveSource('mock', config, formKey('cycle', 'mock'), enable ? '' : '轮播设置已保存');
  if (enable) {
    await ensureStationApp();
    await apiRequest('/api/app/uk_station/layout', {
      method: 'POST',
      body: {layout: 'single', slots: ['mock']},
    });
    updateLocalLayout('single', ['mock']);
    renderAll();
    showNotif('低功耗轮播已启用', 'success');
  }
}

async function saveSourceFromForm(sid, scope) {
  const config = collectSourceConfig(sid, scope);
  await saveSource(sid, config, formKey(scope, sid), `${sourceTitle(sid)}已保存并刷新`);
}

async function saveSource(sid, config, dirtyKey, successText) {
  await apiRequest(`/api/source/${sid}/config?wait=1`, {
    method: 'POST',
    body: config,
  });
  sources[sid] = sources[sid] || {};
  sources[sid].config = {...(sources[sid].config || {}), ...config};
  if (dirtyKey) dirtyForms.delete(dirtyKey);
  renderDisplaySummary();
  renderStatus();
  if (successText) showNotif(successText, 'success');
}

async function refreshSource(sid) {
  await apiRequest(`/api/source/${sid}/refresh?wait=1`, {method: 'POST'});
  showNotif(`${sourceTitle(sid)}已刷新`, 'success');
}

async function useCurrentLocation(scope, sid) {
  if (!navigator.geolocation) {
    throw new Error('当前浏览器不支持定位。');
  }
  const pos = await getBrowserPosition();
  setWeatherLocationFields(scope, sid, pos.coords.latitude, pos.coords.longitude);
  dirtyForms.add(formKey(scope, sid));
  showNotif('已填入当前位置，请保存并刷新。', 'success');
}

function getBrowserPosition() {
  return new Promise((resolve, reject) => {
    navigator.geolocation.getCurrentPosition(resolve, reject, {
      enableHighAccuracy: false,
      timeout: 10000,
      maximumAge: 600000,
    });
  });
}

function setWeatherLocationFields(scope, sid, lat, lon) {
  const latEl = document.getElementById(fieldId(scope, sid, 'latitude'));
  const lonEl = document.getElementById(fieldId(scope, sid, 'longitude'));
  const cityEl = document.getElementById(fieldId(scope, sid, 'city'));
  const modeEl = document.getElementById(fieldId(scope, sid, 'location_mode'));
  if (latEl) latEl.value = Number(lat).toFixed(5);
  if (lonEl) lonEl.value = Number(lon).toFixed(5);
  if (cityEl) cityEl.value = '当前位置';
  if (modeEl) modeEl.value = 'auto';
}

async function ensureStationApp() {
  if (getActiveApp() === 'uk_station') return;
  await apiRequest('/api/current-app', {method: 'POST', body: {app_id: 'uk_station'}});
  state.current_app = 'uk_station';
}

async function switchApp(appId) {
  const data = await apiRequest('/api/current-app', {method: 'POST', body: {app_id: appId}});
  state.current_app = data.current_app || appId;
  updateAppSwitcher();
  renderStatus();
  showNotif('App 已切换', 'success');
}

async function applyLayout() {
  const layout = getSelectedLayout();
  const count = layout === 'dual' ? 2 : (layout === 'carousel' ? 3 : 1);
  const slots = Array.from({length: count}, (_, i) => document.getElementById(`slot_${i}`)?.value || 'mock');
  await ensureStationApp();
  await apiRequest('/api/app/uk_station/layout', {method: 'POST', body: {layout, slots}});
  updateLocalLayout(layout, slots);
  renderAll();
  showNotif('布局已应用', 'success');
}

function updateLocalLayout(layout, slots) {
  state.apps = state.apps || {};
  state.apps.uk_station = state.apps.uk_station || {};
  state.apps.uk_station.layout = layout;
  state.apps.uk_station.slots = slots;
}

function getSelectedLayout() {
  return document.querySelector('.layout-card.active')?.dataset.layout || getLayout();
}

function scheduleSettings() {
  clearTimeout(settingsTimer);
  settingsTimer = setTimeout(pushSettings, 650);
}

async function pushSettings() {
  const appSettings = {
    color_theme: document.getElementById('color_theme')?.value || 'amber',
    animations_enabled: document.getElementById('animations_enabled')?.value === 'true',
  };
  const deviceSettings = {
    brightness: Number(document.getElementById('brightness')?.value || 1),
    orientation: document.getElementById('orientation')?.value || 'portrait',
  };
  try {
    await Promise.all([
      apiRequest('/api/app/uk_station/settings', {method: 'POST', body: appSettings}),
      apiRequest('/api/device-settings', {method: 'POST', body: deviceSettings}),
    ]);
    state.apps = state.apps || {};
    state.apps.uk_station = state.apps.uk_station || {};
    state.apps.uk_station.app_settings = {...(state.apps.uk_station.app_settings || {}), ...appSettings};
    state.device_settings = {...(state.device_settings || {}), ...deviceSettings};
    renderDisplaySummary();
    renderStatus();
    showNotif(deviceSettings.orientation ? '显示设置已保存，方向重启后生效' : '显示设置已保存', 'success');
  } catch (err) {
    showNotif(err.message || '显示设置保存失败', 'error');
  }
}

// ---------------------------------------------------------------------------
// DOM events
// ---------------------------------------------------------------------------

document.addEventListener('click', evt => {
  const nav = evt.target.closest('.nav-item[data-page]');
  if (nav) {
    navigate(nav.dataset.page);
    return;
  }

  const layoutCard = evt.target.closest('.layout-card[data-layout]');
  if (layoutCard) {
    document.querySelectorAll('.layout-card').forEach(card => card.classList.remove('active'));
    layoutCard.classList.add('active');
    renderSlots();
    return;
  }

  const button = evt.target.closest('[data-action]');
  if (!button) return;
  const action = button.dataset.action;

  if (action === 'toggle-source') {
    const sid = button.dataset.source;
    if (openSources.has(sid)) openSources.delete(sid);
    else openSources.add(sid);
    button.closest('.source-card')?.classList.toggle('open');
    return;
  }

  if (action === 'add-row') {
    addRow(button.dataset.scope, button.dataset.source);
    return;
  }

  if (action === 'delete-row') {
    const item = button.closest('.row-editor-item');
    const editor = button.closest('.rows-editor');
    if (editor) dirtyForms.add(formKey(editor.dataset.scope, editor.dataset.source));
    item?.remove();
    return;
  }

  const runners = {
    'refresh-all': () => Promise.all([loadDeviceStatus(), loadSources(true)]),
    'reload-sources': () => loadSources(true),
    'refresh-device-status': () => loadDeviceStatus(),
    'save-cycle': () => saveCycle(false),
    'enable-cycle': () => saveCycle(true),
    'set-current-page': () => setCurrentPage(button.dataset.pageCard),
    'save-page': () => savePage(button.dataset.pageCard),
    'save-source': () => saveSourceFromForm(button.dataset.source, 'source'),
    'refresh-source': () => refreshSource(button.dataset.source),
    'use-current-location': () => useCurrentLocation(button.dataset.scope, button.dataset.source),
    'switch-app': () => switchApp(button.dataset.app),
    'apply-layout': () => applyLayout(),
  };
  if (runners[action]) {
    runButtonAction(button, '处理中...', runners[action]);
  }
});

document.addEventListener('input', evt => {
  markDirtyFromElement(evt.target);
  maybeSwitchWeatherToManual(evt.target);
  if (evt.target.closest('.rows-editor')) {
    const editor = evt.target.closest('.rows-editor');
    dirtyForms.add(formKey(editor.dataset.scope, editor.dataset.source));
  }
  if (['brightness'].includes(evt.target.id)) scheduleSettings();
});

function maybeSwitchWeatherToManual(target) {
  if (!target?.id || !target.id.endsWith('_weather_city')) return;
  if (!target.value.trim() || target.value.trim() === '当前位置') return;
  const parts = target.id.split('_');
  const scope = parts[1];
  const modeEl = document.getElementById(fieldId(scope, 'weather', 'location_mode'));
  if (modeEl && modeEl.value === 'auto') {
    modeEl.value = 'manual';
    dirtyForms.add(formKey(scope, 'weather'));
  }
}

document.addEventListener('change', evt => {
  markDirtyFromElement(evt.target);
  if (['color_theme', 'animations_enabled', 'orientation'].includes(evt.target.id)) {
    scheduleSettings();
  }
});

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------

function esc(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

bootstrap();
