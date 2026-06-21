<script>
  export let apps = []
</script>

<div class="widget">
  <h3>App Installate</h3>
  {#if apps.length > 0}
    <div class="grid">
      {#each apps as app}
        <a href="/app/{app.id}" class="app-card" target="_blank" rel="noreferrer">
          {#if app.icon && app.icon.startsWith('data:')}
            <img src={app.icon} alt={app.name} class="icon" />
          {:else}
            <div class="icon-placeholder">{app.name[0]}</div>
          {/if}
          <span class="name">{app.name}</span>
          <span class="status {app.status}">{app.status}</span>
        </a>
      {/each}
    </div>
  {:else}
    <p class="dim">Nessuna app registrata</p>
  {/if}
</div>

<style>
  .widget {
    background: #1e293b; padding: 1rem; border-radius: 10px;
  }
  h3 { margin-bottom: 0.8rem; color: #94a3b8; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.05em; }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(90px, 1fr)); gap: 0.6rem; }
  .app-card {
    display: flex; flex-direction: column; align-items: center;
    padding: 0.8rem 0.4rem; background: #334155; border-radius: 8px;
    text-decoration: none; color: #e2e8f0; transition: background 0.2s;
  }
  .app-card:hover { background: #475569; }
  .icon, .icon-placeholder {
    width: 36px; height: 36px; border-radius: 8px; margin-bottom: 0.3rem;
  }
  .icon-placeholder {
    background: #0ea5e9; display: flex; align-items: center; justify-content: center;
    font-weight: 700; font-size: 1.1rem;
  }
  .name { font-size: 0.75rem; text-align: center; }
  .status { font-size: 0.65rem; color: #64748b; }
  .status.running { color: #22c55e; }
  .dim { color: #64748b; }
</style>
