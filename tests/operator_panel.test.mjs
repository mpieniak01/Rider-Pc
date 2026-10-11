// Runs in Node's isolated VM. fetch is fixture-only; no socket or SDK exists.
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import vm from 'node:vm';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

const assets = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../web/assets/operator');
const model = await import(`data:text/javascript;base64,${Buffer.from(await readFile(path.join(assets, 'model.js'))).toString('base64')}`);
const instant = Date.now() / 1000;
const capability = { available: true, stop_verified: true };
const armed = (observedAt = Date.now() / 1000) => ({ contract_version: 1, state: 'ARMED', generation: 'fixture-generation', owner: 'manual',
  ready: true, hardware_ready: true, can_move: true, read_only: false, observed_at: observedAt, lease_remaining_s: 10, last_seq: 4,
  capabilities: { move: capability, turn: capability, height: { available: false, stop_verified: false, verification: 'manual_characterization_required' } } });
const disarmed = (observedAt = Date.now() / 1000) => ({ ...armed(observedAt), state: 'DISARMED', owner: null, can_move: false, read_only: true });

test('movement requires version, fresh observation, state, owner, lease and stop capability', () => {
  const state = armed(instant);
  assert.equal(model.authorized(state, 'manual', 'move', instant), true);
  for (const patch of [{ contract_version: 0 }, { observed_at: instant - 4 }, { observed_at: null },
    { state: 'DISARMED' }, { ready: false }, { hardware_ready: false }, { can_move: false }, { read_only: true },
    { owner: 'navigation' }, { lease_remaining_s: 0 }, { generation: '' },
    { capabilities: { move: { available: true, stop_verified: false } } }]) {
    assert.equal(model.authorized({ ...state, ...patch }, 'manual', 'move', instant), false, JSON.stringify(patch));
  }
  assert.equal(model.authorized(state, 'manual', 'height', instant), false);
});
test('DISARMED read_only is a valid known contract for explicit preparation', () => {
  assert.equal(model.safetyKnown(disarmed()), true);
  assert.equal(model.authorized(disarmed(), 'manual'), false);
});
test('zero is a measurement; null and stale frame timestamps remain unknown', () => {
  assert.equal(model.displayValue(0, '%'), '0%');
  assert.equal(model.displayValue(null), '—');
  assert.equal(model.cameraFrame({ raw: { exists: true, mtime: instant - 20 } }, 'raw', instant).fresh, false);
  assert.equal(model.cameraFrame({ raw: { exists: true, mtime: null } }, 'raw', instant).age, null);
});
test('old catalog and moving owner mismatch cannot start a task', () => {
  const task = { installed: true, observed_at: instant, state: 'stopped', can_move: true, motion_owner: 'navigation' };
  const catalog = { contract_version: 2, catalog_version: 2, observed_at: instant, features: [task], units: [] };
  assert.equal(model.taskCanStart(task, catalog, armed(instant), instant), false);
  assert.equal(model.taskCanStart(task, { ...catalog, contract_version: 1 }, { ...armed(instant), owner: 'navigation' }, instant), false);
  assert.equal(model.taskCanStart(task, catalog, { ...armed(instant), owner: 'navigation' }, instant), true);
});
test('ACK matches action, source, sequence, request and send time; accepted is not execution', () => {
  const command = { request_id: 'fixture', action: 'move', source: 'manual', seq: 5 };
  const ack = { ...command, observed_at: instant, status: 'executed' };
  assert.equal(model.matchingAck(ack, command, instant), true);
  for (const patch of [{ observed_at: instant - .1 }, { status: 'accepted' }, { action: 'stop' }, { seq: 4 }, { source: 'navigation' }]) {
    assert.equal(model.matchingAck({ ...ack, ...patch }, command, instant), false);
  }
});
test('confirmed HTTP ACK uses backend identity confirmation; STOP null sequence is equivalent to absent', () => {
  const command = { request_id: 'stop-fixture', action: 'stop', source: 'manual' };
  const ack = { ...command, seq: null, observed_at: instant - 1, status: 'executed' };
  assert.equal(model.matchingAck(ack, command, instant), false);
  assert.equal(model.matchingAck(ack, command, instant, true), true);
  assert.equal(model.matchingAck({ ...ack, request_id: 'another-request' }, command, instant, true), false);
});
test('server clock bounds tolerate skew without future commands or understating observation age', () => {
  const wall = Date.now() / 1000;
  assert.equal(model.setServerClock(wall + 20, wall - .3, wall), true);
  assert.ok(model.commandSeconds() <= wall + 20.1);
  assert.ok(model.nowSeconds() >= wall + 20.3);
  assert.equal(model.setServerClock(wall + 20, wall - .51, wall), false);
  assert.equal(model.setServerClock(null, wall, wall), false);
  model.setServerClock(Date.now() / 1000, Date.now() / 1000, Date.now() / 1000);
});
test('map world coordinates use mapper additive origin and preserve zero', () => {
  assert.deepEqual(model.gridPoint({ origin_x: 5, origin_y: 3, resolution_m: .1 }, { x: 0, y: 0 }), [50, 30]);
  assert.equal(model.gridPoint({ origin_x: null, origin_y: 3, resolution_m: .1 }, [0, 0]), null);
});

class Element {
  constructor(id = '') { this.id = id; this.listeners = {}; this.value = ''; this.checked = false; this.disabled = false; this.dataset = {}; this.children = []; }
  addEventListener(name, action) { this.listeners[name] = action; }
  append(...values) { this.children.push(...values); }
  replaceChildren(...values) { this.children = values; }
  closest(selector) { return this.editing && selector.includes('input') ? this : null; }
}
async function fixture(initial = disarmed(), { interactive = true } = {}) {
  const elements = new Map(['arm', 'clear-estop', 'disarm', 'estop', 'operator-plan', 'operator-consent', 'control-owner', 'lease',
    'duration', 'speed', 'yaw-speed', 'request-history', 'safety-state', 'safety-owner', 'safety-reason', 'safety-lease', 'operator-message'].map(id => [id, new Element(id)]));
  elements.get('control-owner').value = 'manual'; elements.get('lease').value = '10'; elements.get('duration').value = '.1';
  elements.get('speed').value = '.1'; elements.get('yaw-speed').value = '.18';
  const listeners = {}, timers = new Map(), calls = [], replies = new Map();
  let timerId = 0, current = initial;
  const document = { hidden: false, documentElement: { lang: 'pl' }, body: { dataset: { page: 'control' } },
    getElementById: id => elements.get(id), querySelector: () => null, querySelectorAll: () => [], createElement: () => new Element(),
    addEventListener: (name, action) => { listeners[name] = action; }, removeEventListener() {} };
  const context = vm.createContext({ document, window: { addEventListener() {} }, console,
    Date, Math, Number, String, Boolean, JSON, Map, Set, Error, AbortController,
    setTimeout: callback => { timers.set(++timerId, callback); return timerId; }, clearTimeout: id => timers.delete(id),
    setInterval: callback => { timers.set(++timerId, callback); return timerId; }, clearInterval: id => timers.delete(id),
    fetch: async (url, options) => {
      calls.push({ url, ...options, body: options.body ? JSON.parse(options.body) : undefined });
      if (replies.has(url)) { const reply = replies.get(url); return { ok: true, status: reply.status, json: async () => reply.data }; }
      return { ok: true, status: options.method === 'POST' ? 202 : 200,
        json: async () => {
          const now = Date.now() / 1000;
          if (options.method === 'POST') return { pending: true, confirmed: false };
          const catalog = url === '/api/logic/catalog';
          return { ok: true, error: null, operation: null, meta: { envelope_version: 1, contract_id: catalog ? 'rider.catalog' : 'rider.safety', contract_version: catalog ? 2 : 1, observed_at: now, server_time: now, stale: false, offline: false },
            data: catalog ? { contract_version: 2, catalog_version: 2, features: [], units: [], api_envelope_versions: [1], observed_at: now } : { safety: current, server_time: now } };
        } };
    } });
  const modules = new Map();
  async function load(name) {
    if (modules.has(name)) return modules.get(name);
    const source = await readFile(path.join(assets, name), 'utf8');
    const module = new vm.SourceTextModule(source, { context, identifier: name }); modules.set(name, module);
    await module.link(specifier => load(path.basename(specifier)));
    return module;
  }
  const module = await load('safety.js'); await module.evaluate();
  const panel = new module.namespace.SafetyPanel(() => {}, { interactive });
  await new Promise(resolve => setImmediate(resolve));
  return { panel, elements, calls, listeners, document, timers, setReply(url, data, status = 200) { replies.set(url, { data, status }); }, async load(name) { const module = await load(name); await module.evaluate(); return module.namespace; }, setState(value) { current = value; panel.update(value); } };
}

test('opening control issues GET only and permits explicit ARM from known DISARMED', async () => {
  const f = await fixture();
  assert.ok(f.calls.length > 0);
  assert.ok(f.calls.every(call => call.method === 'GET'));
  assert.equal(f.elements.get('arm').disabled, true, 'unprepared form cannot arm');
  f.elements.get('operator-plan').value = 'Isolated prepared fixture';
  f.elements.get('operator-consent').checked = true; f.panel.render();
  assert.equal(f.elements.get('arm').disabled, false);
  assert.equal(f.elements.get('clear-estop').disabled, true);
});
test('typing, select, repeated key and modifier do not issue movement', async () => {
  const f = await fixture(armed());
  const input = new Element(); input.editing = true;
  for (const code of ['KeyW', 'ArrowLeft', 'Space']) f.panel.key({ code, target: input, preventDefault() { throw new Error('typing intercepted'); } });
  f.panel.key({ code: 'KeyW', target: new Element(), repeat: true });
  f.panel.key({ code: 'KeyW', target: new Element(), ctrlKey: true });
  assert.equal(f.calls.filter(call => call.method === 'POST').length, 0);
});
test('wrong owner, stale contract and non-control view do not issue movement', async () => {
  const f = await fixture({ ...armed(), owner: 'navigation' });
  f.panel.key({ code: 'KeyW', target: new Element() });
  f.setState({ ...armed(), observed_at: Date.now() / 1000 - 4 }); f.panel.move('forward');
  f.setState(armed()); f.document.body.dataset.page = 'view'; f.panel.key({ code: 'KeyW', target: new Element() });
  assert.equal(f.calls.filter(call => call.method === 'POST').length, 0);
});
test('explicit arm carries one fresh envelope, plan and consent; never auto arms', async () => {
  const f = await fixture();
  f.elements.get('operator-plan').value = 'Przestrzeń wolna, kabel zabezpieczony, impuls 0.1 s.';
  f.elements.get('operator-consent').checked = true;
  await f.panel.arm('arm');
  const commands = f.calls.filter(call => call.method === 'POST'); assert.equal(commands.length, 1);
  const body = commands[0].body;
  assert.equal(commands[0].url, '/api/safety'); assert.equal(body.action, 'arm');
  assert.equal(body.generation, 'fixture-generation'); assert.equal(body.seq, 5); assert.equal(body.ttl_ms, 500);
  assert.equal(body.operator_consent, true); assert.ok(body.operator_plan); assert.ok(body.ts > instant - 1);
  assert.equal(f.elements.get('operator-consent').checked, false);
});
test('202 remains pending until exact terminal ACK; stale/accepted ACK cannot turn green', async () => {
  const f = await fixture(armed()); await f.panel.send('move', { vx: .1, yaw: 0, duration: .1 });
  const entry = f.panel.history[0]; assert.equal(entry.status, 'pending');
  f.panel.ack({ ...entry.command, observed_at: entry.submittedAt, status: 'accepted' }); assert.equal(entry.status, 'pending');
  f.panel.ack({ ...entry.command, observed_at: entry.submittedAt - 1, status: 'executed' }); assert.equal(entry.status, 'pending');
  f.panel.ack({ ...entry.command, observed_at: entry.submittedAt, status: 'executed', physical_completion: 'unverified' });
  assert.equal(entry.status, 'executed'); assert.equal(entry.ack.physical_completion, 'unverified');
});
test('STOP works without safety metadata while disconnected', async () => {
  const f = await fixture(null); await f.panel.send('stop');
  const command = f.calls.find(call => call.method === 'POST').body;
  assert.equal(command.action, 'stop'); assert.equal(command.generation, undefined); assert.equal(command.seq, undefined);
});
test('focus/connection loss sends STOP and immediately removes authority', async () => {
  const f = await fixture(armed()); f.panel.suspend();
  assert.equal(f.panel.state, null); assert.equal(f.panel.can(), false);
  assert.equal(f.calls.find(call => call.method === 'POST').body.action, 'stop');
  f.setState(armed()); assert.equal(f.panel.can(), false, 'same generation must not recover on reconnect');
});
test('explicit STOP immediately removes authority before a response, with no implicit rearm', async () => {
  const f = await fixture(armed()); await f.panel.send('stop');
  assert.equal(f.panel.can(), false);
  await assert.rejects(f.panel.send('move', { vx: .1, yaw: 0, duration: .1 }));
  assert.equal(f.calls.filter(call => call.method === 'POST').length, 1);
});
test('hardware fault prevents ARM although the state is known DISARMED', async () => {
  const f = await fixture({ ...disarmed(), hardware_ready: false });
  f.elements.get('operator-plan').value = 'Prepared fixture'; f.elements.get('operator-consent').checked = true;
  assert.equal(f.elements.get('arm').disabled, true); await f.panel.arm('arm');
  assert.equal(f.calls.filter(call => call.method === 'POST').length, 0);
});
test('navigation remains passive even with valid ARMED permission; no start or return-home POST', async () => {
  const ui = await fixture(armed()); ui.document.body.dataset.page = 'navigation';
  const { Navigation } = await ui.load('navigation.js');
  const nav = new Navigation(ui.panel);
  await new Promise(resolve => setImmediate(resolve));
  const before = ui.calls.length;
  await nav.command('start'); await nav.command('return_home');
  assert.equal(ui.calls.slice(before).some(row => row.method === 'POST'), false);
});

test('poll never overlaps and waits while the page is hidden', async () => {
  const source = await readFile(path.join(assets, 'transport.js'), 'utf8');
  let resolve, loads = 0; const timers = new Map(); const document = { hidden: false, addEventListener() {}, removeEventListener() {} };
  const context = vm.createContext({ document, Date, AbortController, setTimeout: action => { timers.set(timers.size + 1, action); return timers.size; }, clearTimeout: id => timers.delete(id) });
  const module = new vm.SourceTextModule(source, { context }); await module.link(() => {}); await module.evaluate();
  const poller = module.namespace.poll(() => { loads++; return new Promise(done => { resolve = done; }); });
  await poller.refresh(); assert.equal(loads, 1); resolve(); await new Promise(done => setImmediate(done));
  document.hidden = true; await poller.refresh(); assert.equal(loads, 1); poller.stop();
});

test('unknown task can_move and offline catalog refuse Start', () => {
  const task = { installed: true, observed_at: instant, state: 'stopped', can_move: false };
  const catalog = { contract_version: 2, catalog_version: 2, observed_at: instant, features: [task], units: [] };
  assert.equal(model.taskCanStart(task, catalog, disarmed(instant), instant), true);
  for (const can_move of [undefined, null, 0, 'false']) assert.equal(model.taskCanStart({ ...task, can_move }, catalog, disarmed(instant), instant), false);
  assert.equal(model.taskCanStart(task, { ...catalog, offline: true }, disarmed(instant), instant), false);
});
test('terminal ACK from a previous generation never confirms a new command', () => {
  const command = { request_id: 'reused-request', action: 'move', source: 'manual', seq: 5, generation: 'new' };
  const ack = { ...command, command_generation: 'old', observed_at: instant, status: 'executed' };
  assert.equal(model.matchingAck(ack, command, instant, true), false);
  assert.equal(model.matchingAck({ ...ack, command_generation: 'new' }, command, instant, true), true);
});
test('system actions use host/unit identity, advertised capabilities and distinct autostart', () => {
  const row = { host: 'pc', unit: 'same.service', source: 'systemd', installed: true, load: 'loaded', observed_at: instant, can_move: false };
  assert.equal(model.serviceActionAllowed(row, 'start', null, disarmed(instant), instant), true);
  assert.equal(model.serviceActionAllowed({ ...row, can_move: null }, 'start', null, disarmed(instant), instant), false);
  assert.equal(model.serviceActionAllowed({ ...row, source: 'application', kind: 'application_provider' }, 'stop', null, disarmed(instant), instant), false);
  assert.equal(model.serviceActionAllowed({ ...row, offline: true }, 'stop', null, disarmed(instant), instant), false);
  const remote = { ...row, host: 'pi', contract_version: 2, actions: ['start','stop','restart','enable','disable'], can_move: true, motion_owner: 'manual', lifecycle: 'on-demand' };
  const catalog = { contract_version: 2, catalog_version: 2, observed_at: instant, features: [], units: [] };
  assert.equal(model.serviceActionAllowed(remote, 'start', catalog, disarmed(instant), instant), false);
  assert.equal(model.serviceActionAllowed(remote, 'start', catalog, armed(instant), instant), true);
  assert.equal(model.serviceActionAllowed(remote, 'enable', catalog, armed(instant), instant), false);
  assert.equal(model.serviceActionAllowed(remote, 'stop', catalog, disarmed(instant), instant), true);
});


test('invalid pulses are rejected before any transport or sequence allocation', async () => {
  const f = await fixture(armed()), seq = f.panel.seq;
  for (const patch of [{ vx: NaN }, { yaw: Infinity }, { duration: .3 }, { vx: 2 }, { duration: 0 }])
    await assert.rejects(f.panel.send('move', { vx: .1, yaw: 0, duration: .1, ...patch }));
  f.elements.get('speed').value = ''; f.panel.move('forward');
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(f.calls.filter(call => call.method === 'POST').length, 0);
  assert.equal(f.panel.seq, seq);
});
test('offline or stale camera metadata never confirms a fresh producer', () => {
  const meta = { raw: { exists: true, mtime: instant } };
  for (const patch of [{ offline: true }, { stale: true }, { error: 'offline' }])
    assert.equal(model.cameraFrame({ ...meta, ...patch }, 'raw', instant).fresh, false);
  assert.equal(model.cameraFrame({ raw: { ...meta.raw, stale: true } }, 'raw', instant).fresh, false);
});
test('HTTP 200 task activation without domain ready does not permit chat continuation', async () => {
  const f = await fixture();
  for (const id of ['chat-provider', 'chat-status']) f.elements.set(id, new Element(id));
  const task = { name: 'provider-domain', option_kind: 'provider', option_schema: { choices: [{ value: 'text' }] },
    installed: true, can_move: false, requested: false, ready: false, state: 'stopped', observed_at: Date.now() / 1000 };
  const tasks = { catalog: { contract_version: 2, catalog_version: 2, units: [], features: [task], observed_at: Date.now() / 1000 },
    options: new Map(), safety: f.panel, poller: { refresh() {} } };
  const { Chat } = await f.load('chat.js'), chat = new Chat(tasks);
  f.setReply('/api/logic/feature/provider-domain', { ok: true, result: { task: { ...task, ready: false, state: 'starting', options: { domain: 'text' } } } });
  await assert.rejects(chat.prepareDomain('provider', 'text'), /pending|oczekuje/);
  f.setReply('/api/logic/feature/provider-domain', { ok: true, result: { task: { ...task, ready: true, state: 'ready', options: { domain: 'vision' } } } });
  await assert.rejects(chat.prepareDomain('provider', 'text'), /pending|oczekuje/);
  f.setReply('/api/logic/feature/provider-domain', { ok: true, result: { task: { ...task, ready: true, state: 'ready', options: { domain: 'text' } } } });
  await chat.prepareDomain('provider', 'text');
  assert.equal(f.calls.filter(call => call.url === '/api/chat/send').length, 0);
  assert.ok(f.calls.filter(call => call.method === 'POST').every(call => call.body.options.domain === 'text'));
});

test('ARM lease is finite and bounded before allocating an operator envelope', async () => {
  const f = await fixture(), seq = f.panel.seq;
  for (const lease_s of [NaN, Infinity, 0, -1, 31])
    await assert.rejects(f.panel.send('arm', { operator_consent: true, operator_plan: 'Fixture', owner: 'manual', lease_s }, '/api/safety'));
  assert.equal(f.calls.filter(call => call.method === 'POST').length, 0);
  assert.equal(f.panel.seq, seq);
});

test('navigation measurement usability does not hide a fresh failed task status', () => {
  const row = { observed_at: Date.now() / 1000, quality: 'measured' };
  assert.equal(model.presentationReady(row), true);
  for (const flags of [{ stale: true }, { offline: true }, { error: 'sensor failed' },
    { data_ready: false }, { navigation_ready: false }, { data_error: 'not calibrated' },
    { quality: 'unknown' }, { quality: 'error' }, { quality: null }, { quality: 'UNKNOWN' }]) {
    assert.equal(model.presentationReady({ ...row, ...flags }), false, JSON.stringify(flags));
  }
  const failed = { ...row, state: 'FAILED', active: false, data_ready: false };
  assert.equal(model.fresh(failed), true);
  assert.equal(model.presentationReady(failed), false);
});
test('navigation normalization preserves source time and expires unknown packets', () => {
  const observed = Date.now() / 1000, previous = { x: 0, y: 0, theta: 0, observed_at: observed };
  assert.equal(model.navigationObservation({ x: 1, observed_at: observed - 1 }, previous), previous);
  const changed = model.navigationObservation({ ...previous, quality: 'unknown', data_ready: false }, previous);
  assert.equal(changed.observed_at, observed);
  const failure = model.navigationObservation({ error: 'lost', observed_at: observed - 1 }, previous);
  assert.equal(failure.error, 'lost');
  assert.equal(model.presentationReady(failure), false);
  assert.equal(model.presentationReady(changed), false);
  for (const packet of [null, 'bad', [], { error: 'lost' }, { observed_at: null, ts: observed }]) {
    const unknown = model.navigationObservation(packet, previous);
    assert.equal(unknown.observed_at, null);
    assert.equal(unknown.x, undefined);
    assert.equal(model.presentationReady(unknown), false);
  }
});
test('navigation quality changes at the same timestamp redraw and unknown events expire geometry', async () => {
  const f = await fixture(), paints = [];
  for (const id of ['nav-strategy', 'nav-speed', 'nav-turn', 'nav-start', 'nav-return_home', 'nav-stop', 'nav-config',
    'map-age', 'pose-age', 'path-age', 'nav-status']) f.elements.set(id, new Element(id));
  const context = { globalAlpha: 1, fillStyle: '', fillRect() { paints.push([this.fillStyle, this.globalAlpha]); },
    save() {}, restore() {}, translate() {}, rotate() {}, beginPath() {}, moveTo() {}, lineTo() {}, stroke() {}, arc() {}, fill() {} };
  const canvas = new Element('map-canvas'); canvas.clientWidth = 600; canvas.getContext = () => context;
  f.elements.set('map-canvas', canvas);
  const ts = Date.now() / 1000;
  const map = { width_cells: 2, height_cells: 1, grid: [0,255], resolution_m: .1, origin_x: 0, origin_y: 0,
    observed_at: ts, quality: 'measured' };
  f.setReply('/api/navigator/status', { observed_at: ts, state: 'IDLE', active: false, data_ready: false,
    navigation: { map, pose: null, path: null } });
  const { Navigation } = await f.load('navigation.js'), navigation = new Navigation(f.panel);
  await new Promise(resolve => setImmediate(resolve));
  assert.ok(f.elements.get('nav-status').textContent.includes('IDLE'));
  assert.equal(model.presentationReady(navigation.map), true);
  const key = navigation.drawKey, before = paints.length;
  navigation.event({ topic: 'mapper.map.data', data: { ...map, data_ready: false, quality: 'unknown' } });
  assert.notEqual(navigation.drawKey, key);
  assert.ok(paints.length > before);
  assert.equal(paints.at(-1)[1], .45);
  assert.ok(f.elements.get('map-age').textContent.includes('unavailable'));
  navigation.event({ topic: 'mapper.map.data', data: { error: 'lost', observed_at: null, ts } });
  assert.equal(navigation.map.grid, undefined);
  assert.equal(navigation.map.observed_at, null);
  navigation.event({ topic: 'robot.pose', data: 'broken-json' });
  assert.equal(navigation.pose.x, undefined);
  assert.equal(model.presentationReady(navigation.pose), false);
  f.setReply('/api/navigator/status', { observed_at: ts, state: 'FAILED', active: false, data_ready: false, navigation: null });
  await navigation.poller.refresh();
  assert.equal(navigation.map.grid, undefined);
  assert.ok(f.elements.get('nav-status').textContent.includes('FAILED'));
  assert.ok(f.calls.every(call => call.method === 'GET'));
});

test('explicit null observation never inherits a fresh legacy timestamp', () => {
  const now = Date.now() / 1000, row = { observed_at: null, ts: now };
  assert.equal(model.ageOf(row, now), null);
  assert.equal(model.fresh(row, 3, now), false);
  assert.equal(model.presentationReady(row, 3, now), false);
  assert.equal(model.authorized({ ...armed(), ...row }, 'manual', 'move', now), false);
  const frame = model.cameraFrame({ raw: { exists: true, observed_at: null, mtime: now } }, 'raw', now);
  assert.equal(frame.age, null);
  assert.equal(frame.fresh, false);
  assert.equal(model.ageOf({ ts: now }, now), 0);
});

test('passive pages never bind or dispatch motion shortcuts or a blur STOP', async () => {
  const f = await fixture(armed(), { interactive: false });
  assert.equal(f.panel.can('manual'), false);
  assert.equal(f.listeners.keydown, undefined);
  f.panel.key({ code: 'Space', target: new Element(), preventDefault() { throw new Error('passive shortcut captured'); } });
  f.panel.suspend();
  assert.ok(f.calls.every(call => call.method === 'GET'));
});
test('clearing ESTOP remains disabled until preparation and never automatically arms', async () => {
  const f = await fixture({ ...disarmed(), state: 'ESTOP' });
  assert.equal(f.elements.get('clear-estop').disabled, true);
  f.elements.get('operator-plan').value = 'Prepared isolated fixture, no physical robot';
  f.elements.get('operator-consent').checked = true; f.panel.render();
  assert.equal(f.elements.get('clear-estop').disabled, false);
  await f.panel.arm('clear_estop');
  const writes = f.calls.filter(call => call.method === 'POST');
  assert.equal(writes.length, 1); assert.equal(writes[0].body.action, 'clear_estop');
  assert.equal(writes[0].body.operator_consent, true);
  f.setState({ ...disarmed(), generation: 'cleared-fixture' }); f.panel.render();
  assert.equal(f.elements.get('arm').disabled, true, 'clear consumes consent; another explicit consent is required');
});
test('another presentation clock cannot invalidate the safety permission clock', async () => {
  const f = await fixture(armed());
  assert.equal(f.panel.can('manual'), true);
  const clock = await f.load('model.js'), now = Date.now() / 1000;
  clock.setServerClock(now - 100, now, now);
  assert.equal(f.panel.can('manual'), true);
});
test('service inspection does not grant movement before administration is enabled', async () => {
  const f = await fixture(armed());
  f.document.body.dataset.page = 'system';
  assert.equal(f.panel.can('manual'), false);
  f.panel.key({ code: 'Space', target: new Element(), preventDefault() { throw new Error('read-only admin captured'); } });
  f.panel.suspend();
  assert.ok(f.calls.every(call => call.method === 'GET'));
});
