
import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {readFile} from 'node:fs/promises';
const raw=(await readFile(new URL('../web/assets/operator/overview.js',import.meta.url),'utf8'))
  .replace(/^import .*;$/gm,'').replaceAll('export ','');
function fixture(fetch) {
  const calls=[];
  const scope=vm.createContext({request:async path=>{calls.push(path);return fetch ? await fetch(path) : {data:{raw:{exists:false}}};},
    document:{getElementById:()=>null},window:{dispatchEvent(){}},CustomEvent:class {}});
  const Class=vm.runInContext(raw+';Overview',scope);
  const panel=Object.create(Class.prototype);
  panel.data={state:{devices:{camera:{activity:'off'}}}};
  panel.render=()=>{};panel.renderImages=()=>{};panel.renderSensors=()=>{};
  return {panel,calls};
}
test('idle overview reads metadata once and never polls obstacle; activation resumes',async()=>{
  const {panel,calls}=fixture();
  await panel.loadVision();await panel.loadVision();
  assert.deepEqual(calls,['/vision/snap-info']);
  panel.data.state.devices.camera.activity='on';
  await panel.loadVision();await panel.loadVision();
  assert.equal(calls.filter(x=>x==='/vision/obstacle').length,2);
  panel.data.state.devices.camera.activity='off';
  await panel.loadVision();await panel.loadVision();
  assert.equal(calls.filter(x=>x==='/vision/obstacle').length,2);
});
test('telemetry cadence reads state only; inventory has its own reads',async()=>{
  const {panel,calls}=fixture();
  await panel.loadTelemetry();
  assert.deepEqual(calls,['/state']);
  await panel.loadInventory();
  assert.deepEqual(calls,['/state','/api/app-metrics','/api/logic/catalog']);
});
test('unknown or failed camera observation never activates detection reads',async()=>{
  for(const row of [{},{activity:'on',error:'unavailable'},{activity:'on',stale:true},{activity:'on',offline:true}]){
    const {panel,calls}=fixture();
    panel.data.state.devices.camera=row;
    await panel.loadVision();
    assert.deepEqual(calls,['/vision/snap-info']);
  }
});

test('metadata failure never prevents an independent obstacle read',async()=>{
  const f=fixture(async path=>{
    if(path==='/vision/snap-info')throw new Error('metadata_failed');
    return {data:{present:false}};
  });
  f.panel.data.state.devices.camera.activity='on';
  await assert.rejects(f.panel.loadVision(),/metadata_failed/);
  assert.equal(f.panel.data.snap,null);
  assert.equal(f.panel.data.obstacle.present,false);
  assert.deepEqual(f.calls,['/vision/snap-info','/vision/obstacle']);
});
test('metrics failure never prevents refreshing catalogue',async()=>{
  const f=fixture(async path=>{
    if(path==='/api/app-metrics')throw new Error('metrics_failed');
    return {data:{catalog_version:2}};
  });
  await assert.rejects(f.panel.loadInventory(),/metrics_failed/);
  assert.equal(f.panel.data.metrics,null);
  assert.equal(f.panel.data.catalog.catalog_version,2);
});
test('camera OFF during metadata suppresses obstacle read',async()=>{
  const f=fixture(async path=>{
    f.panel.data.state.devices.camera.activity='off';
    return {data:{}};
  });
  f.panel.data.state.devices.camera.activity='on';
  f.panel.data.obstacle={present:true};
  await f.panel.loadVision();
  assert.deepEqual(f.calls,['/vision/snap-info']);
  assert.equal(f.panel.data.obstacle,null);
});
test('camera OFF during obstacle transfer discards its late result',async()=>{
  const f=fixture(async path=>{
    if(path==='/vision/obstacle')f.panel.data.state.devices.camera.activity='off';
    return {data:{present:true}};
  });
  f.panel.data.state.devices.camera.activity='on';
  await f.panel.loadVision();
  assert.equal(f.panel.data.obstacle,null);
});
