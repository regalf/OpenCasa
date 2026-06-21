<script>
  export let data = null
</script>

<div class="widget">
  <h3>Storage</h3>
  {#if data?.filesystems?.length}
    <table>
      <thead>
        <tr><th>Mount</th><th>Usato</th><th>Totale</th><th>%</th></tr>
      </thead>
      <tbody>
        {#each data.filesystems as fs}
          <tr>
            <td>{fs.mount}</td>
            <td>{fs.used}</td>
            <td>{fs.total}</td>
            <td>
              <div class="mini-bar">
                <div class="fill" style="width:{fs.capacity}%"></div>
              </div>
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
  {:else}
    <p class="dim">Caricamento...</p>
  {/if}
</div>

<style>
  .widget {
    background: #1e293b; padding: 1rem; border-radius: 10px;
  }
  h3 { margin-bottom: 0.8rem; color: #94a3b8; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.05em; }
  table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
  th { text-align: left; color: #64748b; padding-bottom: 0.4rem; }
  td { padding: 0.25rem 0; color: #cbd5e1; }
  .mini-bar { height: 6px; background: #334155; border-radius: 3px; width: 60px; }
  .fill { height: 100%; background: #22d3ee; border-radius: 3px; }
  .dim { color: #64748b; }
</style>
