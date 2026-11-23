/**
 * Minimal typed i18n (German + English), no dependencies.
 *
 * - UI strings live in the dictionaries `./de.ts` (defines the key set) and `./en.ts`
 *   (typed as `Dictionary`, so a missing or extra key in either language is a compile error).
 * - Long-form content that sits next to coordinates (hotspots, teleports, tour chapters,
 *   timeline milestones) uses `Localized<T>` records, read with `loc()`; a missing language
 *   is a compile error there too.
 * - `t(key, { name: value })` replaces `{name}` placeholders.
 * - Static markup is translated through `data-i18n` (textContent), `data-i18n-html` (innerHTML,
 *   only for our own dictionary strings), `data-i18n-title` and `data-i18n-aria` attributes.
 *
 * Initial language: saved choice (localStorage) -> `?lang=de|en` overrides it -> navigator.language
 * (German if it starts with "de", otherwise English). The inline boot script in index.html applies
 * the same rule before the bundle loads, so the loading card does not flash in the wrong language.
 */
import { de, type Dictionary, type MessageKey } from './de';
import { en } from './en';

export type { MessageKey } from './de';
export type Lang = 'de' | 'en';
export const LANGS: readonly Lang[] = ['de', 'en'];
export type Localized<T = string> = Record<Lang, T>;
export type MessageParams = Record<string, string | number>;

const DICTS: Record<Lang, Dictionary> = { de, en };
const STORAGE_KEY = 'sagrada.lang';

function isLang(v: unknown): v is Lang {
  return v === 'de' || v === 'en';
}

export function detectLang(): Lang {
  let lang: Lang | null = null;
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (isLang(saved)) lang = saved;
  } catch {
    // Storage blocked (private mode / sandboxed iframe)
  }
  try {
    const q = new URLSearchParams(window.location.search).get('lang');
    if (isLang(q)) lang = q;
  } catch {
    // Ignore malformed URLs
  }
  if (lang) return lang;
  return /^de/i.test(navigator.language || '') ? 'de' : 'en';
}

let current: Lang = detectLang();
const listeners = new Set<(lang: Lang) => void>();

export function getLang(): Lang {
  return current;
}

/** Looks up a UI string and fills `{placeholders}`. */
export function t(key: MessageKey, params?: MessageParams): string {
  const s = DICTS[current][key] ?? de[key] ?? key;
  if (!params) return s;
  return s.replace(/\{(\w+)\}/g, (m, name: string) => (name in params ? String(params[name]) : m));
}

/** Picks the current language from a localized content record. */
export function loc<T>(value: Localized<T>): T {
  return value[current];
}

const numberFormats = new Map<string, Intl.NumberFormat>();
/** Locale-aware fixed-digit number (de: 172,5 · en: 172.5). */
export function fmtNum(n: number, digits = 0): string {
  const id = `${current}:${digits}`;
  let f = numberFormats.get(id);
  if (!f) {
    f = new Intl.NumberFormat(current === 'de' ? 'de-DE' : 'en-US', {
      minimumFractionDigits: digits,
      maximumFractionDigits: digits,
      useGrouping: false,
    });
    numberFormats.set(id, f);
  }
  return f.format(n);
}

/** Registers a re-render callback for live language switches. Returns an unsubscribe function. */
export function onLangChange(cb: (lang: Lang) => void): () => void {
  listeners.add(cb);
  return () => listeners.delete(cb);
}

export function setLang(lang: Lang): void {
  if (lang === current) return;
  current = lang;
  try {
    localStorage.setItem(STORAGE_KEY, lang);
  } catch {
    // Ignore
  }
  // Keep an explicit ?lang= in the address bar in sync so a reload / shared link keeps the choice
  try {
    const url = new URL(window.location.href);
    if (url.searchParams.has('lang')) {
      url.searchParams.set('lang', lang);
      history.replaceState(history.state, '', url);
    }
  } catch {
    // Ignore
  }
  translateDom();
  for (const cb of listeners) {
    try {
      cb(lang);
    } catch (err) {
      console.error('[i18n] listener failed:', err);
    }
  }
}

function lookupAttr(el: Element, attr: string): string | null {
  const key = el.getAttribute(attr);
  if (!key) return null;
  if (!(key in de)) {
    if (import.meta.env.DEV) console.warn(`[i18n] unknown key "${key}" on`, el);
    return null;
  }
  return t(key as MessageKey);
}

/** Applies the current language to <html lang>, the document title/description and all data-i18n* nodes. */
export function translateDom(root: ParentNode = document): void {
  if (root === document) {
    document.documentElement.lang = current;
    document.title = t('meta.title');
    document.querySelector('meta[name="description"]')?.setAttribute('content', t('meta.description'));
    syncLangSwitches();
  }
  root.querySelectorAll('[data-i18n]').forEach((el) => {
    const s = lookupAttr(el, 'data-i18n');
    if (s !== null && el.textContent !== s) el.textContent = s;
  });
  root.querySelectorAll('[data-i18n-html]').forEach((el) => {
    const s = lookupAttr(el, 'data-i18n-html');
    if (s !== null && el.innerHTML !== s) el.innerHTML = s;
  });
  root.querySelectorAll('[data-i18n-title]').forEach((el) => {
    const s = lookupAttr(el, 'data-i18n-title');
    if (s !== null) el.setAttribute('title', s);
  });
  root.querySelectorAll('[data-i18n-aria]').forEach((el) => {
    const s = lookupAttr(el, 'data-i18n-aria');
    if (s !== null) el.setAttribute('aria-label', s);
  });
}

function syncLangSwitches(): void {
  document.querySelectorAll<HTMLButtonElement>('.lang-switch [data-lang]').forEach((btn) => {
    const on = btn.dataset.lang === current;
    btn.classList.toggle('active', on);
    btn.setAttribute('aria-pressed', String(on));
  });
}

/** Wires every `.lang-switch` group (top bar + loading card) to setLang(). */
export function initLangSwitches(): void {
  document.querySelectorAll<HTMLButtonElement>('.lang-switch [data-lang]').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const lang = btn.dataset.lang;
      if (isLang(lang)) setLang(lang);
      btn.blur();
    });
  });
  syncLangSwitches();
}

// Dev-only guard: the pre-bundle boot script in index.html carries a copy of the loading-card strings
if (import.meta.env.DEV) {
  const boot = (window as unknown as { __sagradaBootText?: Record<Lang, Record<string, string>> }).__sagradaBootText;
  if (boot) {
    for (const lang of LANGS) {
      for (const [key, value] of Object.entries(boot[lang] ?? {})) {
        if (!(key in de) || DICTS[lang][key as MessageKey] !== value) {
          console.warn(`[i18n] index.html boot text for "${key}" (${lang}) differs from the dictionary`);
        }
      }
    }
  }
}
