import { AlertCircle, ArrowLeft, type LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link } from 'react-router'

export function Card({
  title,
  icon: Icon,
  actions,
  children,
  className = '',
  highlight = false,
}: {
  title?: string
  icon?: LucideIcon
  actions?: ReactNode
  children: ReactNode
  className?: string
  /** Emphasise the card (e.g. the item being edited). */
  highlight?: boolean
}) {
  return (
    <section
      className={`rounded-2xl border bg-surface p-4 shadow-card sm:p-5 ${
        highlight ? 'border-transparent ring-2 ring-ring' : 'border-line'
      } ${className}`}
    >
      {(title || actions) && (
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
          {title && (
            <h2 className="flex items-center gap-2 text-base font-semibold">
              {Icon && <Icon className="size-5 text-brand" aria-hidden />}
              {title}
            </h2>
          )}
          {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
        </div>
      )}
      {children}
    </section>
  )
}

export function ErrorBanner({ message }: { message: string | null }) {
  if (!message) return null
  return (
    <p role="alert" className="flex items-start gap-2 rounded-xl bg-danger-soft p-3 text-sm text-danger">
      <AlertCircle className="mt-0.5 size-4 shrink-0" aria-hidden />
      <span>{message}</span>
    </p>
  )
}

export function PageHeader({
  title,
  description,
  icon: Icon,
  backTo,
  backLabel = 'Back',
  actions,
  children,
}: {
  title: ReactNode
  description?: ReactNode
  icon?: LucideIcon
  backTo?: string
  backLabel?: string
  actions?: ReactNode
  /** Extra line under the title (badges etc.). */
  children?: ReactNode
}) {
  return (
    <header className="space-y-3">
      {backTo && (
        <Link
          to={backTo}
          className="inline-flex items-center gap-1.5 rounded-lg py-1 pr-2 text-sm font-medium text-muted hover:text-ink"
        >
          <ArrowLeft className="size-4" aria-hidden />
          {backLabel}
        </Link>
      )}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex min-w-0 items-start gap-3">
          {Icon && (
            <span className="bg-brand-gradient hidden size-11 shrink-0 place-items-center rounded-2xl text-white shadow-sm shadow-indigo-500/25 sm:grid">
              <Icon className="size-5" aria-hidden />
            </span>
          )}
          <div className="min-w-0">
            <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
            {description && <p className="mt-1 text-sm text-muted">{description}</p>}
            {children && <div className="mt-2 flex flex-wrap items-center gap-2">{children}</div>}
          </div>
        </div>
        {actions && <div className="flex w-full flex-wrap gap-2 sm:w-auto">{actions}</div>}
      </div>
    </header>
  )
}

export function EmptyState({
  icon: Icon,
  title,
  text,
  action,
}: {
  icon: LucideIcon
  title: string
  text?: string
  action?: ReactNode
}) {
  return (
    <div className="flex flex-col items-center px-4 py-10 text-center">
      <span className="grid size-14 place-items-center rounded-2xl bg-brand-soft text-brand">
        <Icon className="size-7" aria-hidden />
      </span>
      <p className="mt-4 font-medium">{title}</p>
      {text && <p className="mt-1 max-w-sm text-sm text-muted">{text}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  )
}

/** Small uppercase label used above groups of fields or list sections. */
export function SectionLabel({ children }: { children: ReactNode }) {
  return <p className="text-xs font-semibold tracking-wide text-muted uppercase">{children}</p>
}
