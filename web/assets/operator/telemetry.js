import { ageOf, fresh, presentationReady } from './model.js';
import { el, kv, tr, ageStamp } from './ui.js';

export const finite = value => typeof value === 'number' && Number.isFinite(value);
export const numberText = (value, digits = 1, suffix = '') => finite(value) ? value.toFixed(digits) + suffix : '—';
export function transportCurrent(data, seconds = 8) {
  if (!data || data.offline || data.stale || data.transport_error) return false;
  if (finite(data.received_at)) {
    const age = Date.now() / 1000 - data.received_at;
    return age >= -.1 && age <= seconds;
  }
  return fresh(data, seconds);
}
export function measurementChannel(safety, state, name) {
  const channels = safety?.sensor_quality?.sensors;
  if (channels && Object.hasOwn(channels, name)) {
    const row = channels[name] || {};
    const parentReady = safety?.contract_version === 1 && fresh(safety) && !safety.offline && !safety.transport_error
      && safety.simulated !== true
      && typeof safety.instance_id === 'string' && typeof safety.generation === 'string';
    const valid = finite(row.value) && (name !== 'battery' || (row.value >= 0 && row.value <= 1));
    return { ...row, value: valid ? row.value : null,
      display_value: valid ? row.value * (name === 'battery' ? 100 : 1) : null,
      source: safety.sensor_quality.source || safety.source || 'motion-executor',
      ready: parentReady && row.ready === true && fresh(row, 2.5) && !row.error && !row.offline && valid,
      error: row.error || (!valid ? 'measurement_unknown' : !parentReady ? 'executor_source_unavailable' : null),
      unit: name === 'battery' ? '%' : tr('surowe SDK', 'raw SDK'), legacy: false };
  }
  const xgo = state?.devices?.xgo || {};
  const quality = xgo.sensor_quality?.sensors || xgo.sensor_quality;
  const channel = quality && Object.hasOwn(quality, name) ? quality[name] || {} : null;
  const value = name === 'battery' ? xgo.battery_pct : name === 'yaw' && Object.hasOwn(xgo, 'yaw_raw') ? xgo.yaw_raw : xgo[name];
  const field = name === 'battery' ? 'battery_observed_at' : name + '_observed_at';
  const observed = channel && Object.hasOwn(channel, 'observed_at') ? channel.observed_at
    : xgo.sensor_observed_at && Object.hasOwn(xgo.sensor_observed_at, name) ? xgo.sensor_observed_at[name]
    : Object.hasOwn(xgo, field) ? xgo[field]
    : name !== 'battery' && Object.hasOwn(xgo, 'imu_observed_at') ? xgo.imu_observed_at
    : Object.hasOwn(xgo, 'observed_at') ? xgo.observed_at : xgo.ts;
  const valid = finite(value) && (name !== 'battery' || (value >= 0 && value <= 100));
  const row = { ...xgo, observed_at: observed };
  return { value: valid ? value : null, display_value: valid ? value : null, observed_at: observed,
    source: channel?.source || xgo.source || 'legacy Pi', error: (channel ? channel.error : xgo.error) || (!valid ? 'measurement_unknown' : null),
    ready: state?.offline !== true && state?.stale !== true && !state?.transport_error && !xgo.offline
      && (channel ? channel.ready === true && fresh({ ...channel, observed_at: observed }, 2.5) && !channel.error && !channel.offline : presentationReady(row, 2.5)) && valid,
    unit: name === 'battery' ? '%' : name === 'yaw' && !Object.hasOwn(xgo, 'yaw_raw') ? tr('legacy zawijany', 'legacy wrapped') : tr('surowe SDK', 'raw SDK'), legacy: true };
}
export function channelText(row) {
  const value = numberText(row.display_value, row.unit === '%' ? 0 : 2, row.unit === '%' ? '%' : ' ' + row.unit);
  const age = ageOf(row);
  return `${value} · ${row.ready ? tr('świeże', 'fresh') : tr('nieznane / stare', 'unknown / stale')} · ${age === null ? tr('wiek nieznany', 'age unknown') : age.toFixed(1) + ' s'}${row.error ? ' · ' + row.error : ''}`;
}
export function telemetryCard(safety, state, health) {
  const card = el('article', 'c-card');
  card.append(el('h3', '', (state?.source === 'demo' || safety?.simulated ? 'DEMO · ' : '') + tr('Bateria i IMU — odczyty Pi', 'Battery and IMU — Pi readings')));
  const rows = ['battery', 'roll', 'pitch', 'yaw'].map(name => [name === 'battery' ? tr('Bateria', 'Battery') : name, channelText(measurementChannel(safety, state, name))]);
  card.append(kv([...rows, ['Firmware', state?.devices?.xgo?.fw || health?.devices?.xgo?.fw || '—']]),
    el('p', 'operator-muted', tr('IMU: wartości źródłowe SDK, nie pozycja robota. Jednostki i kalibracja fizyczna pozostają niepotwierdzone.', 'IMU: source SDK values, not robot position. Units and physical calibration remain unverified.')));
  return card;
}
export function hostCard(data, host) {
  if (data && !Object.hasOwn(data, 'observed_at') && !Object.hasOwn(data, 'ts') && finite(data.timestamp)) data = { ...data, observed_at: data.timestamp };
  const card = el('article', 'c-card');
  const current = transportCurrent(data, 12) && fresh(data, 12);
  card.append(el('h3', '', `System ${host.toUpperCase()}`),
    el('p', current ? 'operator-muted' : 'operator-warning', current ? tr('Odczyt aktualny', 'Current observation') : tr('Brak / stary odczyt', 'Missing / stale observation')),
    kv([
      ['CPU', numberText(data?.cpu_pct, 1, '%')],
      ['Load 1 / 5 / 15 min', [data?.load1, data?.load5, data?.load15].map(value => numberText(value, 2)).join(' / ')],
      [tr('Pamięć', 'Memory'), `${numberText(data?.mem_used_mb)} / ${numberText(data?.mem_total_mb)} MiB · ${numberText(data?.mem_pct, 1, '%')}`],
      [tr('Dysk', 'Disk'), `${numberText(data?.disk_used_gb)} / ${numberText(data?.disk_total_gb)} GiB · ${numberText(data?.disk_pct, 1, '%')}`],
      [tr('Temperatura CPU', 'CPU temperature'), numberText(data?.temp_c, 1, ' °C')],
      [tr('System', 'OS'), data?.os_release || data?.platform || '—'],
      [tr('Dystrybucja', 'Distribution'), data?.distribution || '—'],
      [tr('Wiek źródłowy', 'Source age'), ageStamp(data, 12)]
    ]));
  if (data?.error) card.append(el('p', 'operator-error', data.error));
  return card;
}
export function drawHistory(canvas, first = [], second = [], bars = false, low = null, high = null) {
  if (!canvas) return;
  const ctx = canvas.getContext('2d'); if (!ctx) return;
  const width = canvas.width, height = canvas.height, pad = 24, scale = bars ? 1 : 100;
  ctx.clearRect(0, 0, width, height); ctx.strokeStyle = '#58616d'; ctx.strokeRect(pad, 8, width - pad - 8, height - pad);
  const plot = (values, color) => {
    if (!Array.isArray(values)) return;
    const rows = values.slice(-60); ctx.strokeStyle = color; ctx.fillStyle = color; ctx.lineWidth = 2; ctx.beginPath(); let open = false;
    rows.forEach((value, index) => {
      if (!finite(value) || value < 0 || value > scale) { open = false; return; }
      const x = pad + (width - pad - 8) * index / Math.max(1, rows.length - 1);
      const y = height - pad - (height - pad - 8) * value / scale;
      if (bars) ctx.fillRect(x, y, Math.max(1, (width - pad - 8) / Math.max(1, rows.length) - 2), height - pad - y);
      else { if (open) ctx.lineTo(x, y); else ctx.moveTo(x, y); open = true; }
    }); ctx.stroke();
  };
  plot(first, '#6db3ff'); plot(second, '#ffd36d');
  if (bars) for (const [value, color] of [[low, '#8dd69d'], [high, '#ffd36d']]) {
    if (!finite(value) || value < 0 || value > 1) continue;
    const y = height - pad - (height - pad - 8) * value;
    ctx.strokeStyle = color; ctx.setLineDash([4, 3]); ctx.beginPath(); ctx.moveTo(pad, y); ctx.lineTo(width - 8, y); ctx.stroke(); ctx.setLineDash([]);
  }
}
export function obstacleReading(state, obstacle) {
  // Endpoint już łączy REST/BUS; jego odmowa nie może ustąpić staremu childowi /state.
  if (obstacle && typeof obstacle === 'object' && Object.keys(obstacle).length) return obstacle;
  const row = state?.vision?.obstacle;
  if (!row) return null;
  return state.offline || state.stale || state.transport_error
    ? { ...row, stale: true, offline: state.offline, error: state.transport_error || state.error || 'state_source_unavailable' } : row;
}
export function observedDeviceText(device, name, parent) {
  if (!device) return tr('nieznane — brak danych', 'unknown — no data');
  if (parent?.offline || parent?.stale || parent?.transport_error) return tr('nieznane — źródło stare / offline', 'unknown — source stale / offline');
  if (name === 'lcd' && device.power_known !== true) return tr('zasilanie nieznane', 'power unknown') + ` · ${device.ownership_state || 'unknown'}`;
  return (device.on === true ? 'ON' : device.on === false ? 'OFF' : tr('stan nieznany', 'state unknown'))
    + `${device.mode ? ' · ' + device.mode : ''}${finite(device.fps) ? ' · ' + numberText(device.fps, 1, ' FPS') : ''}`
    + (transportCurrent(parent) ? '' : ' · ' + tr('wiek odpowiedzi nieznany', 'response age unknown'));
}
