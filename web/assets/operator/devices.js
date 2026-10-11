import { cameraFrame, fresh, displayValue, presentationReady } from './model.js';
import { request, poll } from './transport.js';
import { el, freshPill, kv, tr, ageStamp, text, showError, rawDetails } from './ui.js';
import { telemetryCard, observedDeviceText, numberText } from './telemetry.js';
export class Devices {
  constructor(safety) {
    this.safety = safety; this.state = null; this.health = null; this.metrics = null;
    this.imageBusy = false; this.preview = false; this.meta = null; this.lastFrame = null; this.displayed = null; this.pendingImage = null;
    this.image = document.getElementById('camera-image');
    this.image?.addEventListener('load', () => { this.displayed = this.pendingImage; this.pendingImage = null; this.imageBusy = false; clearTimeout(this.imageTimeout); this.renderPreview(); });
    this.image?.addEventListener('error', () => { this.pendingImage = null; this.displayed = null; this.imageBusy = false; clearTimeout(this.imageTimeout); this.lastFrame = null; text('camera-display-age', tr('Nie udało się wczytać klatki', 'Frame load failed')); });
    this.expiry = setInterval(() => { if (!document.hidden) this.renderPreview(); }, 1000);
    window.addEventListener('pagehide', () => { clearInterval(this.expiry); clearTimeout(this.imageTimeout); });
    document.getElementById('preview-toggle')?.addEventListener('click', () => { this.preview = !this.preview; this.renderPreview(); });
    document.getElementById('preview-refresh')?.addEventListener('click', () => this.fetchFrame());
    document.getElementById('preview-kind')?.addEventListener('change', () => { this.lastFrame = null; this.frame(); });
    document.getElementById('preview-url-form')?.addEventListener('submit', event => {
      event.preventDefault(); this.lastFrame = null; this.fetchFrame();
    });
    this.poller = poll(() => this.load(), { interval: 10000, onError: showError,
      onVisibility: hidden => { if (hidden) { this.preview = false; this.renderPreview(); } } });
    this.previewPoller = poll(async () => {
      if (!this.preview) return;
      this.meta = (await request('/vision/snap-info')).data; this.renderPreview();
    }, { interval: 2000, onError: error => { this.meta = null; this.renderPreview(); showError(error); } });
  }
  async fetchFrame() {
    try { this.meta = (await request('/vision/snap-info')).data; this.renderPreview(); this.frame(true); }
    catch (error) { this.meta = null; this.renderPreview(); showError(error); }
  }
  async load() {
    const target = document.getElementById('device-list');
    const [stateResult, snapResult, healthResult, metricsResult, ...resources] = await Promise.allSettled([
      request('/state'), request('/vision/snap-info'), request('/healthz'), request('/sysinfo'), ...['camera', 'mic', 'speaker', 'lcd', 'uart'].map(name => request(`/api/resource/${name}`))
    ]);
    const state = stateResult.status === 'fulfilled' ? stateResult.value.data : null;
    this.state = state;
    this.health = healthResult.status === 'fulfilled' ? healthResult.value.data : null;
    this.metrics = metricsResult.status === 'fulfilled' ? metricsResult.value.data : null;
    this.meta = snapResult.status === 'fulfilled' ? snapResult.value.data : null;
    const rows = resources.map((result, index) => {
      const name = ['camera', 'mic', 'speaker', 'lcd', 'uart'][index];
      const data = result.status === 'fulfilled' ? result.value.data : { state: 'unknown', error: result.reason.message, observed_at: null };
      const card = el('article', 'c-card'); const good = fresh(data, 10) && data.state !== 'unknown' && data.state !== 'unavailable' && !data.error;
      card.append(el('h3', '', name.toUpperCase()), freshPill(data, good ? data.state : 'unknown', good ? data.state === 'free' ? 'ok' : 'warn' : 'err'),
        kv([[tr('Źródło', 'Source'), data.source || 'unknown'], [tr('Wiek odczytu', 'Observation age'), ageStamp(data, 10)],
          [tr('Konsumenci zadań', 'Task consumers'), (data.consumers || []).join(', ') || '—'],
          [tr('Właściciele procesów', 'Process owners'), (data.holders || []).map(row => `${row.service || row.cmd || row.command || '?'} (PID ${row.pid})`).join(', ') || (good ? tr('brak', 'none') : tr('nieznani', 'unknown'))]]));
      if (name === 'lcd') card.append(el('p', 'operator-muted', tr('Ekran zamontowany bokiem. Kompensacja 270°; nie zmieniaj orientacji w panelu.', 'Display mounted sideways. Compensation 270°; preserve orientation.')));
      if (name === 'uart') card.append(el('p', 'operator-muted', tr('Jeden właściciel UART: wykonawca ruchu. Telemetria przez BUS.', 'One UART owner: motion executor. Telemetry through BUS.')));
      if (data.error) card.append(el('p', 'operator-error', data.error));
      card.append(rawDetails(data)); return card;
    });
    target?.replaceChildren(...rows);
    this.renderTelemetry();
    this.renderPreview();
  }
  renderTelemetry() {
    const target = document.getElementById('device-telemetry'); if (!target) return;
    const key = JSON.stringify([this.safety?.state?.sensor_quality, this.state?.devices, this.health, this.metrics, Math.floor(Date.now() / 1000), document.documentElement.lang]);
    if (key === this.telemetryKey) return; this.telemetryKey = key;
    const status = el('article', 'c-card'); status.append(el('h3', '', tr('Urządzenia Pi', 'Pi devices')),
      kv([[tr('Kamera', 'Camera'), observedDeviceText(this.health?.devices?.camera, 'camera', this.health)],
        ['LCD', observedDeviceText(this.health?.devices?.lcd, 'lcd', this.health)],
        [tr('Temperatura CPU', 'CPU temperature'), numberText(this.metrics?.temp_c, 1, ' °C')],
        ['CPU / RAM', `${numberText(this.metrics?.cpu_pct, 1, '%')} / ${numberText(this.metrics?.mem_pct, 1, '%')}`]]));
    target.replaceChildren(telemetryCard(this.safety?.state, this.state, this.health), status);
  }
  renderPreview() {
    text('preview-toggle', this.preview ? tr('Wyłącz odświeżanie obrazu', 'Disable image refresh') : tr('Włącz odświeżanie obrazu', 'Enable image refresh'));
    text('camera-preview-state', this.preview ? tr('Podgląd włączony w tej karcie', 'Preview enabled in this tab') : tr('Podgląd wyłączony w tej karcie', 'Preview disabled in this tab'));
    const kind = document.getElementById('preview-kind')?.value || 'raw';
    const frame = cameraFrame(this.meta, kind);
    text('camera-age', `${kind.toUpperCase()} · ${frame.timeBasis === 'file' ? tr('wiek pliku; przechwycenie nieznane · ', 'file age; capture unknown · ') : ''}${frame.age === null ? tr('wiek nieznany', 'age unknown') : `${frame.age.toFixed(1)} s`} · ${frame.fresh ? tr('świeża klatka', 'fresh frame') : tr('brak / stara klatka', 'missing / stale frame')}`);
    const displayedSource = cameraFrame(this.meta, this.displayed?.kind || kind);
    const displayed = cameraFrame({ ...this.meta, stale: this.meta?.stale === true || !displayedSource.fresh, shown: { exists: this.displayed !== null, observed_at: this.displayed?.ts } }, 'shown');
    text('camera-display-age', `${tr('Wyświetlana klatka', 'Displayed frame')}: ${this.displayed?.kind?.toUpperCase() || '—'} · ${displayed.age?.toFixed(1) ?? '—'} s${displayed.fresh ? '' : ' · unknown / stale'}`);
    this.image?.classList.toggle('operator-stale-frame', !displayed.fresh);
    this.frame();
  }
  frame(once = false) {
    if (!this.image || this.imageBusy || document.hidden || (!this.preview && !once)) return;
    const kind = document.getElementById('preview-kind').value;
    const frame = cameraFrame(this.meta, kind);
    if (!frame.fresh) return;
    const custom = document.getElementById('preview-url').value.trim();
    const defaults = { raw: '/vision/cam', proc: '/vision/edge', ssd: '/vision/ssd', obst: '/snapshots/obst_annot.jpg', tracker: '/vision/tracker' };
    let url;
    try {
      url = new URL(custom || defaults[kind], location.origin);
      if (!['http:', 'https:'].includes(url.protocol) || url.origin !== location.origin || !/^\/(camera|vision|snapshots)\//.test(url.pathname)) throw new Error('URL must be a local camera snapshot');
    } catch (error) { showError(error); return; }
    const key = `${url.pathname}:${frame.ts}`;
    if (!once && this.lastFrame === key) return;
    url.searchParams.set('t', frame.ts); this.lastFrame = key; this.imageBusy = true; this.pendingImage = { ts: frame.ts, kind, url: url.href };
    this.image.src = url.href; this.image.hidden = false;
    // Broken endpoints cannot permanently block the preview loop.
    clearTimeout(this.imageTimeout); this.imageTimeout = setTimeout(() => {
      this.image.removeAttribute('src'); this.image.hidden = true; this.imageBusy = false; this.pendingImage = null; this.displayed = null; this.lastFrame = null;
      text('camera-display-age', tr('Timeout obrazu; brak potwierdzonej klatki', 'Image timeout; no confirmed frame'));
    }, 6000);
  }
}
