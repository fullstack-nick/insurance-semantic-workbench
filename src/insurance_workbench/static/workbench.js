const runPanel = document.querySelector('[data-run-id]');
if (runPanel && ['queued', 'running'].includes(runPanel.dataset.runState)) {
  const stream = new EventSource(`/api/v1/runs/${runPanel.dataset.runId}/events`);
  stream.addEventListener('progress', (event) => {
    const update = JSON.parse(event.data);
    const line = document.createElement('li');
    line.textContent = update.kind + (update.payload.name ? ` · ${update.payload.name}` : '');
    document.querySelector('#live-events').appendChild(line);
    if (['completed', 'failed', 'cancelled', 'timed_out', 'rate_limited'].includes(update.kind)) {
      stream.close(); window.location.reload();
    }
  });
  stream.onerror = () => { document.querySelector('#stream-note').textContent = 'Reconnecting to saved progress…'; };
}
const codexState = document.querySelector('#codex-state');
if (codexState) {
  fetch('/api/v1/codex').then(r => r.json()).then(value => { codexState.textContent = value.state; codexState.className = `badge ${value.state}`; })
    .catch(() => { codexState.textContent = 'unavailable'; });
}
const statusRefresh = document.querySelector('[data-refresh-until-ready]');
if (statusRefresh) {
  let busy = false;
  setInterval(async () => {
    if (busy || document.hidden) return;
    busy = true;
    try {
      const current = await (await fetch('/api/v1/snapshot')).json();
      if (current.projection_id !== statusRefresh.dataset.projection) window.location.reload();
    } finally { busy = false; }
  }, 2000);
}
