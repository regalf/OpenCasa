(function(){
'use strict';

const BASE = '/api/v1';
let token = localStorage.getItem('token');
let localeData = null;
let currentLang = 'it';
async function loadLocale(lang) {
  currentLang = lang || 'it';
  try {
    const r = await fetch('/locales/' + currentLang + '.json');
    localeData = await r.json();
  } catch(e) { localeData = {}; }
  document.getElementById('html-root').lang = currentLang;
  document.title = t('app.title');
}
function t(key, ...args) {
  let s = localeData?.[key] || key;
  if (args.length && s.includes('%s')) {
    let i = 0;
    s = s.replace(/%s/g, () => args[i++] ?? '');
  }
  return s;
}
let state = {
  view: 'dashboard',
  loggedIn: !!token,
  stats: null,
  storage: null,
  apps: [],
  notifications: [],
  info: {},
  files: [],
  filePath: '/',
  uploadProgress: -1,
  editing: null,
  editorContent: '',
  error: '',
  appDetail: null,
  appOutput: null,
  appOutputLoading: false,
  widgetsData: {},
  appViewId: null,
  users: [{ user: 'admin', pass: 'admin' }],
};

async function api(method, path, body) {
  const headers = {};
  if (body && !(body instanceof FormData)) {
    headers['Content-Type'] = 'application/json';
    body = JSON.stringify(body);
  }
  if (token) headers['Authorization'] = 'Bearer ' + token;
  const res = await fetch(BASE + path, { method, headers, body });
  if (res.status === 401) {
    token = null; localStorage.removeItem('token');
    state.loggedIn = false; render();
    throw new Error(t('error.unauthorized'));
  }
  if (path === '/files/download') return res;
  if (res.headers.get('content-type')?.includes('application/json')) return res.json();
  const text = await res.text();
  try { return JSON.parse(text); } catch(e) { return text; }
}

async function login() {
  const user = document.getElementById('login-user').value;
  const pass = document.getElementById('login-pass').value;
  const errEl = document.getElementById('login-error');
  const res = await fetch(BASE + '/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: user, password: pass }),
  }).then(r => r.json());
  if (res.token) {
    token = res.token;
    localStorage.setItem('token', token);
    state.loggedIn = true;
    state.error = '';
    closeSidebar();
    fetchAll(); render();
  } else {
    errEl.textContent = res.error || t('login.failed');
  }
}

function logout() {
  token = null; localStorage.removeItem('token');
  state.loggedIn = false; render();
}

function navigate(view) {
  closeSidebar();
  state.view = view; state.error = ''; state.appDetail = null; state.appOutput = null; state.appViewId = null;
  if (view === 'files' && state.files.length === 0) { loadFiles('/'); return; }
  if (view === 'dashboard') { fetchAll(); return; }
  if (view === 'apps') { loadApps(); return; }
  render();
}

function navigateApp(id) {
  try {
    state.view = 'app';
    state.appViewId = id;
    state.error = '';
    state.appDetail = null;
    state.appOutput = null;
    closeSidebar();
    render();
  } catch(e) { console.error('navigateApp:', e); state.error = e.message; render(); }
}
function toggleSidebar() { document.getElementById('sidebar').classList.toggle('open'); }
function closeSidebar() { const el = document.getElementById('sidebar'); if (el) el.classList.remove('open'); }

async function fetchAll() {
  try {
    const [s, st, a, n, i] = await Promise.all([
      api('GET','/system/stats').catch(() => null),
      api('GET','/storage').catch(() => null),
      api('GET','/apps').catch(() => null),
      api('GET','/notifications').catch(() => null),
      api('GET','/system/info').catch(() => null),
    ]);
    if (s && s.cpu) { state.stats = s; if (s.language) loadLocale(s.language); }
    if (st && st.filesystems) state.storage = st;
    if (a && a.apps) state.apps = a.apps;
    if (n && n.notifications) state.notifications = n.notifications;
    if (i && i.hostname) state.info = i;
  } catch(e) { state.error = e.message; }

  // Update/render immediately with main data (no widgets)
  if (state.view === 'dashboard' && document.getElementById('dash-grid')) {
    updateDashboardValues();
  } else {
    render();
  }

  // Widgets in background — don't block dashboard
  if (state.view === 'dashboard') {
    refreshWidgets().then(() => {
      if (document.getElementById('dash-widgets')) updateDashboardValues();
    }).catch(() => {});
  }
}

async function loadFiles(path) {
  try {
    const res = await api('GET', '/files?path=' + encodeURIComponent(path));
    state.filePath = res.path;
    state.files = res.entries || [];
    state.error = '';
  } catch(e) { state.error = e.message; }
  render();
}

function enterDir(name) {
  const sep = state.filePath.endsWith('/') ? '' : '/';
  loadFiles(state.filePath + sep + name);
}

function goUp() {
  const p = state.filePath.replace(/\/$/, '');
  const parent = p.substring(0, p.lastIndexOf('/')) || '/';
  loadFiles(parent);
}

async function openFile(name) {
  const path = joinPath(state.filePath, name);
  try {
    const res = await api('GET', '/files/read?path=' + encodeURIComponent(path));
    state.editing = path;
    state.editorContent = res.content || '';
  } catch(e) { state.error = e.message; }
  render();
}

async function saveFile() {
  const ta = document.getElementById('editor-textarea');
  await api('POST', '/files/write', { path: state.editing, content: ta ? ta.value : '' });
  state.editing = null;
  loadFiles(state.filePath);
}

function closeEditor() {
  state.editing = null;
  render();
}

async function deleteFile(name) {
  if (!confirm(t('files.delete_confirm', name))) return;
  await api('POST', '/files/delete', { path: joinPath(state.filePath, name) });
  loadFiles(state.filePath);
}

function uploadFile() {
  const input = document.createElement('input');
  input.type = 'file';
  input.onchange = () => {
    const file = input.files[0];
    if (!file) return;
    const form = new FormData();
    form.append('file', file);
    form.append('path', joinPath(state.filePath, file.name));
    const xhr = new XMLHttpRequest();
    state.uploadProgress = 0;
    render();
    xhr.upload.onprogress = e => {
      if (e.lengthComputable) {
        state.uploadProgress = Math.round((e.loaded / e.total) * 100);
        render();
      }
    };
    xhr.onload = () => { state.uploadProgress = -1; loadFiles(state.filePath); };
    xhr.onerror = () => { state.uploadProgress = -1; render(); };
    xhr.open('POST', BASE + '/files/upload');
    xhr.setRequestHeader('Authorization', 'Bearer ' + token);
    xhr.send(form);
  };
  input.click();
}

async function downloadFile(name) {
  const path = joinPath(state.filePath, name);
  const res = await fetch(BASE + '/files/download?path=' + encodeURIComponent(path), {
    headers: { 'Authorization': 'Bearer ' + token },
  });
  if (!res.ok) return;
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}

function createDir() {
  const name = prompt(t('files.dir_name_prompt'));
  if (name) { api('POST','/files/mkdir',{path:joinPath(state.filePath,name)}).then(()=>loadFiles(state.filePath)); }
}

async function createFile() {
  const name = prompt(t('files.new_file_prompt'));
  if (!name) return;
  await api('POST', '/files/write', { path: joinPath(state.filePath, name), content: '' });
  loadFiles(state.filePath);
}

async function loadApps() {
  const res = await api('GET','/apps');
  state.apps = res.apps || [];
  render();
}

async function showAppDetail(id) {
  state.appOutput = null;
  state.appOutputLoading = true;
  render();
  const res = await api('GET','/apps/' + encodeURIComponent(id));
  state.appDetail = res.app || null;
  state.appOutputLoading = false;
  render();
}

function closeAppDetail() {
  state.appDetail = null;
  state.appOutput = null;
  render();
}

async function runApp(id) {
  state.appOutputLoading = true;
  state.appOutput = null;
  state.error = '';
  render();
  try {
    const res = await api('POST','/apps/' + encodeURIComponent(id) + '/run');
    state.appOutput = res;
  } catch(e) {
    state.appOutput = {error: e.message};
  }
  state.appOutputLoading = false;
  render();
  try {
    const r = await api('GET','/apps/' + encodeURIComponent(id));
    if (r.app) state.appDetail = r.app;
  } catch(e) {}
  render();
}

async function startWebApp(id) {
  await api('POST','/apps/' + encodeURIComponent(id) + '/start');
  showAppDetail(id);
  loadApps();
}

async function stopWebApp(id) {
  await api('POST','/apps/' + encodeURIComponent(id) + '/stop');
  showAppDetail(id);
  loadApps();
}

async function uninstallApp(id) {
  if (!confirm(t('apps.remove_confirm'))) return;
  await api('POST','/apps/' + encodeURIComponent(id) + '/uninstall');
  state.appDetail = null;
  state.appOutput = null;
  loadApps();
}

function openApp(id, type, status) {
  if (type === 'web' && status === 'running') {
    navigateApp(id);
  } else {
    showAppDetail(id);
  }
}

function isWidgetEnabled(id) {
  return localStorage.getItem('widget_' + id) !== 'false';
}
function setWidgetEnabled(id, en) {
  localStorage.setItem('widget_' + id, en ? 'true' : 'false');
}

function renderAppTab(id) {
  const app = state.apps.find(a => a.id === id);
  if (!app) {
    return `<div class="app-tab-content" style="align-items:center;justify-content:center;padding:3rem"><p class="dim">${t('apps.not_found')}</p></div>`;
  }
  if (app.status !== 'running') {
    return `
      <div class="app-tab-content" style="align-items:center;justify-content:center;padding:3rem">
        <p style="margin-bottom:1rem">${escapeHtml(app.name)} — ${t('apps.not_running')}</p>
        <button class="btn btn-success" onclick="startWebAppFromTab('${escapeHtml(id)}')">${t('apps.start')}</button>
      </div>
    `;
  }
  return `<div class="app-tab-content"><iframe class="app-tab-iframe" src="/app/${encodeURIComponent(id)}/" sandbox="allow-scripts allow-same-origin allow-forms allow-popups"></iframe></div>`;
}

async function startWebAppFromTab(id) {
  await api('POST','/apps/' + encodeURIComponent(id) + '/start');
  await loadApps();
  navigateApp(id);
}

async function refreshWidgets() {
  if (state.view !== 'dashboard') return;
  const ids = state.apps.filter(a => isWidgetEnabled(a.id)).map(a => a.id);
  if (!ids.length) return;
  for (const id of ids) {
    try {
      const res = await api('GET', '/apps/' + encodeURIComponent(id) + '/widget');
      if (res && res.data != null) state.widgetsData[id] = res.data;
    } catch(e) {}
  }
}

function updateDashboardValues() {
  const s = state.stats;
  const st = state.storage;
  const a = state.apps;
  const i = state.info;
  // System info
  const sysEl = document.getElementById('sys-name');
  if (sysEl && i?.hostname) {
    sysEl.textContent = i.ostype + ' ' + i.osrelease + ' — ' + i.hostname + ' (' + i.machine + ')';
  }
  // CPU
  if (s?.cpu) {
    const idle = s.cpu.idle ?? 0;
    const used = 100 - idle;
    const barEl = document.getElementById('cpu-bar');
    const pctEl = document.getElementById('cpu-pct');
    const specEl = document.getElementById('cpu-spec');
    if (barEl) barEl.style.width = used + '%';
    if (pctEl) pctEl.textContent = used.toFixed(1) + t('dashboard.cpu_used');
    if (specEl) specEl.textContent = s.cpu.cores + ' ' + t('dashboard.cpu_core') + ' ' + s.cpu.freq_mhz;
  }
  // Memory
  if (s?.memory) {
    const memUnit = s.memory_unit === 'MB' ? 1024*1024 : 1024*1024*1024;
    const memLabel = s.memory_unit === 'MB' ? 'MB' : 'GB';
    const totalMem = (s.memory.total / memUnit).toFixed(1);
    const usedMem = (s.memory.used / memUnit).toFixed(1);
    const memPct = s.memory.total > 0 ? (s.memory.used / s.memory.total * 100) : 0;
    const barEl = document.getElementById('mem-bar');
    const detEl = document.getElementById('mem-detail');
    const pctEl = document.getElementById('mem-pct');
    if (barEl) barEl.style.width = memPct + '%';
    if (detEl) detEl.textContent = usedMem + ' / ' + totalMem + ' ' + memLabel;
    if (pctEl) pctEl.textContent = memPct.toFixed(1) + '%';
  }
  // Storage
  if (st?.filesystems?.length) {
    const tbody = document.getElementById('stor-body');
    if (tbody) {
      tbody.innerHTML = st.filesystems.map(fs => `
        <tr>
          <td>${escapeHtml(fs.mount)}</td>
          <td>${escapeHtml(fs.used)}</td>
          <td>${escapeHtml(fs.total)}</td>
          <td><div class="mini-bar"><div class="fill" style="width:${fs.capacity}%"></div></div></td>
        </tr>
      `).join('');
    }
  }
  // Widgets row
  const wr = document.getElementById('dash-widgets');
  if (wr) {
    const enabled = a.filter(x => isWidgetEnabled(x.id));
    if (enabled.length) {
      wr.innerHTML = enabled.map(w => {
        const wd = state.widgetsData[w.id];
        return '<div class="widget-mini" onclick="openApp(\'' + escapeHtml(w.id) + '\',\'' + w.type + '\',\'' + w.status + '\')">' +
          '<h4>' + escapeHtml(w.name) + '</h4>' +
          (wd ? Object.entries(wd).map(([k,v]) => {
            const lbl = typeof v === 'object' ? (v.label || '') : String(v);
            const det = typeof v === 'object' ? (v.detail || '') : '';
            return '<div class="widget-row"><span class="widget-label">' + escapeHtml(k) + '</span>' +
              '<span class="widget-value">' + escapeHtml(lbl) + '</span></div>' +
              (det ? '<div class="widget-detail">' + escapeHtml(det) + '</div>' : '');
          }).join('') : '<span class="dim">' + t('apps.no_widget_data') + '</span>') +
        '</div>';
      }).join('');
    }
  }
}

// Rendering
function html(strings, ...vals) {
  let out = '';
  strings.forEach((s, i) => { out += s + (vals[i] !== undefined ? vals[i] : ''); });
  return out;
}

function escapeHtml(s) {
  if (s == null) return '';
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}
function joinPath(dir, name) {
  return dir.endsWith('/') ? dir + name : dir + '/' + name;
}
const DANGEROUS_PATHS = ['/', '/etc', '/usr', '/var', '/sys', '/proc', '/dev', '/boot', '/root', '/bin', '/sbin', '/lib', '/lib64'];
function isDangerousPath(p) {
  return DANGEROUS_PATHS.some(d => p === d || p.startsWith(d + '/'));
}

function render() {
  const app = document.getElementById('app');
  if (!state.loggedIn) {
    app.innerHTML = renderLogin();
    return;
  }
  const webApps = state.apps.filter(a => a.type === 'web');
  const appTabId = state.view === 'app' ? state.appViewId : null;
  app.innerHTML = `
    <button class="hamburger" onclick="toggleSidebar()">☰</button>
    <nav class="sidebar" id="sidebar">
      <div class="brand">${t('app.brand')}</div>
      <button class="${state.view==='dashboard'?'active':''}" onclick="navigate('dashboard')">${t('nav.dashboard')}</button>
      <button class="${state.view==='files'?'active':''}" onclick="navigate('files')">${t('nav.files')}</button>
      <button class="${state.view==='apps'?'active':''}" onclick="navigate('apps')">${t('nav.apps')}</button>
      ${webApps.length > 0 ? `
      <hr class="sidebar-sep">
      ${webApps.map(a => `
        <button class="${state.view==='app' && state.appViewId===a.id ? 'active' : ''}" onclick="navigateApp('${escapeHtml(a.id)}')">
          <span class="sidebar-app-letter">${escapeHtml(a.name[0] || '?')}</span>
          ${escapeHtml(a.name)}
        </button>
      `).join('')}
      ` : ''}
      <div class="spacer"></div>
      <button onclick="logout()">${t('nav.logout')}</button>
    </nav>
    <section class="content">
      ${state.view === 'dashboard' ? renderDashboard() : ''}
      ${state.view === 'files' ? renderFileManager() : ''}
      ${state.view === 'apps' ? renderAppManager() : ''}
      ${appTabId ? renderAppTab(appTabId) : ''}
    </section>
  `;
}

function renderLogin() {
  const wa = state.apps.filter(x => isWidgetEnabled(x.id));
  return `
    <div class="login-screen">
      <div class="login-card">
        <h1>${t('login.title')}</h1>
        <p class="subtitle">${t('login.subtitle')}</p>
        <input id="login-user" placeholder="${t('login.username')}" />
        <input id="login-pass" type="password" placeholder="${t('login.password')}" />
        <p class="login-error" id="login-error"></p>
        <button onclick="login()">${t('login.submit')}</button>
      </div>
      ${wa.length > 0 ? `
      <div class="widget" style="margin-top:1rem">
        <h3>${t('dashboard.widgets')}</h3>
        <div class="widgets-row">
          ${wa.map(w => {
            const wd = state.widgetsData[w.id];
            return `
              <div class="widget-mini" onclick="openApp('${escapeHtml(w.id)}','${w.type}','${w.status}')">
                <h4>${escapeHtml(w.name)}</h4>
                ${wd ? Object.entries(wd).map(([k,v]) => {
                  const lbl = typeof v === 'object' ? (v.label || '') : String(v);
                  const det = typeof v === 'object' ? (v.detail || '') : '';
                  return `
                  <div class="widget-row">
                    <span class="widget-label">${escapeHtml(k)}</span>
                    <span class="widget-value">${escapeHtml(lbl)}</span>
                  </div>
                  ${det ? `<div class="widget-detail">${escapeHtml(det)}</div>` : ''}`;
                }).join('') : `<span class="dim">${t('apps.no_widget_data')}</span>`}
              </div>
            `;
          }).join('')}
        </div>
      </div>
      ` : ''}
    </div>
  `;
}

function renderDashboard() {
  const s = state.stats;
  const st = state.storage;
  const a = state.apps;
  const n = state.notifications;
  const i = state.info;
  const idle = s?.cpu?.idle ?? 0;
  const used = 100 - idle;
  const memUnit = s?.memory_unit === 'MB' ? 1024*1024 : 1024*1024*1024;
  const memLabel = s?.memory_unit === 'MB' ? 'MB' : 'GB';
  const totalMem = s?.memory ? (s.memory.total / memUnit).toFixed(1) : 0;
  const usedMem = s?.memory ? (s.memory.used / memUnit).toFixed(1) : 0;
  const memPct = s?.memory ? (s.memory.used / s.memory.total * 100) : 0;

  return `
    <div class="dashboard">
      <h1>${t('dashboard.title')}</h1>
      ${i?.hostname ? `<p class="sysname" id="sys-name">${escapeHtml(i.ostype)} ${escapeHtml(i.osrelease)} — ${escapeHtml(i.hostname)} (${escapeHtml(i.machine)})</p>` : ''}
      ${(!s && !st && !a) ? `<div class="loading-spinner"></div>` : `
      <div class="grid" id="dash-grid">
        <div class="widget">
          <h3>${t('dashboard.cpu')}</h3>
          ${s?.cpu ? `
            <div class="bar-container"><div class="bar blue" id="cpu-bar" style="width:${used}%"></div></div>
            <div class="details">
              <span id="cpu-pct">${used.toFixed(1)}${t('dashboard.cpu_used')}</span>
              <span class="dim" id="cpu-spec">${s.cpu.cores} ${t('dashboard.cpu_core')} ${s.cpu.freq_mhz}</span>
            </div>
            ${s.cpu.model ? `<p class="model">${escapeHtml(s.cpu.model)}</p>` : ''}
          ` : `<p class="dim">${t('dashboard.loading')}</p>`}
        </div>
        <div class="widget">
          <h3>${t('dashboard.memory')}</h3>
          ${s?.memory ? `
            <div class="bar-container"><div class="bar purple" id="mem-bar" style="width:${memPct}%"></div></div>
            <div class="details">
              <span id="mem-detail">${usedMem} / ${totalMem} ${memLabel}</span>
              <span id="mem-pct">${memPct.toFixed(1)}%</span>
            </div>
          ` : `<p class="dim">${t('dashboard.loading')}</p>`}
        </div>
        <div class="widget">
          <h3>${t('dashboard.storage')}</h3>
          ${st?.filesystems?.length ? `
            <table class="storage-table">
              <thead><tr><th>${t('dashboard.storage_mount')}</th><th>${t('dashboard.storage_used')}</th><th>${t('dashboard.storage_total')}</th><th>${t('dashboard.storage_cap')}</th></tr></thead>
              <tbody id="stor-body">
                ${st.filesystems.map(fs => `
                  <tr>
                    <td>${escapeHtml(fs.mount)}</td>
                    <td>${escapeHtml(fs.used)}</td>
                    <td>${escapeHtml(fs.total)}</td>
                    <td><div class="mini-bar"><div class="fill" style="width:${fs.capacity}%"></div></div></td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          ` : `<p class="dim">${t('dashboard.loading')}</p>`}
        </div>
        <div class="widget">
          <h3>${t('dashboard.installed_apps')}</h3>
          ${a.length > 0 ? `
            <div class="app-grid">
              ${a.map(app => `
                <div class="app-card" onclick="openApp('${escapeHtml(app.id)}','${app.type}','${app.status}')" style="cursor:pointer">
                  <button class="app-card-menu" onclick="event.stopPropagation();showAppDetail('${escapeHtml(app.id)}')">⋮</button>
                  <img class="app-card-icon" src="/api/v1/apps/${encodeURIComponent(app.id)}/icon" alt="" onerror="this.style.display='none'"/>
                  <div class="app-card-icon-placeholder" style="${app.icon ? 'display:none' : ''}">${escapeHtml(app.name[0] || '?')}</div>
                  <span class="app-name">${escapeHtml(app.name)}</span>
                  ${app.status === 'running' ? `<span class="app-status running">● ${t('apps.running')}</span>` : ''}
                </div>
              `).join('')}
            </div>
          ` : `<p class="dim">${t('dashboard.no_apps')}</p>`}
        </div>
      </div>
      `}
      ${a.filter(x => isWidgetEnabled(x.id)).length > 0 ? `
      <div class="widget">
        <h3>${t('dashboard.widgets')}</h3>
        <div class="widgets-row" id="dash-widgets">
          ${a.filter(x => isWidgetEnabled(x.id)).map(w => {
            const wd = state.widgetsData[w.id];
            return `
              <div class="widget-mini" onclick="openApp('${escapeHtml(w.id)}','${w.type}','${w.status}')">
                <h4>${escapeHtml(w.name)}</h4>
                ${wd ? Object.entries(wd).map(([k,v]) => {
                  const lbl = typeof v === 'object' ? (v.label || '') : String(v);
                  const det = typeof v === 'object' ? (v.detail || '') : '';
                  return `
                  <div class="widget-row">
                    <span class="widget-label">${escapeHtml(k)}</span>
                    <span class="widget-value">${escapeHtml(lbl)}</span>
                  </div>
                  ${det ? `<div class="widget-detail">${escapeHtml(det)}</div>` : ''}`;
                }).join('') : `<span class="dim">${t('apps.no_widget_data')}</span>`}
              </div>
            `;
          }).join('')}
        </div>
      </div>
      ` : ''}
      ${n.length > 0 ? `
        <h2 class="section-title">${t('dashboard.notifications')}</h2>
        <div class="notifications">
          ${n.map(not => `
            <div class="notif ${not.severity || 'info'}">
              <strong>${escapeHtml(not.title)}</strong> — ${escapeHtml(not.message)}
              <span class="time">${escapeHtml(not.timestamp)}</span>
            </div>
          `).join('')}
            </div>
          ` : ''}
      ${state.error ? `<p style="color:#f87171">${escapeHtml(state.error)}</p>` : ''}
    </div>
  `;
}

function renderFileManager() {
  return `
    <div class="fm-toolbar">
      <button onclick="goUp()">⬆</button>
      <span class="fm-path">${escapeHtml(state.filePath)}</span>
      <button onclick="uploadFile()">${t('files.upload')}</button>
      <button onclick="createFile()">${t('files.new_file')}</button>
      <button onclick="createDir()">${t('files.new_dir')}</button>
      <button onclick="navigate('dashboard')">${t('files.back_dashboard')}</button>
    </div>
    ${state.editing ? `
      <div class="editor-overlay" onclick="if(event.target===this)closeEditor()">
        <div class="editor-modal">
          <div class="editor-header">
            <h3>${t('files.editing')} ${escapeHtml(state.editing)}</h3>
          </div>
          <div id="editor-container" style="flex:1;min-height:0;display:flex">
            <textarea id="editor-textarea"
              style="flex:1;background:#0f172a;color:#e2e8f0;border:none;padding:.75rem;font-family:monospace;resize:none;font-size:14px;outline:none">${escapeHtml(state.editorContent)}</textarea>
          </div>
          <div class="editor-footer">
            <button class="btn btn-success" onclick="saveFile()">${t('files.save')}</button>
            <button class="btn btn-danger" onclick="closeEditor()">${t('files.cancel')}</button>
          </div>
        </div>
      </div>
    ` : ''}
    ${state.error ? `<p style="color:#f87171;margin-bottom:.5rem">${escapeHtml(state.error)}</p>` : ''}
    ${state.uploadProgress >= 0 ? `
      <div class="progress-bar">
        <div class="progress-bar-fill" style="width:${state.uploadProgress}%"></div>
        <span class="progress-bar-text">${state.uploadProgress}%</span>
      </div>
    ` : ''}
    ${isDangerousPath(state.filePath) ? `<div class="warning-banner">${t('files.danger_warning', escapeHtml(state.filePath))}</div>` : ''}
    <table class="file-table">
      <thead><tr><th>${t('files.name')}</th><th>${t('files.size')}</th><th>${t('files.date')}</th><th></th></tr></thead>
      <tbody>
        ${state.files.length === 0 ? `
          <tr><td colspan="4" style="text-align:center;padding:2rem;color:#64748b">${t('files.empty')}</td></tr>
        ` : state.files.map(e => `
          <tr>
            <td>
              ${e.is_dir
                ? `<a onclick="enterDir('${escapeHtml(e.name)}')">📁 ${escapeHtml(e.name)}</a>`
                : `📄 ${escapeHtml(e.name)}`
              }
            </td>
            <td>${e.is_dir ? '—' : (e.size < 1024 ? e.size + ' ' + t('files.bytes') : (e.size/1024).toFixed(1) + ' ' + t('files.kilobytes'))}</td>
            <td>${escapeHtml(e.mod_time)}</td>
            <td class="file-actions">
              ${!e.is_dir ? `
                <button onclick="openFile('${escapeHtml(e.name)}')" title="${t('files.edit')}">✏️</button>
                <button onclick="downloadFile('${escapeHtml(e.name)}')" title="${t('files.download')}">⬇️</button>
              ` : ''}
              <button onclick="deleteFile('${escapeHtml(e.name)}')" title="${t('files.delete')}">🗑️</button>
            </td>
          </tr>
        `).join('')}
      </tbody>
    </table>
  `;
}

function renderAppManager() {
  const d = state.appDetail;
  return `
    <h1 style="margin-bottom:1rem">${t('apps.title')}</h1>
    ${state.apps.length === 0 ? `<p class="dim">${t('apps.empty_list')}</p>` : `
      <div class="apps-grid">
        ${state.apps.map(app => `
          <div class="app-card" onclick="openApp('${escapeHtml(app.id)}','${app.type}','${app.status}')">
            <button class="app-card-menu" onclick="event.stopPropagation();showAppDetail('${escapeHtml(app.id)}')">⋮</button>
            <img class="app-card-icon" src="/api/v1/apps/${encodeURIComponent(app.id)}/icon" alt="" onerror="this.style.display='none'"/>
            <div class="app-card-icon-placeholder" style="${app.icon ? 'display:none' : ''}">${escapeHtml(app.name[0] || '?')}</div>
            <span class="app-card-name">${escapeHtml(app.name)}</span>
            <span class="app-card-type ${app.type}">${app.type}</span>
            ${app.status === 'running' ? `<span class="app-card-status running">● ${t('apps.running')}</span>` : ''}
          </div>
        `).join('')}
      </div>
    `}
    ${d ? `
      <div class="detail-overlay" onclick="if(event.target===this)closeAppDetail()">
        <div class="detail-modal">
          <div class="detail-header">
            <div>
              <h2>${escapeHtml(d.name)}</h2>
              <span class="dim" style="font-size:.85rem">${escapeHtml(d.id)} v${escapeHtml(d.version)}</span>
            </div>
            <button class="btn" onclick="closeAppDetail()">${t('apps.cancel')}</button>
          </div>
          ${d.author ? `<p class="dim">${t('apps.author')}: ${escapeHtml(d.author)}</p>` : ''}
          ${d.description ? `<p>${escapeHtml(d.description)}</p>` : ''}
          <div class="detail-section">
            <strong>${t('apps.type')}:</strong> <span class="app-card-type ${d.type}">${d.type}</span>
            ${d.type === 'web' && d.port ? `<span style="margin-left:1rem;color:#64748b">port ${d.port}</span>` : ''}
          </div>
          ${d.permissions && d.permissions.length ? `
            <div class="detail-section">
              <strong>${t('apps.permissions')}:</strong>
              <div class="perm-list">
                ${d.permissions.map(p => `<span class="perm-badge">${escapeHtml(p)}</span>`).join('')}
              </div>
            </div>
          ` : ''}
          <div class="detail-section">
            <label style="display:flex;align-items:center;gap:.5rem;cursor:pointer;font-size:.9rem">
              <input type="checkbox" onchange="setWidgetEnabled('${escapeHtml(d.id)}',this.checked)" ${isWidgetEnabled(d.id) ? 'checked' : ''}>
              ${t('apps.show_widget')}
            </label>
          </div>
          <div class="detail-section">
            <strong>${t('apps.status')}:</strong>
            <span class="status-badge ${d.status}">${d.status}</span>
            ${d.pid > 0 ? `<span class="pid-text">PID ${d.pid}</span>` : ''}
          </div>
          <div class="detail-actions">
            ${d.type === 'tool' || d.type === 'widget' ? `
              <button class="btn btn-success" onclick="runApp('${escapeHtml(d.id)}')" ${state.appOutputLoading ? 'disabled' : ''}>
                ${state.appOutputLoading ? t('apps.running') + '...' : t('apps.run')}
              </button>
            ` : ''}
            ${d.type === 'web' ? `
              ${d.status === 'running'
                ? `<button class="btn btn-danger" onclick="stopWebApp('${escapeHtml(d.id)}')">${t('apps.stop')}</button>
                   <a href="/app/${encodeURIComponent(d.id)}" target="_blank" class="btn btn-primary">${t('apps.open')}</a>`
                : `<button class="btn btn-success" onclick="startWebApp('${escapeHtml(d.id)}')">${t('apps.start')}</button>`
              }
            ` : ''}
            <button class="btn btn-danger" style="margin-left:auto" onclick="uninstallApp('${escapeHtml(d.id)}')">${t('apps.uninstall')}</button>
          </div>
          ${state.appOutput ? `
            <div class="detail-section">
              <strong>${t('apps.output')}</strong>
              ${state.appOutput.error ? `<p style="color:#f87171">${escapeHtml(state.appOutput.error)}</p>` : `
                <pre class="app-output">${escapeHtml(state.appOutput.stdout || '')}${state.appOutput.stderr ? '\n--- stderr ---\n' + escapeHtml(state.appOutput.stderr) : ''}${state.appOutput.returncode !== 0 ? '\n' + t('apps.exit_code') + ': ' + state.appOutput.returncode : ''}</pre>
              `}
            </div>
          ` : state.appOutputLoading ? `<p class="dim">${t('apps.running')}...</p>` : ''}
          ${d.logs && d.logs.length ? `
            <div class="detail-section">
              <strong>${t('apps.recent_logs')}</strong>
              ${d.logs.slice().reverse().map(log => `
                <div class="log-entry">
                  <span class="log-time">${escapeHtml(log.timestamp)}</span>
                  <span class="log-rc ${log.returncode === 0 ? 'ok' : 'fail'}">exit ${log.returncode}</span>
                  <pre class="log-output">${escapeHtml((log.stdout || '').substring(0, 200))}</pre>
                </div>
              `).join('')}
            </div>
          ` : ''}
        </div>
      </div>
    ` : ''}
    ${state.error ? `<p style="color:#f87171">${escapeHtml(state.error)}</p>` : ''}
  `;
}

// Auto-refresh dashboard every 5s
setInterval(() => {
  if (state.loggedIn && state.view === 'dashboard') fetchAll();
}, 5000);

// Initial render — load default locale then fetch
loadLocale('en').then(fetchAll);
window.login = login;
window.logout = logout;
window.navigate = navigate;
window.enterDir = enterDir;
window.goUp = goUp;
window.openFile = openFile;
window.saveFile = saveFile;
window.closeEditor = closeEditor;
window.deleteFile = deleteFile;
window.uploadFile = uploadFile;
window.downloadFile = downloadFile;
window.createDir = createDir;
window.createFile = createFile;
window.showAppDetail = showAppDetail;
window.closeAppDetail = closeAppDetail;
window.runApp = runApp;
window.startWebApp = startWebApp;
window.stopWebApp = stopWebApp;
window.uninstallApp = uninstallApp;
window.openApp = openApp;
})();
