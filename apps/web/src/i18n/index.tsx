import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { messages, type MessageKey } from './messages'
import { setFormatLocale } from '../utils'

export type Locale = 'zh-CN' | 'en-US'

const LOCALE_STORAGE_KEY = 'paw.locale.v1'
const DEFAULT_LOCALE: Locale = 'zh-CN'
let activeLocale: Locale = DEFAULT_LOCALE

function isLocale(value: string | null): value is Locale {
  return value === 'zh-CN' || value === 'en-US'
}

function readStoredLocale(): Locale {
  try {
    const stored = localStorage.getItem(LOCALE_STORAGE_KEY)
    return isLocale(stored) ? stored : DEFAULT_LOCALE
  } catch {
    return DEFAULT_LOCALE
  }
}

function interpolate(template: string, values?: Record<string, string | number>): string {
  if (!values) return template
  return template.replace(/\{(\w+)\}/g, (match, key: string) =>
    Object.prototype.hasOwnProperty.call(values, key) ? String(values[key]) : match,
  )
}

interface I18nValue {
  locale: Locale
  setLocale: (locale: Locale) => void
  t: (key: MessageKey, values?: Record<string, string | number>) => string
}

const I18nContext = createContext<I18nValue | null>(null)

export function translate(key: MessageKey, values?: Record<string, string | number>): string {
  return interpolate(messages[activeLocale][key], values)
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(readStoredLocale)
  // Apply the locale before children render so dates and relative times switch in the same frame.
  activeLocale = locale
  setFormatLocale(locale)

  const setLocale = useCallback((next: Locale) => {
    setLocaleState(next)
    try {
      localStorage.setItem(LOCALE_STORAGE_KEY, next)
    } catch {
      // Storage can be unavailable in private or restricted contexts.
    }
  }, [])

  useEffect(() => {
    document.documentElement.lang = locale
    try {
      localStorage.setItem(LOCALE_STORAGE_KEY, locale)
    } catch {
      // Keep the in-memory locale when persistence is unavailable.
    }
  }, [locale])

  const t = useCallback(
    (key: MessageKey, values?: Record<string, string | number>) =>
      interpolate(messages[locale][key], values),
    [locale],
  )

  const value = useMemo(() => ({ locale, setLocale, t }), [locale, setLocale, t])

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}

export function useI18n(): I18nValue {
  const value = useContext(I18nContext)
  if (!value) throw new Error('useI18n must be used within I18nProvider')
  return value
}
