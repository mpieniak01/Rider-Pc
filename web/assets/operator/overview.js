import { ageOf, cameraFrame, catalogKnown, fresh, presentationReady } from './model.js';
import { request, poll } from './transport.js';
import { el, text, tr, showError } from './ui.js';
import { finite, numberText, transportCurrent, measurementChannel, channelText, drawHistory, obstacleReading, observedDeviceText, hostObservation } from './telemetry.js';

const node = id => document.getElementById(id);
export function previewPreference(storage) {
  try { return storage?.getItem('rider.overview.preview') !== 'false'; }
  catch { return true; }
}
export class Overview {
  constructor(safety) {
    this.safety = safety; this.data = {}; this.frames = new Map(); this.hist = { cpu: [], mem: [], gpu: [], gpuMem: [] };
    this.preview = previewPreference(window.localStorage);
    if (node('overview-preview')) node('overview-preview').checked = this.preview;
    node('overview-preview')?.addEventListener('change', event => {
      this.preview = event.target.checked;
      try { window.localStorage?.setItem('rider.overview.preview', String(this.preview)); } catch { /* Storage is optional. */ }
      this.renderImages();
    });
    for (const [kind, id] of [['raw', 'img_cam'], ['proc', 'img_proc'], ['obst', 'img_obst'], ['tracker', 'img_tracker']]) {
      const image = node(id); if (!image) continue;
      const row = { image, observed_at: null, key: null, busy: false }; this.frames.set(kind, row);
      image.addEventListener('load', () => { row.busy = false; row.observed_at = row.pending ?? null; row.pending = null; row.failures = 0; row.retryAt = 0; clearTimeout(row.timer); this.renderImages(); });
      image.addEventListener('error', () => { row.busy = false; row.error = 'frame_load_failed'; row.key = null; row.failures = (row.failures || 0) + 1; row.retryAt = Date.now() + Math.min(30000, 5000 * 2 ** Math.min(row.failures, 3)); clearTimeout(row.timer); this.renderImages(); });
    }
    this.expiry = setInterval(() => { if (!document.hidden) { this.renderSensors(); this.renderImages(); } }, 1000);
    window.addEventListener('pagehide', () => { clearInterval(this.expiry); for (const row of this.frames.values()) clearTimeout(row.timer); });
    this.telemetryPoller = poll(() => this.loadTelemetry(), { interval: 1000, onError: showError });
    this.poller = poll(() => this.load(), { interval: 2000, onError: showError });
    this.visionPoller = poll(() => this.loadVision(), { interval: 2000, onError: showError });
    this.inventoryPoller = poll(() => this.loadInventory(), { interval: 10000, onError: showError });
    this.slowPoller = poll(() => this.loadLocal(), { interval: 10000, onError: showError });
    window.addEventListener('dashboard:langchange', () => this.render());
  }
  async load() {
    const names = ['health', 'pi'];
    const paths = ['/healthz', '/sysinfo'];
    const results = await Promise.allSettled(paths.map(path => request(path)));
    names.forEach((name, index) => { this.data[name] = results[index].status === 'fulfilled' ? results[index].value.data : null; });
    this.render();
    window.dispatchEvent(new CustomEvent('dashboard:update', { detail: { state: this.data.state, health: this.data.health, sysinfo: this.data.pi, snapInfo: this.data.snap } }));
  }
  async loadTelemetry() {
    await Promise.all([['state', '/state']].map(async ([name, path]) => {
      try { this.data[name] = (await request(path)).data; }
      catch (error) { this.data[name] = null; throw error; }
      finally { name === 'state' ? this.renderSensors() : this.renderImages(); }
    }));
  }
  cameraActive() {
    const row = this.data.state?.devices?.camera || this.data.health?.devices?.camera;
    return row && row.activity === 'on' && !row.error && !row.stale && !row.offline;
  }
  async loadVision() {
    const active = this.cameraActive();
    if (!active && this.idleVisionRead) return;
    const readings = [['snap', '/vision/snap-info']];
    if (active) readings.push(['obstacle', '/vision/obstacle']);
    for (const [name, path] of readings) {
      try { this.data[name] = (await request(path)).data; }
      catch (error) { this.data[name] = null; throw error; }
    }
    this.idleVisionRead = !active;
    if (!active) this.data.obstacle = null;
    this.render(); this.renderImages();
  }
  async loadInventory() {
    for (const [name, path] of [['metrics', '/api/app-metrics'], ['catalog', '/api/logic/catalog']]) {
      try { this.data[name] = (await request(path)).data; }
      catch (error) { this.data[name] = null; throw error; }
    }
    this.render();
  }
  async loadLocal() {
    const names = ['pc', 'services', 'live', 'mcpStats', 'mcpConfig', 'mcpTools', 'mcpHistory'];
    const paths = ['/status/system-pc', '/svc', '/health/live', '/api/mcp/stats', '/api/mcp/resources', '/api/mcp/tools', '/api/chat/pc/mcp-history?limit=6'];
    const results = await Promise.allSettled(paths.map(path => request(path)));
    names.forEach((name, index) => { this.data[name] = results[index].status === 'fulfilled' ? results[index].value.data : null; });
    this.renderLocal();
  }
  renderHost(data, prefix, host) {
    text(prefix === 'ci' ? 'ci_host' : 'pcHostInfo', host + (data?.source === 'demo' || data?.simulated === true ? ' · DEMO' : ''));
    text(prefix === 'ci' ? 'ci_cpu' : 'pcCpu', numberText(data?.cpu_pct, 1, '%'));
    text(prefix === 'ci' ? 'ci_load' : 'pcLoad', [data?.load1, data?.load5, data?.load15].map(value => numberText(value, 2)).join(' / '));
    text(prefix === 'ci' ? 'ci_mem' : 'pcMem', `${numberText(data?.mem_used_mb)} / ${numberText(data?.mem_total_mb)} MiB · ${numberText(data?.mem_pct, 1, '%')}`);
    text(prefix === 'ci' ? 'ci_disk' : 'pcDisk', `${numberText(data?.disk_used_gb)} / ${numberText(data?.disk_total_gb)} GiB · ${numberText(data?.disk_pct, 1, '%')}`);
    text(prefix === 'ci' ? 'ci_os' : 'pcOs', data?.os_release || data?.platform || '—');
    const observation = hostObservation(data, prefix === 'ci' ? 'pi' : 'pc');
    text(prefix === 'ci' ? 'pi-source-age' : 'pc-source-age', `${observation.age === null ? tr('wiek nieznany', 'age unknown') : observation.age.toFixed(1) + ' s'} · ${observation.current ? tr('odczyt aktualny', 'current observation') : 'unknown / stale'}`);
  }
  render() {
    const { state, health, pi, metrics, catalog } = this.data;
    this.renderHost(pi, 'ci', 'Rider-Pi');
    text('d_temp', numberText(pi?.temp_c, 1, ' °C'));
    text('ci_fw', state?.devices?.xgo?.fw || health?.devices?.xgo?.fw || '—');
    text('d_cam', observedDeviceText(health?.devices?.camera, 'camera', health));
    text('d_lcd', observedDeviceText(health?.devices?.lcd, 'lcd', health));
    text('h_status', !health ? 'unknown' : health.offline ? 'offline' : (health.status || 'unknown') + (transportCurrent(health) ? '' : ' · ' + tr('wiek odpowiedzi nieznany / stary', 'response age unknown / stale')));
    text('h_uptime', numberText(health?.uptime_s, 0, ' s'));
    text('h_msg', numberText(health?.bus?.last_msg_age_s, 3, ' s'));
    text('h_hb', numberText(health?.bus?.last_heartbeat_age_s, 3, ' s'));
    text('overview-connection', `PC: ${this.data.live?.status === 'alive' ? 'alive' : 'unknown'} · Pi: ${state?.offline || catalog?.offline ? 'offline' : catalogKnown(catalog) ? 'observed v2' : 'unknown'}`);
    text('overview-task-status', (catalog?.features || []).filter(task => task.requested).map(task => `${task.title || task.name}: ${task.state || 'unknown'}`).join(' · ') || tr('Brak zamówionych zadań', 'No requested tasks'));
    const obstacle = obstacleReading(state, this.data.obstacle);
    const usable = presentationReady(obstacle, 3) && typeof obstacle?.present === 'boolean';
    text('obs_present', usable ? String(obstacle.present) : 'unknown');
    text('obs_conf', numberText(obstacle?.confidence, 3)); text('obs_edge', numberText(obstacle?.edge_ratio ?? obstacle?.edge_pct, 3));
    text('obstacle-source-age', `${usable ? tr('świeży pomiar', 'fresh observation') : tr('brak / stare / zadanie wyłączone', 'missing / stale / task stopped')} · ${ageOf(obstacle)?.toFixed(1) ?? '—'} s${obstacle?.error || obstacle?.data_error ? ' · ' + (obstacle.error || obstacle.data_error) : ''}`);
    const diag = obstacle?.diag;
    text('binsLegendTxt', `LOW/HIGH: ${numberText(diag?.t_low, 3)} / ${numberText(diag?.t_high, 3)} · edge_pct: ${numberText(diag?.edge_ratio_raw ?? diag?.edge_pct_raw ?? obstacle?.edge_ratio ?? obstacle?.edge_pct, 3)} · ${usable ? tr('aktualne', 'current') : 'unknown / stale'}`);
    drawHistory(node('binsCanvas'), diag?.bins || (finite(obstacle?.edge_ratio ?? obstacle?.edge_pct) ? [obstacle.edge_ratio ?? obstacle.edge_pct] : []), [], true, diag?.t_low, diag?.t_high);
    node('binsCanvas')?.classList.toggle('operator-stale-frame', !usable);
    drawHistory(node('chart'), pi?.hist_cpu, pi?.hist_mem, false, null, null, {peaks:pi?.hist_cpu_peak,times:pi?.hist_ts});
    if (node('ci_cpu')) node('ci_cpu').title = finite(pi?.cpu_peak_pct) ? tr('Szczyt w ostatniej sekundzie: ', 'Peak in the last second: ') + numberText(pi.cpu_peak_pct, 1, '%') : '';
    node('chart')?.classList.toggle('operator-stale-frame', !transportCurrent(pi, 12) || !fresh(pi, 12));
    for (const name of ['control', 'navigator', 'voice', 'google_home', 'chat', 'face']) {
      const row = metrics?.metrics?.[name]; text(`metric_${name}`, row ? `${row.ok ?? '—'} OK / ${row.error ?? '—'} error` : '—');
    }
    text('metric_total_errors', metrics?.total_errors ?? '—');
    this.renderSensors(); this.renderImages(); this.renderLocal();
  }
  renderSensors() {
    const state = this.data.state, safety = this.safety.state;
    const rows = ['battery', 'roll', 'pitch', 'yaw'].map(name => measurementChannel(safety, state, name));
    text('d_xgo_batt', channelText(rows[0]));
    text('d_xgo_imu', rows.slice(1).every(row => row.ready) ? tr('świeże kanały SDK', 'fresh SDK channels') : tr('częściowe / stare / nieznane', 'partial / stale / unknown'));
    text('d_xgo_pose', rows.slice(1).map((row, index) => `${['roll', 'pitch', 'yaw'][index]}: ${channelText(row)}`).join('\n'));
  }
  renderImages() {
    for (const kind of ['raw', 'proc', 'ssd', 'obst', 'tracker']) {
      const row = cameraFrame(this.data.snap, kind);
      text(`age_${kind}`, `${row.timeBasis === 'file' ? tr('wiek pliku; czas przechwycenia nieznany · ', 'file age; capture time unknown · ') : ''}${row.age === null ? tr('wiek nieznany', 'age unknown') : row.age.toFixed(1) + ' s'} · ${row.fresh ? tr('świeże', 'fresh') : 'unknown / stale'}`);
    }
    const paths = { raw: '/vision/cam', proc: '/vision/edge', obst: '/snapshots/obst_annot.jpg', tracker: '/vision/tracker' };
    const labels = { raw: 'leg_cam_txt', proc: 'leg_proc_txt', obst: 'leg_obst_txt', tracker: 'leg_tracker_txt' };
    for (const [kind, row] of this.frames) {
      const frame = cameraFrame(this.data.snap, kind);
      const shown = cameraFrame({ ...this.data.snap, shown: { exists: finite(row.observed_at), observed_at: row.observed_at } }, 'shown');
      const age = (frame.timeBasis === 'file' ? tr('wiek pliku, przechwycenie nieznane · ', 'file age, capture unknown · ') : '') + (frame.age === null ? tr('wiek nieznany', 'age unknown') : frame.age.toFixed(1) + ' s');
      text(labels[kind], `${kind.toUpperCase()} · ${age} · ${frame.fresh ? tr('świeża klatka', 'fresh frame') : frame.exists ? tr('archiwalna — nie pokazuje bieżącej sytuacji', 'historical — not the current scene') : tr('brak klatki / zadanie wyłączone', 'no frame / task stopped')}${row.error ? ' · ' + row.error : ''}`);
      row.image.classList.toggle('operator-stale-frame', !shown.fresh || !frame.fresh);
      if (!this.preview || document.hidden || row.busy || Date.now() < (row.retryAt || 0) || !frame.fresh) continue;
      const key = `${kind}:${frame.ts}`; if (row.key === key) continue;
      row.key = key; row.pending = frame.ts; row.busy = true; row.error = null;
      row.image.src = `${paths[kind]}?t=${encodeURIComponent(frame.ts)}`;
      row.timer = setTimeout(() => { row.busy = false; row.error = 'frame_timeout'; row.key = null; row.retryAt = Date.now() + 10000; this.renderImages(); }, 5000);
    }
    text('camBadge', observedDeviceText(this.data.health?.devices?.camera, 'camera', this.data.health));
  }
  renderLocal() {
    const { pc, services, mcpStats, mcpConfig, mcpTools, mcpHistory } = this.data;
    this.renderHost(pc, 'pc', 'Rider-PC / WSL');
    text('pcGpuUtil', numberText(pc?.gpu_util_pct, 1, '%'));
    text('pcGpuMem', `${numberText(pc?.gpu_mem_used_mb)} / ${numberText(pc?.gpu_mem_total_mb)} MiB · ${numberText(pc?.gpu_mem_pct, 1, '%')}`);
    text('pcDistro', pc?.distribution || '—'); text('pcUptime', numberText(pc?.uptime_s, 0, ' s'));
    if (finite(pc?.timestamp) && pc.timestamp !== this.pcTs) {
      this.pcTs = pc.timestamp;
      for (const [key, value] of [['cpu', pc.cpu_pct], ['mem', pc.mem_pct], ['gpu', pc.gpu_util_pct], ['gpuMem', pc.gpu_mem_pct]]) {
        this.hist[key].push(finite(value) ? value : null); this.hist[key] = this.hist[key].slice(-60);
      }
    }
    drawHistory(node('chartPc'), this.hist.cpu, this.hist.mem); drawHistory(node('chartGpu'), this.hist.gpu, this.hist.gpuMem);
    for (const id of ['chartPc', 'chartGpu']) node(id)?.classList.toggle('operator-stale-frame', !hostObservation(pc, 'pc').current);
    const serviceRows = (services?.services || []).filter(row => row.host === 'pc');
    node('pcServiceList')?.replaceChildren(...(serviceRows.length ? serviceRows.map(row => el('p', '', `${row.label || row.unit || row.id} · ${row.kind || row.source} · ${row.offline || row.stale || row.error ? 'unknown' : row.active_state || row.active || row.state || 'unknown'}`)) : [el('p', 'operator-muted', tr('Brak skonfigurowanych jednostek systemd PC. API panelu:', 'No configured PC systemd units. Panel API:') + ' ' + (this.data.live?.status || 'unknown'))]));
    const stats = mcpStats?.stats;
    text('mcpTotalTools', stats?.total_tools ?? '—'); text('mcpInvocations', stats?.invocation_count ?? '—'); text('mcpLastTool', stats?.last_invoked_tool || '—'); text('mcpStatus', stats ? tr('rejestr API dostępny', 'API registry available') : 'unknown');
    text('mcpStandalone', mcpConfig?.resources?.config?.mcp_standalone === true ? 'true' : mcpConfig?.resources?.config?.mcp_standalone === false ? 'false' : 'unknown');
    text('mcpPort', mcpConfig?.resources?.config?.mcp_port ?? '—');
    node('mcpToolsList')?.replaceChildren(...(mcpTools?.tools?.length ? mcpTools.tools.slice(0, 20).map(tool => el('p', '', tool.name)) : [el('p', 'operator-muted', tr('Brak danych rejestru', 'No registry data'))]));
    node('mcpRecentCalls')?.replaceChildren(...(mcpHistory?.history?.length ? mcpHistory.history.slice(0, 6).map(row => el('p', '', `${row.tool || '—'} · ${row.ok === true ? 'API OK' : row.error || 'unknown'}`)) : [el('p', 'operator-muted', tr('Brak wywołań', 'No calls'))]));
  }
}
