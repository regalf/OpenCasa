const API = '/app/notify-test/api/v1';

async function api(method, path, body) {
  const opts = {
    method,
    headers: { 'Content-Type': 'application/json' },
    credentials: 'same-origin',
  };
  if (body) opts.body = JSON.stringify(body);
  const res = await fetch(API + path, opts);
  if (!res.ok) {
    const err = await res.json().catch(() => ({error: res.statusText}));
    throw new Error(err.error || res.statusText);
  }
  return res.json();
}

function fmtTime(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  const diff = Math.floor((Date.now() - d.getTime()) / 1000);
  if (diff < 60) return 'ora';
  if (diff < 3600) return Math.floor(diff / 60) + 'm';
  if (diff < 86400) return Math.floor(diff / 3600) + 'h';
  return d.toLocaleDateString();
}

async function sendNotif() {
  const sev = document.getElementById('notif-severity').value;
  const title = document.getElementById('notif-title').value.trim() || 'Notify Test';
  const msg = document.getElementById('notif-message').value.trim() || '(vuoto)';
  const btn = document.getElementById('send-btn');
  const msgEl = document.getElementById('send-msg');
  btn.disabled = true;
  btn.textContent = '⏳ Invio...';
  msgEl.textContent = '';
  msgEl.className = 'msg';
  try {
    await api('POST', '/notify', {
      title: title,
      message: msg,
      severity: sev,
    });
    msgEl.textContent = '✅ Notifica inviata!';
    msgEl.className = 'msg';
    document.getElementById('notif-message').value = '';
    loadNotifs();
  } catch (e) {
    msgEl.textContent = '❌ ' + e.message;
    msgEl.className = 'msg fail';
  }
  btn.disabled = false;
  btn.textContent = '✉️ Invia notifica';
}

async function loadNotifs() {
  const el = document.getElementById('notif-list');
  try {
    const res = await api('GET', '/notifications');
    const notifs = res.notifications || [];
    if (notifs.length === 0) {
      el.innerHTML = '<p class="dim">Nessuna notifica.</p>';
      return;
    }
    el.innerHTML = notifs.map(n => `
      <div class="notif-item ${n.severity || 'info'}">
        <div class="notif-body">
          <div class="notif-top">
            <span class="notif-name">${esc(n.app_id || n.title)}</span>
            <span class="notif-time">${fmtTime(n.timestamp)}</span>
          </div>
          <div class="notif-msg">${esc(n.message)}</div>
          <button class="notif-del" onclick="delNotif('${esc(n.id)}')">🗑️ Elimina</button>
        </div>
      </div>
    `).join('');
  } catch (e) {
    el.innerHTML = '<p class="dim" style="color:#f87171">Errore: ' + esc(e.message) + '</p>';
  }
}

async function delNotif(id) {
  try {
    await api('POST', '/notifications/delete', {id: id});
    loadNotifs();
  } catch (e) {
    alert(e.message);
  }
}

async function clearAll() {
  try {
    await api('POST', '/notifications/clear');
    loadNotifs();
  } catch (e) {
    alert(e.message);
  }
}

function esc(s) {
  if (s == null) return '';
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

loadNotifs();
