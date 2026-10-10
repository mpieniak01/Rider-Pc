import { initI18n } from '/web/assets/i18n.js';
import { SafetyPanel } from './safety.js';
import { Tasks } from './tasks.js';
import { Devices } from './devices.js';
import { System } from './system.js';
import { Navigation } from './navigation.js';
import { Providers } from './providers.js';
import { Chat } from './chat.js';
import { request, poll, events } from './transport.js';
import { fresh, ageOf, displayValue, catalogKnown, safetyKnown, presentationReady } from './model.js';
import { el, text, tr, localizeStatic, refreshAges, showError } from './ui.js';

initI18n(localStorage.getItem('lang') || 'pl'); localizeStatic();
setInterval(refreshAges, 1000);
const page = document.body.dataset.page;
const globalStop = el('button', 'c-btn operator-stop operator-global-stop', '■ STOP');
globalStop.type = 'button'; globalStop.dataset.stop = ''; document.querySelector('main').append(globalStop);
let tasks, system, navigation, chat, lastKey = '';
const safety = new SafetyPanel(state => {
  const key = JSON.stringify([state?.state, state?.generation, state?.can_move, state?.ready, state?.hardware_ready, state?.capabilities, ['manual', 'follow_me', 'navigation'].map(owner => safety.can(owner)), fresh(state), safety.clockFresh(), safety.revokedGenerations.has(state?.generation)]);
  if (key !== lastKey) { lastKey = key; tasks?.render(); system?.render(); }
  navigation?.render();
  renderCapabilities(state);
});
if (page === 'control') { tasks = new Tasks(safety); new Providers(); }
if (page === 'devices') new Devices();
if (page === 'system') system = new System(safety);
if (page === 'navigation') { tasks = new Tasks(safety, 'task-list', task => task.motion_owner === 'navigation' || task.scenario === 'S8'); navigation = new Navigation(safety); }
if (page === 'chat') { tasks = new Tasks(safety, 'task-list', task => ['voice', 'provider'].includes(task.option_kind)); chat = new Chat(tasks); }
if (page === 'view') {
  poll(async () => {
    const results = await Promise.allSettled([request('/state'), request('/healthz'), request('/api/logic/catalog')]);
    const [state, health, catalog] = results.map(result => result.status === 'fulfilled' ? result.value.data : null);
    const xgo = state?.devices?.xgo;
    text('overview-connection', tr('API PC', 'PC API') + ': ' + (health?.status === 'ok' || health?.ok === true ? 'responding' : 'unknown') + ' · Pi: ' + (catalog?.offline ? 'offline' : catalogKnown(catalog) ? 'v2 observed' : 'unknown'));
    text('overview-battery', `${displayValue(xgo?.battery_pct, '%')} · ${presentationReady(xgo) ? tr('świeży pomiar', 'fresh reading') : tr('brak / stary pomiar', 'missing / stale reading')}`);
    text('overview-age', ageOf(xgo) === null ? '—' : `${ageOf(xgo).toFixed(1)} s`);
    const active = catalog?.features?.filter(task => task.requested) || [];
    document.getElementById('overview-tasks').replaceChildren(...active.map(task => el('li', '', `${task.title || task.name} · ${task.state || 'unknown'}${task.error ? ` · ${task.error}` : ''}`)));
    text('overview-task-status', catalogKnown(catalog) ? tr('Stan z katalogu v2', 'State from catalog v2') : tr('Nieznany / stary katalog', 'Unknown / old catalog'));
    if (state) window.dispatchEvent(new CustomEvent('dashboard:update', { detail: state }));
    if (!health || !state || !catalog) throw new Error(tr('Niepełny odczyt; brak danych nie oznacza sprawnego urządzenia', 'Incomplete read; missing data does not mean healthy hardware'));
  }, { interval: 3000, onError: error => { text('overview-connection', 'unknown'); showError(error); } });
}
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
