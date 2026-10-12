// Isolated source modules and DOM fixtures: no network, timers or robot SDK.
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import vm from 'node:vm';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

const assets = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../web/assets/operator');
class Element {
  constructor(tag = 'div') {
    this.tagName = tag; this.children = []; this.dataset = {}; this.listeners = {};
    this.className = ''; this.nodeType = 1; this.open = false; this.value = ''; this.checked = false;
    this.classes = new Set();
    this.classList = { add: name => this.classes.add(name), toggle: (name, enabled) => enabled ? this.classes.add(name) : this.classes.delete(name) };
  }
  setAttribute(name, value) { this[name] = value; }
  append(...nodes) { this.children.push(...nodes); }
  replaceChildren(...nodes) { this.children = nodes; }
  addEventListener(name, callback) { this.listeners[name] = callback; }
  querySelectorAll(selector) {
    const result = [];
    for (const child of this.children) {
      if (!(child instanceof Element)) continue;
      if ((selector === 'details[data-system-detail]' && child.tagName === 'details' && Object.hasOwn(child.dataset, 'systemDetail'))
        || (selector === '.operator-age' && child.className.split(' ').includes('operator-age'))
        || (selector === '[data-status-max-age]' && Object.hasOwn(child.dataset, 'statusMaxAge'))) result.push(child);
      result.push(...child.querySelectorAll(selector));
    }
    return result;
  }
}
async function fixture() {
  let clock = 1000;
  const calls = [], replies = new Map(), elements = new Map();
  const body = new Element('body');
  for (const id of ['service-list', 'system-details-data', 'rescue-release', 'rescue-resource']) {
    const node = new Element(); elements.set(id, node); body.append(node);
  }
  const document = { hidden: false, documentElement: { lang: 'en' }, body,
    createElement: tag => new Element(tag), getElementById: id => elements.get(id),
    querySelectorAll: selector => body.querySelectorAll(selector), addEventListener() {}, removeEventListener() {} };
  const context = vm.createContext({ document, window: { addEventListener() {} }, console,
    Date: class extends Date { static now() { return clock * 1000; } }, AbortController,
    setTimeout: () => 1, clearTimeout() {}, setInterval: () => 1, clearInterval() {},
    fetch: async (url, options) => {
      assert.equal(options.method, 'GET', 'presentation must never mutate the robot'); calls.push(url);
      return { ok: true, status: 200, json: async () => replies.get(url) || {} };
    } });
  const modules = new Map();
  async function load(name) {
    if (modules.has(name)) return modules.get(name);
    const module = new vm.SourceTextModule(await readFile(path.join(assets, name), 'utf8'), { context, identifier: name });
    modules.set(name, module); await module.link(specifier => load(path.basename(specifier))); return module;
  }
  return { document, elements, calls, replies, advance: seconds => { clock += seconds; },
    async load(name) { const module = await load(name); await module.evaluate(); return module.namespace; } };
}
const flush = () => new Promise(resolve => setImmediate(resolve));

test('explicit unknown observation never becomes fresh through age refresh or legacy ts', async () => {
  const f = await fixture(); const ui = await f.load('ui.js');
  for (const observed_at of [null, undefined, NaN, Infinity, 0]) {
    const row = { observed_at, ts: 1000 };
    const stamp = ui.ageStamp(row), status = ui.freshPill(row, 'active', 'ok');
    f.document.body.append(stamp, status);
    assert.equal(stamp.textContent, 'age unknown'); assert.equal(status.textContent, 'unknown / stale');
    f.advance(.1); ui.refreshAges();
    assert.equal(stamp.textContent, 'age unknown'); assert.equal(status.textContent, 'unknown / stale');
    assert.equal(stamp.classes.has('operator-error'), true);
  }
});
test('legacy ts remains valid only when observed_at is absent, then ages conservatively', async () => {
  const f = await fixture(); const ui = await f.load('ui.js');
  const stamp = ui.ageStamp({ ts: 1000 }, 3), status = ui.freshPill({ ts: 1000 }, 'active', 'ok', 3);
  f.document.body.append(stamp, status); ui.refreshAges();
  assert.equal(stamp.textContent, '0.0 s'); assert.equal(status.textContent, 'Active');
  f.advance(4); ui.refreshAges();
  assert.equal(stamp.textContent, '4.0 s · stale'); assert.equal(status.textContent, 'unknown / stale');
});

test('service polling preserves operator expansion and collapsed logs by host and unit identity', async () => {
  const f = await fixture();
  const row = { host: 'pi', unit: 'rider-camera.service', lifecycle: 'on_demand', load: 'loaded', active: 'active', can_move: false, observed_at: 1000 };
  const second = { ...row, unit: 'rider-api.service' };
  f.replies.set('/api/logic/catalog', { contract_version: 2, catalog_version: 2, observed_at: 1000, features: [], units: [row, second] });
  const services = { contract_version: 2, observed_at: 1000, services: [row, second] };
  f.replies.set('/svc', services); f.replies.set('/api/services/rider-camera.service/logs?host=pi', { lines: ['fixture only'], source: 'journal', observed_at: 1000 });
  const { System } = await f.load('system.js'); const system = new System({ can: () => false }); await flush();
  const detail = key => f.document.querySelectorAll('details[data-system-detail]').find(node => node.dataset.systemDetail === key);
  detail('autostart:pi:rider-camera.service').open = true;
  detail('source:pi:rider-camera.service').open = true;
  detail('source:system').open = true;
  await system.logs(row);
  assert.equal(detail('logs:pi:rider-camera.service').open, true, 'explicit first log read is visible');
  detail('logs:pi:rider-camera.service').open = false;
  services.services = [second, row]; await system.poller.refresh();
  assert.equal(detail('autostart:pi:rider-camera.service').open, true);
  assert.equal(detail('source:pi:rider-camera.service').open, true);
  assert.equal(detail('source:system').open, true);
  assert.equal(detail('logs:pi:rider-camera.service').open, false);
  assert.equal(detail('autostart:pi:rider-api.service').open, false);
  assert.equal(f.calls.filter(url => url.includes('/logs')).length, 1, 'poll never retrieves logs automatically');
  services.services = []; system.render(); services.services = [row]; system.render();
  assert.equal(detail('autostart:pi:rider-camera.service').open, true, 'temporary missing row retains operator preference');
  assert.equal(detail('logs:pi:rider-camera.service').open, false);
});

test('cached navigation parent failures expire nested geometry without restamping its source', async () => {
  const f = await fixture(); const { Navigation } = await f.load('navigation.js'); const model = await f.load('model.js');
  const navigation = new Navigation({ can: () => false, state: null }); await flush();
  const children = { map: { observed_at: 1000, source: 'mapper.map.data', grid: [0] },
    pose: { observed_at: 1000, source: 'robot.pose', x: 0, y: 0, theta: 0 },
    path: { observed_at: 1000, source: 'navigator.path', path: [[0, 0]] } };
  for (const failure of [{ stale: true }, { offline: true }, { error: 'cache unavailable' }, { data_error: 'source invalid' },
    { data_ready: false }, { navigation_ready: false }, { quality: 'UNKNOWN' }, { quality: null }]) {
    navigation.observeSnapshot({ ...children, ...failure });
    for (const name of ['map', 'pose', 'path']) {
      assert.equal(model.presentationReady(navigation[name], 10), false, JSON.stringify(failure));
      assert.equal(navigation[name].observed_at, 1000); assert.equal(navigation[name].source, children[name].source);
    }
  }
  navigation.observeSnapshot(children);
  assert.equal(model.presentationReady(navigation.pose), true, 'new healthy envelope clears prior failure');
  navigation.observeSnapshot(null);
  assert.equal(navigation.map.observed_at, null); assert.equal(navigation.map.grid, undefined);
  assert.equal(navigation.pose.x, undefined); assert.equal(model.presentationReady(navigation.path), false);
});

test('outer proxy failures invalidate cached navigation and cannot confirm a pending task', async () => {
  const f = await fixture(); const { Navigation } = await f.load('navigation.js'); const model = await f.load('model.js');
  f.elements.set('nav-status', new Element());
  const children = { map: { observed_at: 1000, grid: [0] }, pose: { observed_at: 1000, x: 0, y: 0, theta: 0 },
    path: { observed_at: 1000, path: [[0, 0]] } };
  const status = { observed_at: 1000, state: 'EXPLORING', active: true, generation: 'g', request_id: 'r' };
  const navigation = new Navigation({ can: () => false, state: null }); await flush();
  navigation.history = [{ generation: 'g', request_id: 'r', ts: 1000, status: 'pending' }];
  for (const failure of [{ offline: true }, { stale: true }, { error: 'proxy unavailable' }, { data_error: 'source invalid' }]) {
    f.replies.set('/api/navigator/status', { navigation: children, navigator: status, ...failure }); await navigation.poller.refresh();
    assert.ok(f.elements.get('nav-status').textContent.startsWith('unknown / stale'));
    assert.equal(navigation.history[0].status, 'pending');
    for (const name of ['map', 'pose', 'path']) assert.equal(model.presentationReady(navigation[name]), false, JSON.stringify(failure));
  }
  // A fresh failed task is useful status, even when its measurements are unusable.
  f.replies.set('/api/navigator/status', { navigation: children, navigator: { ...status, state: 'FAILED', active: false }, data_ready: false });
  await navigation.poller.refresh();
  assert.ok(f.elements.get('nav-status').textContent.startsWith('FAILED'));
  assert.equal(navigation.history[0].status, 'task_observed'); assert.equal(navigation.history[0].active, false);
  assert.equal(model.presentationReady(navigation.map), true, 'task readiness does not invalidate an independently fresh cached map');
});


test('outer cache failures expire geometry and never confirm a cached request', async () => {
  const f = await fixture(); const { Navigation } = await f.load('navigation.js'); const model = await f.load('model.js');
  const navigation = new Navigation({ can: () => false, state: null }); await flush();
  const children = { map: { observed_at: 1000, source: 'mapper.map.data', grid: [0] },
    pose: { observed_at: 1000, source: 'robot.pose', x: 0, y: 0, theta: 0 },
    path: { observed_at: 1000, source: 'navigator.path', path: [[0, 0]] } };
  for (const failure of [{ stale: true }, { offline: true }, { error: 'cached source lost' }, { data_error: 'source unknown' }]) {
    f.replies.set('/api/navigator/status', { ...failure, navigation: children,
      navigator: { observed_at: 1000, state: 'FAILED', active: false, generation: 'g', request_id: 'r' } });
    navigation.history = [{ action: 'start', generation: 'g', request_id: 'r', ts: 999, status: 'pending' }];
    await navigation.poller.refresh();
    assert.equal(navigation.history[0].status, 'pending');
    for (const name of ['map', 'pose', 'path']) {
      assert.equal(model.presentationReady(navigation[name]), false);
      assert.equal(navigation[name].observed_at, 1000);
    }
  }
  navigation.observeSnapshot(children, { data_ready: false, state: 'FAILED' });
  assert.equal(model.presentationReady(navigation.pose), true, 'task readiness does not imply map quality');
});

test('provider cards use actual text and per-domain voice readiness, without starting models', async () => {
  const f = await fixture(), target = new Element(); f.elements.set('provider-runtime', target);
  f.replies.set('/api/providers/state', { observed_at: 1000, domains: {} });
  f.replies.set('/providers/capabilities', {
    text: { source: 'pc', runtime_mode: 'real', initialized: true, ready: true },
    voice: { source: 'pc', runtime_mode: 'real', initialized: true, ready: false, capabilities: { asr: { ready: false }, tts: { ready: true } } },
    vision: { source: 'demo', runtime_mode: 'mock', initialized: true, ready: true },
  });
  const { Providers } = await f.load('providers.js'); const providers = new Providers(); await flush();
  const textOf = node => [node.textContent || '', ...node.children.map(child => child instanceof Element ? textOf(child) : String(child))].join(' ');
  assert.match(textOf(target.children[0]), /pc · real · initialized=true · ready=true/);
  assert.match(textOf(target.children[1]), /demo · mock · initialized=true · ready=true/);
  assert.match(textOf(target.children[2]), /pc · real · initialized=true · ready=false/);
  f.replies.set('/providers/capabilities', { text: { initialized: false, ready: true } });
  await providers.load();
  assert.match(textOf(target.children[0]), /initialized=false · ready=false/);
  assert.ok(f.calls.includes('/providers/capabilities'));
  assert.ok(!f.calls.includes('/svc'));
});


test('cached provider health is unknown after source loss even with a healthy registry', async () => {
  const f = await fixture(), target = new Element(); f.elements.set('provider-runtime', target);
  f.replies.set('/api/providers/state', { observed_at: 1000, domains: { pc_health: { status: 'healthy', reachable: true } } });
  f.replies.set('/api/providers/health', { observed_at: 1000, pc_health: { status: 'healthy', reachable: true } });
  const { Providers } = await f.load('providers.js'); const providers = new Providers(); await flush();
  const textOf = node => [node.textContent || '', ...node.children.map(child => child instanceof Element ? textOf(child) : String(child))].join(' ');
  const healthCell = () => target.children[0].children[2].children[7].textContent;
  assert.equal(healthCell(), 'healthy');
  for (const failure of [{ offline: true }, { stale: true }, { error: 'cached source failed' }, { observed_at: null }]) {
    f.replies.set('/api/providers/health', { observed_at: 1000, pc_health: { status: 'healthy', reachable: true }, ...failure });
    await providers.load();
    assert.equal(healthCell(), 'unknown / stale');
    assert.match(textOf(target.children[0]), /health_envelope/);
  }
});

test('PC system freshness and live age retain the PC clock when Pi clock differs', async () => {
  const f = await fixture(); const model = await f.load('model.js'); const telemetry = await f.load('telemetry.js'); const ui = await f.load('ui.js');
  model.setServerClock(1040, 1000, 1000);
  assert.equal(telemetry.hostObservation({ timestamp: 1000, cpu_pct: 0 }, 'pc').current, true);
  assert.equal(telemetry.hostObservation({ timestamp: 970 }, 'pc').current, false);
  assert.equal(telemetry.hostObservation({ observed_at: 1040 }, 'pi').current, true);
  assert.equal(telemetry.hostObservation({ observed_at: null, timestamp: 1000 }, 'pc').current, false);
  const stamp = ui.ageStamp({ observed_at: 1000 }, 12, 'pc'); f.document.body.append(stamp);
  assert.equal(stamp.textContent, '0.0 s'); f.advance(2); ui.refreshAges(); assert.equal(stamp.textContent, '2.0 s');
});


test('mixed service aggregate keeps separately labelled source clocks and explicit unknown batch time', async () => {
  const f = await fixture(); const model = await f.load('model.js'); const telemetry = await f.load('telemetry.js');
  model.setServerClock(1040, 1000, 1000);
  assert.equal(telemetry.inventoryStamp({ observed_at: 1039.8 }, 'pi'), '0.2 s');
  assert.equal(telemetry.inventoryStamp({ observed_at: 999.8 }, 'pc'), '0.2 s');
  const unknown = { observed_at: null, oldest_member_observed_at: 1039.7 };
  assert.equal(telemetry.inventoryStamp(unknown, 'pi'), 'oldest row: 0.3 s');
  assert.equal(unknown.observed_at, null, 'member diagnostic never replaces source batch time');
  assert.equal(telemetry.inventoryStamp({ ...unknown, offline: true }, 'pi'), 'offline');
  assert.equal(telemetry.inventoryStamp({ observed_at: null }, 'pi'), 'source age unknown');
});


test('LCD event power keeps the original accepted-write age without claiming a current physical measurement', async () => {
  const f = await fixture(); const telemetry = await f.load('telemetry.js');
  const event = { on: false, power_known: true, source: 'lcd-renderer', power_source: 'lcd-renderer',
    power_observed_at: 10, observed_at: 1000, confirmation: 'control_write_accepted' };
  const parent = { received_at: 1000 };
  assert.equal(telemetry.observedDeviceText(event, 'lcd', parent),
    'OFF · last confirmation lcd-renderer · 990.0 s · physical measurement unverified');
  f.advance(30); parent.received_at = 1030;
  assert.equal(telemetry.observedDeviceText({ ...event, on: true }, 'lcd', parent),
    'ON · last confirmation lcd-renderer · 1020.0 s · physical measurement unverified');
  assert.equal(event.power_observed_at, 10, 'publication never renews the control-write evidence');
  for (const patch of [{ power_known: false }, { on: 'false' }, { source: '' }, { power_source: 'api_env' },
    { confirmation: 'frame_write_accepted' }, { power_observed_at: null }, { power_observed_at: NaN },
    { power_observed_at: Infinity }, { power_observed_at: 0 }, { power_observed_at: 1030.01 },
    { offline: true }, { stale: true }, { error: 'GPIO write failed' }]) {
    assert.match(telemetry.observedDeviceText({ ...event, ...patch }, 'lcd', parent), /power state unknown/);
  }
  for (const patch of [{ offline: true }, { stale: true }, { error: 'source unavailable' }, { received_at: 900 }]) {
    assert.doesNotMatch(telemetry.observedDeviceText(event, 'lcd', { ...parent, ...patch }), /^(ON|OFF)/);
  }
});

test('GPIO backlight observation reports LCD ON/OFF without requiring a prior write',async()=>{
  const f=await fixture();
  const telemetry=await f.load('telemetry.js');
  const parent={observed_at:1000,received_at:1000,source:'pi'};
  const row={power_known:true,on:false,source:'gpio',power_source:'gpio',power_observed_at:999,
    confirmation:'gpio_level_observed'};
  assert.equal(telemetry.observedDeviceText(row,'lcd',parent),'OFF');
  assert.equal(telemetry.observedDeviceText({...row,on:true},'lcd',parent),'ON');
  assert.doesNotMatch(telemetry.observedDeviceText({...row,error:'unavailable'},'lcd',parent),/^(ON|OFF)/);
});
test('Pi history renders CPU peaks and breaks the line across missing source time',async()=>{
  const f=await fixture();
  const telemetry=await f.load('telemetry.js');
  const strokes=[], moves=[], lines=[];
  const ctx={clearRect(){},strokeRect(){},beginPath(){},stroke(){strokes.push(this.strokeStyle);},
    moveTo(x,y){moves.push([x,y]);},lineTo(x,y){lines.push([x,y]);}};
  telemetry.drawHistory({width:300,height:140,getContext:()=>ctx},[10,20,30],[40,50,60],
    false,null,null,{peaks:[15,80,35],times:[1000,1001,1006]});
  assert.ok(strokes.includes('#a17fff'));
  assert.equal(moves.length,6);
  assert.equal(lines.length,3);
});
