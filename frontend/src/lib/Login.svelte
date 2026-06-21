<script>
  import { createEventDispatcher } from 'svelte'
  import { api, setToken } from './api.js'

  const dispatch = createEventDispatcher()
  let user = '', pass = '', error = ''

  async function submit() {
    error = ''
    const res = await api.login(user, pass)
    if (res.token) {
      setToken(res.token)
      dispatch('login')
    } else {
      error = res.error || 'Login fallito'
    }
  }
</script>

<div class="login">
  <div class="card">
    <h1>OpenCasa</h1>
    <p class="subtitle">Pannello di Gestione</p>
    <form on:submit|preventDefault={submit}>
      <input bind:value={user} placeholder="Username" required />
      <input bind:value={pass} type="password" placeholder="Password" required />
      {#if error}<p class="error">{error}</p>{/if}
      <button type="submit">Accedi</button>
    </form>
  </div>
</div>

<style>
  .login {
    display: flex; align-items: center; justify-content: center;
    height: 100%; width: 100%;
  }
  .card {
    background: #1e293b; padding: 2.5rem; border-radius: 12px;
    width: 340px;
  }
  h1 { text-align: center; color: #38bdf8; margin-bottom: 0.3rem; }
  .subtitle { text-align: center; color: #64748b; margin-bottom: 1.5rem; }
  input {
    width: 100%; padding: 0.7rem; margin-bottom: 0.8rem;
    border: 1px solid #334155; border-radius: 6px;
    background: #0f172a; color: #e2e8f0; font-size: 0.95rem;
  }
  button {
    width: 100%; padding: 0.7rem; background: #0ea5e9; color: #fff;
    border: none; border-radius: 6px; font-size: 1rem; cursor: pointer;
  }
  button:hover { background: #0284c7; }
  .error { color: #f87171; margin-bottom: 0.5rem; font-size: 0.85rem; text-align: center; }
</style>
