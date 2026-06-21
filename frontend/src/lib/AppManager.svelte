<script>
  import { onMount } from 'svelte'
  import { api } from './api.js'

  let apps = []
  let showForm = false
  let form = { name: '', port: 8081, command: '', description: '', icon: '' }

  onMount(() => loadApps())

  async function loadApps() {
    const res = await api.getApps()
    apps = res.apps || []
  }

  async function toggleApp(app) {
    if (app.status === 'running') {
      await api.stopApp(app.id)
    } else {
      await api.startApp(app.id)
    }
    loadApps()
  }

  async function register() {
    await api.registerApp(form)
    showForm = false
    form = { name: '', port: 8081, command: '', description: '', icon: '' }
    loadApps()
  }

  async function unregister(id) {
    if (!confirm('Rimuovere app?')) return
    // DELETE /api/v1/apps/register with id
    await fetch('/api/v1/apps/register', {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json',
                 'Authorization': 'Bearer ' + localStorage.getItem('token') },
      body: JSON.stringify({ id }),
    })
    loadApps()
  }
</script>

<div class="am">
  <div class="header">
    <h1>App Installate</h1>
    <button on:click={() => showForm = !showForm}>
      {showForm ? 'Annulla' : '+ Nuova App'}
    </button>
  </div>

  {#if showForm}
    <div class="form-card">
      <h3>Registra Nuova App</h3>
      <input bind:value={form.name} placeholder="Nome app" />
      <input bind:value={form.port} type="number" placeholder="Porta" />
      <input bind:value={form.command} placeholder="Comando (es. /usr/local/bin/myapp -p 8081)" />
      <input bind:value={form.description} placeholder="Descrizione" />
      <textarea bind:value={form.icon} placeholder="Icona (base64 data: URI o URL)" rows="3"></textarea>
      <button on:click={register}>Registra</button>
    </div>
  {/if}

  <div class="app-list">
    {#each apps as app}
      <div class="app-card">
        <div class="info">
          <strong>{app.name}</strong>
          <span class="desc">{app.description}</span>
          <span class="meta">{app.command}</span>
        </div>
        <div class="controls">
          <span class="status {app.status}">{app.status}</span>
          {#if app.pid > 0}
            <span class="pid">PID {app.pid}</span>
          {/if}
          <button class="{app.status === 'running' ? 'stop' : 'start'}"
                  on:click={() => toggleApp(app)}>
            {app.status === 'running' ? 'Stop' : 'Start'}
          </button>
          {#if app.status === 'running'}
            <a href="/app/{app.id}" target="_blank" class="open-btn">Apri</a>
          {/if}
        </div>
      </div>
    {/each}
  </div>
</div>

<style>
  .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; }
  .header button { background: #0ea5e9; color: #fff; border: none; padding: 0.5rem 1rem; border-radius: 6px; cursor: pointer; }
  .form-card {
    background: #1e293b; padding: 1rem; border-radius: 10px; margin-bottom: 1rem;
    display: flex; flex-direction: column; gap: 0.5rem;
  }
  .form-card h3 { margin-bottom: 0.3rem; }
  .form-card input, .form-card textarea {
    width: 100%; padding: 0.5rem; background: #0f172a; border: 1px solid #334155;
    border-radius: 5px; color: #e2e8f0;
  }
  .form-card button { background: #22c55e; color: #fff; border: none; padding: 0.5rem; border-radius: 5px; cursor: pointer; }
  .app-list { display: flex; flex-direction: column; gap: 0.5rem; }
  .app-card {
    background: #1e293b; padding: 1rem; border-radius: 8px;
    display: flex; justify-content: space-between; align-items: center;
  }
  .info { display: flex; flex-direction: column; gap: 0.2rem; }
  .info strong { color: #e2e8f0; }
  .desc { color: #64748b; font-size: 0.85rem; }
  .meta { color: #475569; font-size: 0.75rem; font-family: monospace; }
  .controls { display: flex; align-items: center; gap: 0.5rem; }
  .status { font-size: 0.8rem; padding: 0.2rem 0.5rem; border-radius: 4px; }
  .status.running { background: #166534; color: #86efac; }
  .status.stopped { background: #450a0a; color: #fca5a5; }
  .pid { color: #64748b; font-size: 0.75rem; font-family: monospace; }
  .controls button { border: none; padding: 0.4rem 0.8rem; border-radius: 5px; cursor: pointer; }
  .start { background: #22c55e; color: #fff; }
  .stop { background: #ef4444; color: #fff; }
  .open-btn {
    background: #0ea5e9; color: #fff; padding: 0.4rem 0.8rem;
    border-radius: 5px; text-decoration: none; font-size: 0.85rem;
  }
</style>
