import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import type { ToastMessage } from '../types'
import { Icon } from './Icon'
import { useI18n } from '../i18n'

type ToastTone = ToastMessage['tone']

interface ToastApi {
  notify: (text: string, tone?: ToastTone) => void
}

const ToastContext = createContext<ToastApi | null>(null)

export function ToastProvider({ children }: { children: ReactNode }) {
  const { t } = useI18n()
  const [toasts, setToasts] = useState<ToastMessage[]>([])
  const nextId = useRef(0)
  const timers = useRef<Map<number, number>>(new Map())

  const dismiss = useCallback((id: number) => {
    setToasts((current) => current.filter((toast) => toast.id !== id))
    const timer = timers.current.get(id)
    if (timer) {
      window.clearTimeout(timer)
      timers.current.delete(id)
    }
  }, [])

  const notify = useCallback(
    (text: string, tone: ToastTone = 'info') => {
      const id = ++nextId.current
      setToasts((current) => [...current.slice(-3), { id, tone, text }])
      const timer = window.setTimeout(() => dismiss(id), tone === 'danger' ? 7000 : 4200)
      timers.current.set(id, timer)
    },
    [dismiss],
  )

  const value = useMemo(() => ({ notify }), [notify])

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="toast-stack" aria-live="polite" aria-atomic="false">
        {toasts.map((toast) => (
          <div key={toast.id} className={`toast toast-${toast.tone}`} role="status">
            <span className="toast-icon">
              <Icon
                name={toast.tone === 'danger' ? 'alert' : toast.tone === 'success' ? 'check' : 'terminal'}
                size={13}
              />
            </span>
            <span className="toast-text">{toast.text}</span>
            <button
              type="button"
              className="icon-button toast-close"
              aria-label={t('component.dismissNotification')}
              onClick={() => dismiss(toast.id)}
            >
              <Icon name="x" size={12} />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast(): ToastApi {
  const context = useContext(ToastContext)
  if (!context) throw new Error('useToast must be used within ToastProvider')
  return context
}
