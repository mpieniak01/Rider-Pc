import { catalogKnown, fresh, serviceActionAllowed, safetyKnown } from './model.js';
import { request, poll } from './transport.js';
import { el, kv, freshPill, button, details, tr, ageLabel, ageStamp, text, showError, rawDetails } from './ui.js';

export class System {
  constructor(safety) {
    this.safety = safety; this.admin = false; this.catalog = null; this.services = null;
    this.busy = new Set(); this.results = new Map(); this.resources = new Map(); this.logResults = new Map(); this.logBusy = new Set(); this.expandedDetails = new Map();
    document.getElementById('admin-mode')?.addEventListener('change', event => { this.admin = event.target.checked; this.render(); });
    document.getElementById('rescue-inspect')?.addEventListener('click', () => this.inspectRescue());
    document.getElementById('rescue-release')?.addEventListener('click', () => this.release());
    this.poller = poll(async () => {
      const [catalog, services, graph, pc, pi] = await Promise.allSettled([
        request('/api/logic/catalog'), request('/svc'), request('/api/services/graph'),
        request('/status/system-pc'), request('/sysinfo')
      ]);
      this.catalog = catalog.status === 'fulfilled' ? catalog.value.data : null;
      this.services = services.status === 'fulfilled' ? services.value.data : null;
      this.graph = graph.status === 'fulfilled' ? graph.value.data : null;
      this.hostMetrics = { pc: pc.status === 'fulfilled' ? pc.value.data : null, pi: pi.status === 'fulfilled' ? pi.value.data : null };
      this.render();
      if (!this.services) throw new Error(tr('Inwentarz usług niedostępny', 'Service inventory unavailable'));
    }, { interval: 5000, onError: showError });
  }
  rememberDetails(target) {
    for (const node of target?.querySelectorAll?.('details[data-system-detail]') || []) {
      this.expandedDetails.set(node.dataset.systemDetail, node.open === true);
    }
  }
  keepDetails(key, node, defaultOpen = false) {
    node.dataset.systemDetail = key;
    node.open = this.expandedDetails.has(key) ? this.expandedDetails.get(key) : defaultOpen;
    return node;
  }
  identity(row) { return `${row.host}:${row.unit}`; }
  allowed(row, action) {
    return this.admin && !this.busy.has(this.identity(row))
      && serviceActionAllowed(row, action, this.catalog, this.safety.state)
      && (!row.can_move || !['start', 'restart'].includes(action) || (this.safety.can(row.motion_owner) && this.safety.can(row.motion_owner, 'turn')));
  }
  async action(row, action) {
    if (!this.allowed(row, action)) return;
    const id = this.identity(row), body = { action, host: row.host };
    if (row.can_move && ['start', 'restart'].includes(action)) {
      const envelope = this.safety.envelope('move', {}, row.motion_owner);
      for (const key of ['generation', 'seq', 'source', 'ts', 'ttl_ms', 'request_id']) body[key] = envelope[key];
    }
    this.busy.add(id); this.results.set(id, { status: 'pending' }); this.render();
    try {
      const result = await request(`/svc/${encodeURIComponent(row.unit)}`, { method: 'POST', body, timeout: 20000 });
      this.results.set(id, { status: result.status === 202 || result.data.pending ? 'pending' : result.data.ok ? 'observed' : 'rejected', data: result.data });
      text('operator-message', tr('Odpowiedź procesu odebrana; gotowość zadania sprawdź w katalogu.', 'Process response received; verify task readiness in the catalog.'));
    } catch (error) { this.results.set(id, { status: error.status ? 'rejected' : 'unknown', error: error.message, data: error.data }); showError(error); }
    finally { this.busy.delete(id); this.render(); this.poller.refresh(); this.safety.poller.refresh(); }
  }
  async logs(row) {
    const id = this.identity(row);
    if (this.logBusy.has(id)) return;
    this.logBusy.add(id);
    try { this.logResults.set(id, (await request(`/api/services/${encodeURIComponent(row.unit)}/logs?host=${encodeURIComponent(row.host)}`, { timeout: 4000 })).data); }
    catch (error) { this.logResults.set(id, { error: error.message, observed_at: null, source: row.host }); }
    finally { this.logBusy.delete(id); this.render(); }
  }
  render() {
    const target = document.getElementById('service-list'); if (!target) return;
    this.rememberDetails(target); this.rememberDetails(document.getElementById('system-details-data'));
    text('system-contract', this.services?.contract_version === 2 ? `PC aggregator v2 · ${ageLabel(this.services)}` : tr('Brak kontraktu — tylko odczyt', 'No contract — read only'));
    const rows = Array.isArray(this.services?.services) ? this.services.services : [];
    const groups = new Map();
    for (const row of rows) {
      const group = `${(row.host || 'unknown').toUpperCase()} · ${row.kind === 'application_provider' ? tr('Providery aplikacji', 'Application providers') : row.lifecycle || row.group || 'unknown'}`;
      if (!groups.has(group)) groups.set(group, []); groups.get(group).push(row);
    }
    target.replaceChildren(...[...groups].map(([group, entries]) => {
      const section = el('section'); section.append(el('h2', '', group));
      const grid = el('div', 'operator-grid');
      for (const row of entries) {
        const card = el('article', 'c-card service-node'); card.setAttribute('role', 'article');
        card.dataset.identity = this.identity(row); card.title = tr('Odczyt stanu; akcje tylko przez osobne przyciski', 'Read only status; actions require separate buttons');
        const current = fresh(row, 10) && !row.offline && !row.error;
        const active = row.active || row.active_state || 'unknown';
        card.append(el('h3', '', `${row.host || '?'} · ${row.label || row.unit}`),
          freshPill(row, current ? active : 'unknown', current && active === 'active' ? 'ok' : row.error || active === 'failed' ? 'err' : 'warn'),
          kv([[tr('Jednostka', 'Unit'), row.unit], [tr('Host / typ / źródło', 'Host / type / source'), `${row.host || '?'} / ${row.kind || 'systemd'} / ${row.source || 'unknown'}`],
            [tr('Wiek odczytu', 'Observation age'), ageStamp(row, 10)],
            [tr('Ruch', 'Motion'), row.can_move === true ? tr('TAK — osobna zgoda', 'YES — separate consent') : row.can_move === false ? tr('bez napędów', 'no actuators') : tr('nieznany wpływ — start zablokowany', 'unknown effect — start blocked')],
            [tr('Konsumenci', 'Consumers'), (row.consumers || []).join(', ')], [tr('Zasoby', 'Resources'), (row.resources || []).join(', ')],
            [tr('Zależności', 'Dependencies'), (row.dependencies || []).join(', ')],
            [tr('Powód / błąd', 'Reason / error'), row.error || row.reason || row.sub], [tr('Autostart', 'Autostart'), row.enabled]]));
        if (row.last_known_active) card.append(el('p', 'operator-warning', `${tr('Ostatni znany stan', 'Last known state')}: ${row.last_known_active}`));
        if (row.kind !== 'application_provider') {
          const actions = el('div', 'operator-row');
          for (const action of ['start', 'stop', 'restart']) actions.append(button(action, () => this.action(row, action).catch(showError), !this.allowed(row, action)));
          card.append(actions);
          const autostart = el('div', 'operator-row');
          autostart.append(el('span', '', tr('Osobna zmiana autostartu:', 'Separate autostart change:')),
            button('enable', () => this.action(row, 'enable').catch(showError), !this.allowed(row, 'enable')),
            button('disable', () => this.action(row, 'disable').catch(showError), !this.allowed(row, 'disable')));
          card.append(this.keepDetails(`autostart:${this.identity(row)}`, details(tr('Autostart', 'Autostart'), autostart)));
        } else card.append(el('p', 'operator-muted', tr('Cykl życia providera aplikacji; brak fikcyjnej jednostki systemd.', 'Application provider lifecycle; no fictional systemd unit.')));
        if (row.kind !== 'application_provider') {
          const readLogs = button(tr('Odczytaj ostatnie logi', 'Read recent logs'), () => this.logs(row), this.logBusy.has(this.identity(row)) || !['pc', 'pi'].includes(row.host)); readLogs.dataset.serviceLogs = ''; card.append(readLogs);
          const logs = this.logResults.get(this.identity(row));
          if (logs) {
            const body = el('div'); body.append(kv([[tr('Źródło', 'Source'), logs.source], [tr('Wiek odczytu', 'Observation age'), ageStamp(logs, 60)]]), el('pre', 'operator-json', logs.error || (logs.lines || []).join('\n') || tr('Brak wpisów', 'No entries')));
            if (logs.truncated) body.append(el('p', '', tr('Odczyt ograniczony do 64 KiB / 50 linii', 'Read limited to 64 KiB / 50 lines')));
            card.append(this.keepDetails(`logs:${this.identity(row)}`, details(tr('Logi tylko do odczytu', 'Read only logs'), body), true));
          }
        }
        const result = this.results.get(this.identity(row)); if (result) card.append(this.keepDetails(`result:${this.identity(row)}`, rawDetails(result)));
        card.append(this.keepDetails(`source:${this.identity(row)}`, rawDetails(row))); grid.append(card);
      }
      section.append(grid); return section;
    }));
    document.getElementById('system-details-data')?.replaceChildren(this.keepDetails('source:system', rawDetails({ hosts: this.hostMetrics, graph: this.graph, inventory_hosts: this.services?.hosts })));
    const pi = this.services?.hosts?.pi;
    text('network-status', `Pi: ${pi?.offline ? 'offline' : pi?.observed_at ? 'observed' : 'unknown'} · PC: ${this.services?.hosts?.pc?.demo ? 'demo' : this.services?.hosts?.pc?.configured ? 'configured' : tr('brak skonfigurowanych jednostek', 'no configured units')}`);
  }
  async inspectRescue() {
    const name = document.getElementById('rescue-resource').value;
    try {
      const data = (await request(`/api/resource/${encodeURIComponent(name)}`)).data; this.resources.set(name, data);
      const target = document.getElementById('rescue-owners'); target.replaceChildren();
      for (const owner of data.holders || []) {
        const label = el('label', 'operator-row'), checkbox = el('input'); checkbox.type = 'checkbox'; checkbox.value = owner.pid; checkbox.name = 'rescue-pid';
        label.append(checkbox, el('span', '', `${owner.pid} · ${owner.service || owner.cmd || owner.command || '?'} · ${owner.user || '?'}`)); target.append(label);
      }
      target.append(rawDetails(data)); text('rescue-status', `${data.state || 'unknown'} · ${ageLabel(data)}`);
    } catch (error) { this.resources.delete(name); text('rescue-status', 'unknown'); showError(error); }
  }
  async release() {
    const name = document.getElementById('rescue-resource').value, data = this.resources.get(name);
    const pids = [...document.querySelectorAll('[name="rescue-pid"]:checked')].map(node => Number(node.value));
    const permitted = new Set((data?.holders || []).map(owner => Number(owner.pid)));
    if (!this.admin || !catalogKnown(this.catalog) || !safetyKnown(this.safety.state)
      || !['DISARMED', 'ESTOP'].includes(this.safety.state.state) || !this.safety.clockFresh()
      || !fresh(data, 10) || data.state !== 'busy' || data.error || data.offline || !pids.length
      || pids.some(pid => !Number.isInteger(pid) || pid <= 0 || !permitted.has(pid))
      || !document.getElementById('rescue-consent').checked || document.getElementById('rescue-confirm').value.trim() !== name)
      return showError(new Error(tr('Wymagane potwierdzone DISARMED/ESTOP, administracja, świeży zajęty zasób, wybrane PID, nazwa i zgoda.', 'Confirmed DISARMED/ESTOP, administration, fresh busy resource, selected PIDs, resource name and consent are required.')));
    const button = document.getElementById('rescue-release'); button.disabled = true;
    try { const result = await request(`/api/resource/${encodeURIComponent(name)}`, { method: 'POST', body: { action: 'release', pids, force: true, operator_consent: true }, timeout: 20000 }); text('operator-message', JSON.stringify(result.data)); }
    catch (error) { showError(error); }
    finally { button.disabled = false; document.getElementById('rescue-consent').checked = false; document.getElementById('rescue-confirm').value = ''; this.resources.delete(name); }
  }
}
