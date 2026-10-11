import { fresh } from './model.js';
import { request, poll } from './transport.js';
import { el, kv, freshPill, rawDetails, tr, text, ageStamp, statusLabel } from './ui.js';
export class Providers {
  constructor() {
    this.target = document.getElementById('provider-runtime');
    this.poller = poll(() => this.load(), { interval: 10000 });
  }
  async load() {
    if (!this.target) return;
    const [state, health, inventory] = await Promise.allSettled([request('/api/providers/state'), request('/api/providers/health'), request('/providers/capabilities')]);
    const data = state.status === 'fulfilled' ? state.value.data : null;
    const checks = health.status === 'fulfilled' ? health.value.data : null;
    const runtimeData = inventory.status === 'fulfilled' ? inventory.value.data : null;
    this.target.replaceChildren(...['text', 'vision', 'voice'].map(domain => {
      const item = data?.domains?.[domain], check = checks?.peer_health ?? checks?.pc_health, runtime = runtimeData?.[domain];
      const card = el('article', 'c-card'); card.append(el('h3', '', domain.toUpperCase()),
        freshPill(data, data?.offline ? 'unknown' : `${data?.source === 'demo' ? 'DEMO · ' : ''}${tr('Rejestr', 'Registry')}: ${statusLabel(item?.ready === true ? 'ready' : item?.effective || item?.mode || item?.status || 'unknown')}`, data?.offline ? 'err' : 'warn'),
        kv([[tr('Host w rejestrze domeny', 'Host in domain registry'), item?.mode || 'unknown'],
          [tr('Źródło / wiek odczytu Pi', 'Pi source / observation age'), data?.source || 'unknown'], [tr('Wiek', 'Age'), ageStamp(data, 10)],
          [tr('Łącze Pi → PC (nie gotowość domeny)', 'Pi → PC reachability (not domain readiness)'), fresh(checks, 10) && !checks?.offline && !checks?.error ? check?.status || 'unknown' : 'unknown / stale'],
          [tr('Rzeczywisty provider PC', 'Actual PC provider'), runtime ? `${runtime.source || 'unknown'} · ${runtime.runtime_mode || 'unknown'} · initialized=${runtime.initialized === true} · ready=${runtime.initialized === true && runtime.ready === true}` : tr('niezainicjalizowany', 'not initialized')]]),
        rawDetails({ registry: item, health: check, health_envelope: checks, pc_runtime: runtime || null }));
      return card;
    }));
    text('provider-note', tr('Rejestr i health nie oznaczają gotowego zadania. Uruchom wybraną domenę opcją z katalogu i sprawdź jej ready. Odczyt i wybór nie uruchamiają modeli.', 'Registry and health do not mean task ready. Start a selected catalog domain and check its ready state. Viewing and selecting do not start models.'));
  }
}
