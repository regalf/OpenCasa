<script>
  export let data = null
  $: idle = data?.idle ?? 0
  $: used = 100 - idle
</script>

<div class="widget">
  <h3>CPU</h3>
  {#if data}
    <div class="bar-container">
      <div class="bar" style="width: {used}%"></div>
    </div>
    <div class="details">
      <span>{used.toFixed(1)}% utilizzato</span>
      <span class="dim">{data.cores} core @ {data.freq_mhz} MHz</span>
    </div>
    {#if data.model}
      <p class="model">{data.model}</p>
    {/if}
  {:else}
    <p class="dim">Caricamento...</p>
  {/if}
</div>

<style>
  .widget {
    background: #1e293b; padding: 1rem; border-radius: 10px;
  }
  h3 { margin-bottom: 0.8rem; color: #94a3b8; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.05em; }
  .bar-container {
    height: 20px; background: #334155; border-radius: 10px; overflow: hidden;
  }
  .bar {
    height: 100%; background: linear-gradient(90deg, #0ea5e9, #38bdf8);
    border-radius: 10px; transition: width 0.5s ease;
  }
  .details { display: flex; justify-content: space-between; margin-top: 0.5rem; }
  .model { color: #64748b; font-size: 0.8rem; margin-top: 0.5rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .dim { color: #64748b; }
</style>
