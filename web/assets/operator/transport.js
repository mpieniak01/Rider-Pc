export const contractAccept = 'application/vnd.rider.api+json;version=1';
const families = new Set('safety telemetry system health catalog tasks services service_graph resources frames obstacle navigation odometry calibration providers voice chat face models google_feed home api_metrics version network mcp project knowledge assistant http'.split(' ').map(name => 'rider.' + name));
const versions = new Map(['catalog', 'tasks', 'services', 'service_graph'].map(name => ['rider.' + name, 2]));
export function contractFamily(path) {
  if (['/api/status', '/api/metrics'].includes(path)) return 'rider.system';
  for (const [prefixes, name] of [
    [['/api/control', '/api/safety', '/api/motion', '/api/flags', '/api/stop', '/api/cmd', '/api/move', '/api/balance', '/api/height', '/control'], 'safety'],
    [['/face/', '/api/draw/face', '/draw/face'], 'face'], [['/api/calibration'], 'calibration'], [['/api/odometry'], 'odometry'], [['/api/navigator'], 'navigation'],
    [['/api/logic/catalog'], 'catalog'], [['/api/logic/', '/api/vision/tracking', '/api/vision/follow', '/vision/tracking', '/vision/follow'], 'tasks'],
    [['/api/services/graph'], 'service_graph'], [['/svc', '/api/services', '/api/systemd'], 'services'],
    [['/api/resource'], 'resources'], [['/vision/snap-info', '/api/vision/snap-info', '/camera/', '/snapshots/', '/api/last_frame'], 'frames'], [['/vision/obstacle', '/api/vision/obstacle'], 'obstacle'],
    [['/sysinfo', '/status/system-pc'], 'system'], [['/health', '/livez', '/readyz', '/api/bus/health'], 'health'],
    [['/api/app-metrics'], 'api_metrics'], [['/api/status/version', '/api/version'], 'version'],
    [['/api/config/network', '/api/status/network'], 'network'], [['/api/voice'], 'voice'], [['/api/chat'], 'chat'],
    [['/api/providers', '/providers', '/api/system/ai-mode', '/capabilities'], 'providers'], [['/api/models', '/api/proxy/pi'], 'models'],
    [['/api/google', '/raw/last.json'], 'google_feed'], [['/api/home'], 'home'], [['/api/mcp'], 'mcp'],
    [['/api/project'], 'project'], [['/api/knowledge'], 'knowledge'], [['/api/assistant'], 'assistant']
  ]) if (prefixes.some(prefix => path.startsWith(prefix))) return 'rider.' + name;
  return 'rider.telemetry';
}
export function unpackContract(payload, expectedFamily = null) {
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) throw new Error('invalid_json_type');
  const declared = Object.hasOwn(payload, 'data') || payload.meta && (Object.hasOwn(payload.meta, 'envelope_version') || Object.hasOwn(payload.meta, 'contract_id'));
  if (!declared) return payload;
  if (!Object.hasOwn(payload, 'meta') || !Object.hasOwn(payload, 'data')) throw new Error('invalid_contract_payload');
  const { meta } = payload;
  const data = payload.data === null && payload.ok === false && payload.error ? {} : payload.data;
  if (meta?.envelope_version !== 1 || typeof meta.contract_id !== 'string' || !families.has(meta.contract_id)
    || meta.contract_version !== (versions.get(meta.contract_id) || 1)
    || !data || typeof data !== 'object' || Array.isArray(data) || typeof payload.ok !== 'boolean') throw new Error('unsupported_contract');
  if (expectedFamily !== null && meta.contract_id !== expectedFamily) throw new Error('contract_family_mismatch');
  const result = { ...data, contract_meta: { ...meta } };
  for (const key of ['host', 'source', 'observed_at', 'server_time', 'generated_at', 'partial']) if (!Object.hasOwn(result, key)) result[key] = meta[key];
  for (const key of ['stale', 'offline']) result[key] = result[key] === true || meta[key] === true;
  result.ok = payload.ok;
  if (payload.error) { result.error = payload.error.code || payload.error.message || 'upstream_error'; result.contract_error = payload.error; }
  if (payload.operation) { result.operation = payload.operation; result.pending ??= payload.operation.status === 'pending'; result.confirmed ??= payload.operation.confirmed === true; }
  return result;
}
const reads = new Map();
// Motion permission needs a canonical catalogue before its short-lived envelope.
export async function prepareMutation() {
  const { data } = await request('/api/logic/catalog');
  const meta = data?.contract_meta;
  if (meta?.envelope_version !== 1 || meta.contract_id !== 'rider.catalog' || meta.contract_version !== 2
    || data.ok !== true || data.catalog_version !== 2 || data.stale || data.offline || data.error) {
    throw Object.assign(new Error('Unsupported Rider contract; read only'), { status: 409 });
  }
}
export function request(path, options = {}) {
  const method = options.method || 'GET';
  if (method === 'GET' && reads.has(path)) return reads.get(path);
  const flight = performRequest(path, options);
  if (method === 'GET') {
    reads.set(path, flight);
    flight.then(() => reads.delete(path), () => reads.delete(path));
  }
  return flight;
}
async function performRequest(path, { method = 'GET', body, timeout = 6000 } = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);
  const sentAt = Date.now() / 1000;
  try {
    const response = await fetch(path, { method, cache: 'no-store', signal: controller.signal,
      headers: { Accept: contractAccept, ...(body === undefined ? {} : { 'Content-Type': 'application/json' }) },
      body: body === undefined ? undefined : JSON.stringify(body) });
    const payload = await response.json();
    const data = unpackContract(payload, !response.ok && payload?.meta?.contract_id === 'rider.http' ? 'rider.http' : contractFamily(path));
    if (!response.ok) throw Object.assign(new Error(data.error || data.detail || data.result?.error || `HTTP ${response.status}`), { data, status: response.status });
    return { data, meta: payload?.meta ?? null, canonical: payload?.meta?.envelope_version === 1,
      status: response.status, sent_at: sentAt, received_at: Date.now() / 1000 };
  } finally { clearTimeout(timer); }
}
// One flight per poller, bounded timeout, bounded backoff, hidden tabs sleep.
export function poll(load, { interval = 2000, onError = () => {}, onVisibility = () => {} } = {}) {
  let timer, busy = false, stopped = false, failures = 0;
  const schedule = () => {
    clearTimeout(timer);
    if (!stopped && !document.hidden) timer = setTimeout(run, Math.min(30000, interval * 2 ** failures));
  };
  async function run() {
    if (busy || stopped || document.hidden) return;
    busy = true;
    try { await load(); failures = 0; }
    catch (error) { failures = Math.min(4, failures + 1); onError(error); }
    finally { busy = false; schedule(); }
  }
  function visibility() {
    clearTimeout(timer);
    onVisibility(document.hidden);
    if (!document.hidden) run();
  }
  document.addEventListener('visibilitychange', visibility);
  run();
  return { refresh: run, stop() { stopped = true; clearTimeout(timer); document.removeEventListener('visibilitychange', visibility); } };
}
export function events(onEvent, onError = () => {}) {
  let stream, timer, stopped = false, failures = 0, cursor = null;
  function close() { stream?.close(); stream = null; clearTimeout(timer); }
  function open() {
    close();
    if (stopped || document.hidden || typeof EventSource === 'undefined') return;
    stream = new EventSource('/events' + (cursor === null ? '' : '?after=' + encodeURIComponent(cursor)));
    stream.onmessage = event => {
      try { const value = JSON.parse(event.data); if (Number.isInteger(value.event_id)) cursor = value.event_id; onEvent(value); failures = 0; }
      catch (error) { onError(error); }
    };
    stream.onerror = () => {
      close(); onError(new Error('SSE disconnected'));
      timer = setTimeout(open, Math.min(30000, 2000 * 2 ** Math.min(failures++, 4)));
    };
  }
  function visibility() { document.hidden ? close() : open(); }
  document.addEventListener('visibilitychange', visibility);
  open();
  return () => { stopped = true; close(); document.removeEventListener('visibilitychange', visibility); };
}
