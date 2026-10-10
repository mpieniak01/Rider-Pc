import assert from 'node:assert/strict';
import test from 'node:test';
import { readFile } from 'node:fs/promises';
import vm from 'node:vm';
const load = async name => {
  const module = new vm.SourceTextModule(await readFile(new URL('../web/assets/operator/' + name, import.meta.url), 'utf8'));
  await module.link(() => { throw new Error('Unexpected module dependency'); });
  await module.evaluate(); return module.namespace;
};
const { unpackContract } = await load('transport.js');
const { observationChannel } = await load('observations.js');
const { cameraFrame, taskCanStart, passivePlanCurrent } = await load('model.js');

const fixture = JSON.parse(await readFile(new URL('./fixtures/contracts/rider-v1.json', import.meta.url), 'utf8'));
for (const [name, { body }] of Object.entries(fixture.cases)) test(`golden ${name} preserves source metadata and fields`, () => {
  const data = unpackContract(body);
  assert.deepEqual(data.contract_meta, body.meta);
  for (const [key, value] of Object.entries(body.data)) {
    if (!['offline', 'stale', 'error'].includes(key)) assert.deepEqual(data[key], value);
  }
  assert.equal(data.offline, body.meta.offline || body.data.offline === true);
});
test('canonical partial telemetry keeps independent battery and zero roll; expired axes stay unknown', () => {
  for (const name of ['telemetry', 'partial_telemetry']) {
    const data = unpackContract(fixture.cases[name].body), input = data.devices.xgo;
    const battery = observationChannel(input, 'battery', { now: fixture.now });
    assert.equal(battery.value, input.sensor_quality.sensors.battery.value * 100); assert.equal(battery.ready, true);
    assert.equal(observationChannel(input, 'roll', { now: fixture.now }).value, 0);
    assert.equal(battery.physical_validity, 'unverified');
  }
});
test('known legacy REST percent and safety ratio never use magnitude guessing', () => {
  assert.equal(observationChannel(fixture.legacy_rest_percent, 'battery', { now: fixture.now }).value, 1);
  assert.equal(observationChannel(fixture.legacy_safety_ratio, 'battery', { now: fixture.now }).value, 100);
});
test('source failure, null and publication heartbeat cannot renew canonical channel time', () => {
  const data = unpackContract(fixture.cases.transport_failure.body);
  assert.equal(observationChannel(data.devices.xgo, 'battery', { now: fixture.now, unavailable: data.offline }).ready, false);
  const canonical = structuredClone(fixture.cases.telemetry.body.data.devices.xgo);
  canonical.sensor_quality.sensors.battery.observed_at = null;
  canonical.sensor_quality.sensors.battery.ts = fixture.now;
  assert.equal(observationChannel(canonical, 'battery', { now: fixture.now }).ready, false);
  canonical.sensor_quality.sensors.battery.observed_at = fixture.now - 10;
  canonical.generated_at = fixture.now;
  assert.equal(observationChannel(canonical, 'battery', { now: fixture.now }).ready, false);
});
test('Frame identities distinguish SSD and obstacle annotations, and unknown time stays unknown', () => {
  const data = unpackContract(fixture.cases.frames.body);
  assert.notEqual(data.ssd.source, data.obst.source);
  assert.equal(cameraFrame({ raw: { exists: true, observed_at: null, mtime: fixture.now } }, 'raw', fixture.now).fresh, false);
});
test('catalog denies autonomous start regardless of armed authorization; geometry is not motion permission', () => {
  const catalog = unpackContract(fixture.cases.catalog.body);
  const task = { installed: true, can_move: false, observed_at: fixture.now, state: 'stopped', start_available: false };
  assert.equal(taskCanStart(task, catalog, null, fixture.now), false);
  assert.equal(passivePlanCurrent({ planning_ready: true }, {}, {}, fixture.now), false);
});
test('full overview manifest keeps twenty cards, four charts and four distinct previews', async () => {
  const html = await readFile(new URL('../web/view.html', import.meta.url), 'utf8');
  assert.equal((html.match(/<div class="c-card">/g) || []).length, 20);
  assert.equal((html.match(/<canvas /g) || []).length, 4);
  for (const id of ['img_cam', 'img_proc', 'img_obst', 'img_tracker', 'd_xgo_batt', 'ci_cpu', 'pcCpu', 'mcpToolsList']) assert.match(html, new RegExp(`id="${id}"`));
  const overview = await readFile(new URL('../web/assets/operator/overview.js', import.meta.url), 'utf8');
  assert.match(overview, /obst: '\/snapshots\/obst_annot\.jpg'/);
  assert.match(overview, /\['obst', 'img_obst'\]/);
  assert.doesNotMatch(overview, /\['ssd', 'img_obst'\]/);
});

test('unsupported named domain or version cannot be treated as a supported contract', () => {
  const body = fixture.cases.telemetry.body;
  for (const meta of [{ ...body.meta, contract_id: 'rider.future' }, { ...body.meta, contract_version: true }, { ...body.meta, envelope_version: 2 }]) {
    assert.throws(() => unpackContract({ ...body, meta }), /unsupported_contract/);
  }
});
test('explicit file provenance exposes file age, never invents capture time or camera running', () => {
  const row = cameraFrame({ raw: { exists: true, observed_at: null, file_observed_at: fixture.now, provenance: 'file_mtime' } }, 'raw', fixture.now);
  assert.equal(row.fresh, true); assert.equal(row.capture_at, null); assert.equal(row.timeBasis, 'file');
  assert.equal(cameraFrame({ raw: { exists: true, observed_at: null, mtime: fixture.now } }, 'raw', fixture.now).fresh, false);
});

test('partial declared envelopes and cross-domain responses fail closed rather than becoming legacy', () => {
  for (const body of [{ meta: { envelope_version: 99 } }, { data: {} }, { meta: { contract_id: 'rider.telemetry' } }]) assert.throws(() => unpackContract(body), /invalid_contract_payload/);
  assert.throws(() => unpackContract(fixture.cases.telemetry.body, 'rider.safety'), /contract_family_mismatch/);
});

for (const flag of ['error', 'offline', 'placeholder', 'stale']) test(`frame child ${flag} blocks fresh preview without changing source time`, () => {
  const frame = cameraFrame({ raw: { exists: true, observed_at: fixture.now, [flag]: flag === 'error' ? 'capture_failed' : true } }, 'raw', fixture.now);
  assert.equal(frame.fresh, false); assert.equal(frame.ts, fixture.now); assert.equal(frame.age, 0);
});

test('assessment age advances independently of unchanged producer generation time', () => {
  const input = structuredClone(fixture.cases.telemetry.body.data.devices.xgo);
  const row = input.sensor_quality.sensors.battery;
  row.observed_at = 999.8; row.age_s = 1.2; row.assessed_at = 1001; input.generated_at = 1000;
  assert.ok(Math.abs(observationChannel(input, 'battery', { now: 1001 }).age_s - 1.2) < 1e-9);
  assert.ok(Math.abs(observationChannel(input, 'battery', { now: 1002 }).age_s - 2.2) < 1e-9);
  delete row.assessed_at;
  assert.ok(Math.abs(observationChannel(input, 'battery', { now: 1002 }).age_s - 2.2) < 1e-9);
  assert.equal(observationChannel({ ...input, stale: true }, 'battery', { now: 1001 }).ready, false);
});
