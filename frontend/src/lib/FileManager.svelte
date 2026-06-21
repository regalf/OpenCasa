<script>
  import { api } from './api.js'

  let currentPath = '/'
  let entries = []
  let error = ''
  let editing = null
  let editorContent = ''

  async function loadDir(path) {
    try {
      const res = await api.listFiles(path)
      currentPath = res.path
      entries = res.entries
      error = ''
    } catch (e) {
      error = e.message
    }
  }

  function enterDir(name) {
    loadDir(currentPath + (currentPath.endsWith('/') ? '' : '/') + name)
  }

  function goUp() {
    const p = currentPath.replace(/\/$/, '')
    const parent = p.substring(0, p.lastIndexOf('/')) || '/'
    loadDir(parent)
  }

  async function openFile(name) {
    const path = currentPath + name
    try {
      const res = await api.readFile(path)
      if (res.content != null) {
        editing = path
        editorContent = res.content
      }
    } catch (e) {
      error = e.message
    }
  }

  async function saveFile() {
    await api.writeFile(editing, editorContent)
    editing = null
    loadDir(currentPath)
  }

  async function deleteFile(name) {
    if (!confirm('Eliminare ' + name + '?')) return
    await api.deleteFile(currentPath + name)
    loadDir(currentPath)
  }

  function uploadFile() {
    const input = document.createElement('input')
    input.type = 'file'
    input.onchange = async () => {
      const file = input.files[0]
      if (!file) return
      const form = new FormData()
      form.append('file', file)
      form.append('path', currentPath + file.name)
      await fetch(api.createUploadUrl(), {
        method: 'POST',
        headers: { 'Authorization': 'Bearer ' + localStorage.getItem('token') },
        body: form,
      })
      loadDir(currentPath)
    }
    input.click()
  }

  function downloadFile(name) {
    const path = currentPath + name
    window.open('/api/v1/files/download?path=' + encodeURIComponent(path))
  }

  $: if (currentPath) loadDir(currentPath)
</script>

<div class="fm">
  <div class="toolbar">
    <button on:click={goUp}>⬆</button>
    <span class="path">{currentPath}</span>
    <button on:click={uploadFile}>Carica</button>
    <button on:click={() => {
      const name = prompt('Nome directory:')
      if (name) { api.mkdir(currentPath + name); loadDir(currentPath) }
    }}>+ Dir</button>
  </div>

  {#if editing}
    <div class="editor">
      <h3>Modifica: {editing}</h3>
      <textarea bind:value={editorContent} rows="20"></textarea>
      <div class="editor-actions">
        <button on:click={saveFile}>Salva</button>
        <button class="secondary" on:click={() => editing = null}>Annulla</button>
      </div>
    </div>
  {/if}

  <table>
    <thead>
      <tr><th>Nome</th><th>Dimensione</th><th>Data</th><th></th></tr>
    </thead>
    <tbody>
      {#each entries as e}
        <tr>
          <td>
            {#if e.is_dir}
              <a href="#" on:click|preventDefault={() => enterDir(e.name)}>
                📁 {e.name}
              </a>
            {:else}
              📄 {e.name}
            {/if}
          </td>
          <td>{e.is_dir ? '—' : e.size < 1024 ? e.size + ' B' : (e.size / 1024).toFixed(1) + ' KB'}</td>
          <td>{e.mod_time}</td>
          <td class="actions">
            {#if !e.is_dir}
              <button on:click={() => openFile(e.name)} title="Modifica">✏️</button>
              <button on:click={() => downloadFile(e.name)} title="Scarica">⬇️</button>
            {/if}
            <button on:click={() => deleteFile(e.name)} title="Elimina">🗑️</button>
          </td>
        </tr>
      {/each}
    </tbody>
  </table>
</div>

<style>
  .toolbar {
    display: flex; align-items: center; gap: 0.5rem;
    margin-bottom: 1rem; background: #1e293b; padding: 0.5rem 1rem; border-radius: 8px;
  }
  .path { flex: 1; color: #94a3b8; font-size: 0.9rem; }
  .toolbar button {
    background: #334155; border: none; color: #e2e8f0;
    padding: 0.4rem 0.8rem; border-radius: 5px; cursor: pointer;
  }
  .toolbar button:hover { background: #475569; }
  table { width: 100%; border-collapse: collapse; }
  th { text-align: left; color: #64748b; padding: 0.5rem; border-bottom: 1px solid #334155; }
  td { padding: 0.5rem; border-bottom: 1px solid #1e293b; color: #cbd5e1; }
  td a { color: #38bdf8; text-decoration: none; }
  td a:hover { text-decoration: underline; }
  .actions button {
    background: none; border: none; cursor: pointer; padding: 0.2rem;
  }
  .editor {
    background: #1e293b; padding: 1rem; border-radius: 8px; margin: 1rem 0;
  }
  .editor h3 { margin-bottom: 0.5rem; }
  .editor textarea {
    width: 100%; background: #0f172a; color: #e2e8f0;
    border: 1px solid #334155; border-radius: 6px; padding: 0.5rem;
    font-family: monospace; resize: vertical;
  }
  .editor-actions { margin-top: 0.5rem; display: flex; gap: 0.5rem; }
  .editor-actions button {
    background: #0ea5e9; border: none; color: #fff;
    padding: 0.5rem 1rem; border-radius: 5px; cursor: pointer;
  }
  .editor-actions .secondary { background: #475569; }
</style>
