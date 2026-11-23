import type { ReactNode } from 'react'
import { cx } from '../utils'
import { Icon, type IconName } from './Icon'
import { useI18n } from '../i18n'

export function MicroLabel({ children, className }: { children: ReactNode; className?: string }) {
  return <span className={cx('micro-label', className)}>{children}</span>
}

export function Tag({
  children,
  tone = 'default',
  title,
}: {
  children: ReactNode
  tone?: 'default' | 'accent' | 'success' | 'danger' | 'muted'
  title?: string
}) {
  return (
    <span className={cx('tag', `tag-${tone}`)} title={title}>
      {children}
    </span>
  )
}

export function Spinner({ size = 14 }: { size?: number }) {
  return <span className="spinner" style={{ width: size, height: size }} aria-hidden="true" />
}

export function Skeleton({
  lines = 3,
  className,
  variant = 'line',
}: {
  lines?: number
  className?: string
  variant?: 'line' | 'card' | 'block'
}) {
  if (variant === 'card') {
    return (
      <div className={cx('skeleton-card', className)} aria-hidden="true">
        <div className="skeleton skeleton-image" />
        <div className="skeleton skeleton-line" />
        <div className="skeleton skeleton-line short" />
      </div>
    )
  }
  if (variant === 'block') {
    return <div className={cx('skeleton skeleton-block', className)} aria-hidden="true" />
  }
  return (
    <div className={cx('skeleton-lines', className)} aria-hidden="true">
      {Array.from({ length: lines }, (_, index) => (
        <div
          key={index}
          className={cx('skeleton', 'skeleton-line', index === lines - 1 && 'short')}
        />
      ))}
    </div>
  )
}

export function EmptyState({
  icon = 'folder',
  title,
  description,
  action,
  compact = false,
}: {
  icon?: IconName
  title: string
  description?: string
  action?: ReactNode
  compact?: boolean
}) {
  return (
    <div className={cx('empty-state', compact && 'empty-state-compact')}>
      <div className="empty-icon">
        <Icon name={icon} size={20} />
      </div>
      <h3>{title}</h3>
      {description && <p>{description}</p>}
      {action && <div className="empty-action">{action}</div>}
    </div>
  )
}

export function ErrorBanner({
  message,
  onRetry,
  onDismiss,
}: {
  message: string
  onRetry?: () => void
  onDismiss?: () => void
}) {
  const { t } = useI18n()
  return (
    <div className="error-banner" role="alert">
      <Icon name="alert" size={14} />
      <span>{message}</span>
      <div className="error-banner-actions">
        {onRetry && (
          <button type="button" className="text-button" onClick={onRetry}>
            {t('common.retry')}
          </button>
        )}
        {onDismiss && (
          <button
            type="button"
            className="icon-button"
            onClick={onDismiss}
            aria-label={t('component.dismissError')}
          >
            <Icon name="x" size={12} />
          </button>
        )}
      </div>
    </div>
  )
}

export function ViewHeader({
  eyebrow,
  title,
  description,
  actions,
  back,
}: {
  eyebrow: string
  title: string
  description?: string
  actions?: ReactNode
  back?: { label: string; onClick: () => void }
}) {
  return (
    <header className="view-header">
      <div className="view-heading">
        {back && (
          <button type="button" className="back-link" onClick={back.onClick}>
            <Icon name="arrow-left" size={12} />
            {back.label}
          </button>
        )}
        <MicroLabel>{eyebrow}</MicroLabel>
        <h1>{title}</h1>
        {description && <p>{description}</p>}
      </div>
      {actions && <div className="view-actions">{actions}</div>}
    </header>
  )
}
