const TESTS = [
  {id: 'network-client', label: 'network:client', desc: 'Make an outbound HTTPS request to httpbin.org'},
  {id: 'network-server', label: 'network:server', desc: 'Bind a TCP socket to a local port'},
  {id: 'files-read', label: 'files:read', desc: 'Read a file from opencasa\'s home directory'},
  {id: 'files-write', label: 'files:write', desc: 'Create and delete a test file in home'},
  {id: 'system-exec', label: 'system:exec', desc: 'Run `id -un` via subprocess'},
  {id: 'system-monitor', label: 'system:monitor', desc: 'Read platform info and /proc stats'},
  {id: 'files-read-blocked', label: 'unveil', desc: 'Attempt to read /etc/shadow or /root (should fail with unveil)'},
];

const state = {running: false, results: {}};

function $(id) { return document.getElementById(id); }

async function runTest(test) {
  const card = $(test.id);
  if (card) card.className = 'test-card running';
  try {
    const res = await fetch('/api/test/' + test.id);
    const data = await res.json();
    state.results[test.id] = data;
    renderCard(test, data);
  } catch(e) {
    state.results[test.id] = {ok: false, detail: e.message};
    renderCard(test, state.results[test.id]);
  }
}

function renderCard(test, data) {
  const card = $(test.id);
  if (!card) return;
  card.className = 'test-card ' + (data.ok ? 'pass' : 'fail');
  card.querySelector('.result-badge').textContent = data.ok ? 'PASS' : 'FAIL';
  card.querySelector('.result-detail').textContent = data.detail || '';
}

async function runAll() {
  if (state.running) return;
  state.running = true;
  $('btn-run-all').disabled = true;
  $('btn-run-all').textContent = 'Running...';
  state.results = {};
  for (const t of TESTS) {
    await runTest(t);
  }
  state.running = false;
  $('btn-run-all').disabled = false;
  $('btn-run-all').textContent = 'Run All Tests';
}

function init() {
  const main = $('results');
  main.innerHTML = TESTS.map(t => `
    <div id="${t.id}" class="test-card">
      <div class="test-header">
        <span class="perm-badge">${t.label}</span>
        <span class="result-badge">—</span>
      </div>
      <p class="test-desc">${t.desc}</p>
      <pre class="result-detail"></pre>
      <button class="btn-test" onclick="runTest(TESTS.find(x=>x.id==='${t.id}'))">Test</button>
    </div>
  `).join('');
}

document.addEventListener('DOMContentLoaded', init);
