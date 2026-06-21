<script>
  import { onMount, onDestroy } from 'svelte'
  import { api } from './api.js'
  import CpuWidget from '../widgets/CpuWidget.svelte'
  import MemoryWidget from '../widgets/MemoryWidget.svelte'
  import DiskWidget from '../widgets/DiskWidget.svelte'
  import AppGrid from '../widgets/AppGrid.svelte'

  let stats = null
  let storage = null
  let apps = []
  let notifications = []
  let info = {}
  let error = ''
  let interval

  async function fetchAll() {
    try {
      const [s, st, a, n, i] = await Promise.all([
        api.getStats(), api.getStorage(), api.getApps(),
        api.getNotifications(), api.getInfo(),
      ])
      if (s.cpu) stats = s
      if (st.filesystems) storage = st
      if (a.apps) apps = a.apps
      if (n.notifications) notifications = n.notifications
      if (i.hostname) info = i
    } catch (e) {
      error = e.message
    }
  }

  onMount(() => {
    fetchAll()
    interval = setInterval(fetchAll, 5000)
  })
  onDestroy(() => clearInterval(interval))
</script>

<div class="dashboard">
  <h1>Dashboard</h1>
  {#if info.hostname}
    <p class="sysname">{info.ostype} {info.osrelease} — {info.hostname} ({info.machine})</p>
  {/if}

  <div class="grid">
    <CpuWidget data={stats?.cpu} />
    <MemoryWidget data={stats?.memory} />
    <DiskWidget data={storage} />
    <AppGrid {apps} />
  </div>

  {#if notifications.length > 0}
    <h2>Notifiche</h2>
    <div class="notifications">
      {#each notifications as n}
        <div class="notif severity-{n.severity}">
          <strong>{n.title}</strong> — {n.message}
          <span class="time">{n.timestamp}</span>
        </div>
      {/each}
    </div>
  {/if}
</div>

<style>
  .dashboard h1 { margin-bottom: 0.3rem; }
  .sysname { color: #64748b; margin-bottom: 1.5rem; font-size: 0.9rem; }
  .grid {
    display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 1rem; margin-bottom: 2rem;
  }
  h2 { margin: 1rem 0 0.5rem; }
  .notifications { display: flex; flex-direction: column; gap: 0.5rem; }
  .notif {
    background: #1e293b; padding: 0.7rem 1rem; border-radius: 8px;
    border-left: 3px solid #64748b;
  }
  .notif.severity-info { border-left-color: #0ea5e9; }
  .notif.severity-warning { border-left-color: #f59e0b; }
  .notif.severity-error { border-left-color: #ef4444; }
  .time { color: #64748b; font-size: 0.8rem; float: right; }
</style>
