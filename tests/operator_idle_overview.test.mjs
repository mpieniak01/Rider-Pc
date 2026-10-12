
import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {readFile} from 'node:fs/promises';
const raw=(await readFile(new URL('../web/assets/operator/overview.js',import.meta.url),'utf8'))
  .replace(/^import .*;$/gm,'').replaceAll('export ','');
function fixture() {
  const calls=[];
  const scope=vm.createContext({request:async path=>{calls.push(path);return {data:{raw:{exists:false}}};},
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
