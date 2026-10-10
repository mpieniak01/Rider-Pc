import { initI18n } from '/web/assets/i18n.js';
import { Overview } from './overview.js?v=telemetry-20261010';
import { SafetyPanel } from './safety.js';
import { Tasks } from './tasks.js';
import { Devices } from './devices.js?v=telemetry-20261010';
import { System } from './system.js?v=telemetry-20261010';
import { Navigation } from './navigation.js';
import { Providers } from './providers.js';
import { Chat } from './chat.js';
import { events } from './transport.js';
import { fresh, catalogKnown, safetyKnown } from './model.js';
import { el, text, tr, localizeStatic, refreshAges, showError } from './ui.js';

initI18n(localStorage.getItem('lang') || 'pl'); localizeStatic();
setInterval(refreshAges, 1000);
const page = document.body.dataset.page;
const globalStop = el('button', 'c-btn operator-stop operator-global-stop', '■ STOP');
globalStop.type = 'button'; globalStop.dataset.stop = ''; document.querySelector('main').append(globalStop);
let tasks, system, navigation, chat, devices, overview, lastKey = '';
const safety = new SafetyPanel(state => {
  const key = JSON.stringify([state?.state, state?.generation, state?.can_move, state?.ready, state?.hardware_ready, state?.capabilities, ['manual', 'follow_me', 'navigation'].map(owner => safety.can(owner)), fresh(state), safety.clockFresh(), safety.revokedGenerations.has(state?.generation)]);
  if (key !== lastKey) { lastKey = key; tasks?.render(); system?.render(); }
  navigation?.render();
  devices?.renderTelemetry(); overview?.renderSensors();
  renderCapabilities(state);
});
if (page === 'control') { tasks = new Tasks(safety); new Providers(); }
if (page === 'devices') devices = new Devices(safety);
if (page === 'system') system = new System(safety);
if (page === 'navigation') { tasks = new Tasks(safety, 'task-list', task => task.motion_owner === 'navigation' || task.scenario === 'S8'); navigation = new Navigation(safety); }
if (page === 'chat') { tasks = new Tasks(safety, 'task-list', task => ['voice', 'provider'].includes(task.option_kind)); chat = new Chat(tasks); }
if (page === 'view') overview = new Overview(safety);

events(event => {
  let data = event.data;
  try { if (typeof data === 'string') data = JSON.parse(data); } catch { navigation?.event(event); return; }
  if (event.topic === 'motion.state' && data?.contract_version === 1) safety.update(data);
  if (event.topic === 'motion.ack') safety.ack(data);
  navigation?.event(event);
  const log = document.getElementById('system-events');
  if (log) { log.prepend(el('li', '', `${event.topic || '?'} · ${event.ts ?? '—'} · ${JSON.stringify(data).slice(0, 500)}`)); while (log.children.length > 40) log.lastElementChild.remove(); }
  text('last-event', `${event.topic || '?'} · ${event.ts ?? '—'}`);
}, () => text('last-event', tr('Strumień zdarzeń niedostępny; odczyt okresowy aktywny', 'Event stream unavailable; periodic reads active')));

function renderCapabilities(state) {
  const target = document.getElementById('actuator-capabilities'); if (!target) return;
  const key = JSON.stringify([state?.capabilities, fresh(state), state?.state, state?.can_move]);
  if (target.dataset.key !== key) {
  target.dataset.key = key;
  target.replaceChildren(...['move', 'turn', 'balance', 'height', 'action'].map(action => {
    const cap = safetyKnown(state) ? state?.capabilities?.[action] : null; const row = el('li');
    row.textContent = `${action}: ${cap?.available === true && cap?.stop_verified === true ? tr('dostępne po uzbrojeniu', 'available after arming') : cap?.verification === 'manual_characterization_required' ? tr('blokada — wymagana ręczna charakterystyka i przerwanie ruchu', 'blocked — manual characterization and interruption required') : tr('niedostępne / niepotwierdzone', 'unavailable / unverified')}`;
    return row;
  }));
  }
  document.querySelectorAll('[data-actuator]').forEach(node => { node.disabled = !safety.can('manual', node.dataset.actuator); });
}
document.getElementById('height-apply')?.addEventListener('click', () => safety.send('height', { height: Number(document.getElementById('height').value) }).catch(showError));
document.getElementById('balance-apply')?.addEventListener('click', () => safety.send('balance', { enabled: document.getElementById('balance').checked }).catch(showError));
document.getElementById('action-apply')?.addEventListener('click', () => safety.send('action', { action_id: Number(document.getElementById('action-id').value) }).catch(showError));
window.addEventListener('dashboard:langchange', () => { localizeStatic(); lastKey = ''; safety.render(); tasks?.render(); system?.render(); navigation?.render(); });
if (chat) setInterval(() => { if (!chat.busy) document.getElementById('chat-send').disabled = !catalogKnown(tasks.catalog); }, 1000);

document.getElementById('event-clear')?.addEventListener('click', () => document.getElementById('system-events').replaceChildren());
