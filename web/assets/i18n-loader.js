import { initI18n, applyDom, t } from '/web/assets/i18n.js';

function pickLang(value) {
  if (!value) return null;
  const lowered = value.toLowerCase();
  if (lowered.startsWith('en')) return 'en';
  if (lowered.startsWith('pl')) return 'pl';
  return null;
}

export async function initI18nPage(options = {}) {
  const { titleKey, fallbackTitle, defaultLang = 'pl' } = options;
  const urlLang = new URLSearchParams(location.search).get('lang');
  const saved = localStorage.getItem('lang');
  const browser = (navigator.language || '').slice(0, 2).toLowerCase();
  const lang = pickLang(urlLang) || pickLang(saved) || pickLang(browser) || defaultLang;
  if (urlLang) localStorage.setItem('lang', lang);
  await initI18n(lang);
  applyDom();
  document.documentElement.setAttribute('lang', lang);
  if (titleKey) {
    document.title = t(titleKey) || fallbackTitle || document.title;
  } else if (fallbackTitle && !document.title) {
    document.title = fallbackTitle;
  }
  window.__i18n_t = t;
  return { lang, t };
}
