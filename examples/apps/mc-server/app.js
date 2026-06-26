(function(){
'use strict';

var API = '/app/mc-server';
var _pollTimer = null;
var _outputTimer = null;
var _dlTimer = null;

function byId(id) { return document.getElementById(id); }
function qsa(s) { return document.querySelectorAll(s); }

function showNotif(msg, type) {
  var n = byId('notif');
  n.textContent = msg;
  n.className = 'notif ' + type + ' hidden';
  requestAnimationFrame(function() { n.classList.remove('hidden'); });
  clearTimeout(n._hide);
  n._hide = setTimeout(function() { n.classList.add('hidden'); }, 4000);
}

// ── Tabs ──
qsa('.tab-btn').forEach(function(btn) {
  btn.addEventListener('click', function() {
    qsa('.tab-btn').forEach(function(b) { b.classList.remove('active'); });
    qsa('.tab-content').forEach(function(t) { t.classList.remove('active'); });
    btn.classList.add('active');
    byId('tab-' + btn.dataset.tab).classList.add('active');
    if (btn.dataset.tab === 'output') startOutputPoll();
    else stopOutputPoll();
    if (btn.dataset.tab === 'config') loadConfig();
    if (btn.dataset.tab === 'releases') loadReleases();
    if (btn.dataset.tab === 'status') loadStatus();
  });
});

// ── Status ──
function loadStatus() {
  fetch(API + '/api/status').then(function(r) { return r.json(); }).then(function(d) {
    byId('s-running').textContent = d.running ? 'Running' : 'Stopped';
    byId('s-running').className = 'stat-value status-dot ' + (d.running ? 'running' : 'stopped');
    byId('s-port').textContent = d.port || '--';
    byId('s-gamemode').textContent = ({'0':'Survival','1':'Creative','2':'Adventure','3':'Spectator'}[d.gamemode]) || d.gamemode || '--';
    byId('s-motd').textContent = d.motd || '--';
    byId('s-binary').textContent = d.installed ? 'installed' : 'missing';
    byId('s-world').textContent = d.world_exists ? 'exists' : 'none';
    byId('btn-start').disabled = d.running || !d.installed;
    byId('btn-stop').disabled = !d.running;
    byId('btn-restart').disabled = !d.running;
  }).catch(function(e) { showNotif('Failed to load status: ' + e.message, 'error'); });
}

byId('btn-start').addEventListener('click', function() {
  fetch(API + '/api/start', {method:'POST'}).then(function(r) { return r.json(); }).then(function(d) {
    if (d.success) { showNotif('Server started (PID: ' + d.pid + ')', 'success'); loadStatus(); }
    else showNotif(d.error, 'error');
  }).catch(function(e) { showNotif(e.message, 'error'); });
});

byId('btn-stop').addEventListener('click', function() {
  fetch(API + '/api/stop', {method:'POST'}).then(function(r) { return r.json(); }).then(function(d) {
    if (d.success) { showNotif('Server stopped', 'info'); loadStatus(); }
    else showNotif(d.error, 'error');
  }).catch(function(e) { showNotif(e.message, 'error'); });
});

byId('btn-restart').addEventListener('click', function() {
  fetch(API + '/api/restart', {method:'POST'}).then(function(r) { return r.json(); }).then(function(d) {
    if (d.success) { showNotif('Server restarted (PID: ' + d.pid + ')', 'success'); loadStatus(); }
    else showNotif(d.error, 'error');
  }).catch(function(e) { showNotif(e.message, 'error'); });
});

// ── Releases ──
function loadInstalled() {
  fetch(API + '/api/installed').then(function(r) { return r.json(); }).then(function(d) {
    var info = byId('installed-info');
    if (d.installed) {
      info.classList.remove('hidden');
      byId('bi-version').textContent = d.version || 'yes';
    } else {
      info.classList.add('hidden');
    }
  }).catch(function() {});
}

function loadReleases() {
  var list = byId('release-list');
  if (list.dataset.loaded) return;
  list.dataset.loaded = '1';
  list.innerHTML = '<div class="dim">Loading releases...</div>';
  fetch(API + '/api/releases').then(function(r) { return r.json(); }).then(function(d) {
    list.innerHTML = '';
    if (d.error) {
      list.innerHTML = '<div class="notice">Releases unavailable: ' + escapeHtml(d.error) + '</div>';
      return;
    }
    var rels = d.releases || [];
    if (rels.length === 0) {
      list.innerHTML = '<div class="notice">No releases found on GitHub. Download the binary manually and place it in the server directory.</div>';
      loadInstalled();
      return;
    }
    rels.forEach(function(r) {
      var card = document.createElement('div');
      card.className = 'release-card';
      var assetsHtml = '';
      (r.assets || []).forEach(function(a) {
        var highlight = a.name.indexOf('macppc') !== -1 || a.name.indexOf('openbsd') !== -1 ? ' btn-green' : '';
        assetsHtml += '<button class="btn' + highlight + ' btn-sm dl-btn" data-url="' + escapeAttr(a.url) + '" data-name="' + escapeAttr(a.name) + '">Download ' + escapeHtml(a.name) + ' (' + fmtSize(a.size) + ')</button>';
      });
      card.innerHTML = '<div class="rel-tag">' + escapeHtml(r.tag) + '</div>' +
        '<div class="rel-name">' + escapeHtml(r.name || r.tag) + '</div>' +
        '<div class="rel-date">' + (r.published ? r.published.slice(0,10) : '') + '</div>' +
        '<div class="rel-actions">' + assetsHtml + '</div>';
      list.appendChild(card);
    });
    loadInstalled();
    // bind download buttons
    qsa('.dl-btn').forEach(function(btn) {
      btn.addEventListener('click', function() {
        var url = btn.dataset.url;
        var name = btn.dataset.name;
        if (!url) return;
        byId('dl-progress').classList.remove('hidden');
        byId('dl-status').textContent = 'Downloading ' + name + '...';
        fetch(API + '/api/download', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({url:url, name:name})})
          .then(function(r) { return r.json(); }).then(function(d) {
          byId('dl-progress').classList.add('hidden');
          if (d.success) {
            showNotif('Downloaded ' + (d.path || name), 'success');
            loadInstalled();
            loadStatus();
          } else {
            showNotif('Download failed: ' + d.error, 'error');
          }
        }).catch(function(e) {
          byId('dl-progress').classList.add('hidden');
          showNotif(e.message, 'error');
        });
      });
    });
  }).catch(function(e) {
    list.innerHTML = '<div class="notice">Failed to fetch releases: ' + escapeHtml(e.message) + '</div>';
  });
}

function fmtSize(s) {
  if (!s) return '';
  s = parseInt(s);
  if (s < 1024) return s + ' B';
  if (s < 1048576) return (s / 1024).toFixed(0) + ' KB';
  return (s / 1048576).toFixed(1) + ' MB';
}

// ── Config ──
function loadConfig() {
  var list = byId('config-list');
  var editor = byId('config-editor');
  var notice = byId('config-notice');
  fetch(API + '/api/config').then(function(r) { return r.json(); }).then(function(d) {
    if (d.error) { showNotif(d.error, 'error'); return; }
    if (!d.exists) {
      editor.classList.add('hidden');
      notice.classList.remove('hidden');
      return;
    }
    notice.classList.add('hidden');
    editor.classList.remove('hidden');
    list.innerHTML = '';
    var keys = Object.keys(d.properties);
    if (keys.length === 0) {
      list.innerHTML = '<div class="dim">All settings are commented out. Uncomment and set values, then save.</div>';
      return;
    }
    keys.forEach(function(k) {
      var row = document.createElement('div');
      row.className = 'config-row';
      row.innerHTML = '<span class="ckey">' + escapeHtml(k) + '</span><input class="cval" data-key="' + escapeAttr(k) + '" value="' + escapeAttr(d.properties[k]) + '">';
      list.appendChild(row);
    });
  }).catch(function(e) { showNotif('Failed to load config: ' + e.message, 'error'); });
}

byId('btn-save-config').addEventListener('click', function() {
  var props = {};
  qsa('.cval').forEach(function(inp) {
    props[inp.dataset.key] = inp.value;
  });
  fetch(API + '/api/config', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(props)})
    .then(function(r) { return r.json(); }).then(function(d) {
    if (d.success) showNotif('Configuration saved', 'success');
    else showNotif(d.error, 'error');
  }).catch(function(e) { showNotif(e.message, 'error'); });
});

function escapeHtml(s) { return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }
function escapeAttr(s) { return String(s).replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

// ── Output ──
var _autoScroll = true;

byId('btn-auto-scroll').addEventListener('click', function() {
  _autoScroll = !_autoScroll;
  byId('btn-auto-scroll').classList.toggle('active');
});

byId('btn-clear-output').addEventListener('click', function() {
  byId('output-box').innerHTML = '';
});

function appendOutput(lines) {
  var el = byId('output-box');
  var wasEmpty = el.textContent.trim() === '' || el.textContent === 'Waiting for server output...';
  if (wasEmpty) el.innerHTML = '';
  lines.forEach(function(l) {
    var d = document.createElement('div');
    d.textContent = l;
    el.appendChild(d);
  });
  if (_autoScroll) el.scrollTop = el.scrollHeight;
}

function startOutputPoll() {
  stopOutputPoll();
  _outputTimer = setInterval(function() {
    fetch(API + '/api/output?lines=50').then(function(r) { return r.json(); }).then(function(d) {
      if (d.lines && d.lines.length > 0) appendOutput(d.lines);
    }).catch(function() {});
  }, 2000);
  fetch(API + '/api/output?lines=50').then(function(r) { return r.json(); }).then(function(d) {
    if (d.lines) appendOutput(d.lines);
  }).catch(function() {});
}

function stopOutputPoll() {
  if (_outputTimer) { clearInterval(_outputTimer); _outputTimer = null; }
}

// ── Status poll ──
function startStatusPoll() {
  _pollTimer = setInterval(loadStatus, 5000);
}

function stopStatusPoll() {
  if (_pollTimer) { clearInterval(_pollTimer); _pollTimer = null; }
}

// ── Init ──
loadStatus();
startStatusPoll();
loadReleases();

})();
