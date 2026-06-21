<script>
  import { api, setToken, getToken } from './lib/api.js'
  import Login from './lib/Login.svelte'
  import Dashboard from './lib/Dashboard.svelte'
  import FileManager from './lib/FileManager.svelte'
  import AppManager from './lib/AppManager.svelte'

  let view = 'dashboard'
  let loggedIn = !!getToken()

  function handleLogin(ev) {
    loggedIn = true
    view = 'dashboard'
  }

  function handleLogout() {
    setToken(null)
    loggedIn = false
  }

  function navigate(v) {
    view = v
  }
</script>

<main class="app">
  {#if !loggedIn}
    <Login on:login={handleLogin} />
  {:else}
    <nav class="sidebar">
      <div class="brand">OpenCasa</div>
      <button class:active={view === 'dashboard'} on:click={() => navigate('dashboard')}>
        Dashboard
      </button>
      <button class:active={view === 'files'} on:click={() => navigate('files')}>
        File Manager
      </button>
      <button class:active={view === 'apps'} on:click={() => navigate('apps')}>
        App Store
      </button>
      <div class="spacer"></div>
      <button on:click={handleLogout}>Logout</button>
    </nav>
    <section class="content">
      {#if view === 'dashboard'}
        <Dashboard />
      {:else if view === 'files'}
        <FileManager />
      {:else if view === 'apps'}
        <AppManager />
      {/if}
    </section>
  {/if}
</main>

<style>
  :global(*) { margin: 0; padding: 0; box-sizing: border-box; }
  :global(body) {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: #0f172a; color: #e2e8f0; height: 100vh;
  }
  .app { display: flex; height: 100vh; }
  .sidebar {
    width: 220px; background: #1e293b; padding: 1rem;
    display: flex; flex-direction: column; gap: 0.5rem;
  }
  .sidebar .brand {
    font-size: 1.4rem; font-weight: 700; padding-bottom: 1rem;
    border-bottom: 1px solid #334155; margin-bottom: 1rem;
    color: #38bdf8;
  }
  .sidebar button {
    background: none; border: none; color: #94a3b8; padding: 0.6rem 1rem;
    text-align: left; border-radius: 6px; cursor: pointer; font-size: 0.95rem;
  }
  .sidebar button:hover { background: #334155; color: #e2e8f0; }
  .sidebar button.active { background: #0ea5e9; color: #fff; }
  .sidebar .spacer { flex: 1; }
  .content { flex: 1; padding: 1.5rem; overflow-y: auto; }
</style>
