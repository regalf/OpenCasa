<script>
  export let data = null
  $: totalGB = data ? (data.total / (1024*1024*1024)).toFixed(1) : 0
  $: usedGB = data ? (data.used / (1024*1024*1024)).toFixed(1) : 0
  $: percent = data ? (data.used / data.total * 100) : 0
</script>

<div class="widget">
  <h3>Memoria</h3>
  {#if data}
    <div class="bar-container">
      <div class="bar" style="width: {percent}%"></div>
    </div>
    <div class="details">
      <span>{usedGB} / {totalGB} GB</span>
      <span>{percent.toFixed(1)}%</span>
    </div>
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
    height: 100%; background: linear-gradient(90deg, #a78bfa, #8b5cf6);
    border-radius: 10px; transition: width 0.5s ease;
  }
  .details { display: flex; justify-content: space-between; margin-top: 0.5rem; }
  .dim { color: #64748b; }
</style>
