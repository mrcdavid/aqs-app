import {
  Archive,
  Ban,
  CheckCircle2,
  Circle,
  Clock,
  Lock,
  Trash2,
  XCircle,
  type LucideIcon,
} from 'lucide-react'
import type { ReactNode } from 'react'

import type { QuotationStatus } from '../../api/quotations'

type Tone = 'success' | 'warning' | 'danger' | 'neutral' | 'brand'

const TONES: Record<Tone, string> = {
  success: 'bg-success-soft text-success',
  warning: 'bg-warning-soft text-warning',
  danger: 'bg-danger-soft text-danger',
  neutral: 'bg-surface-2 text-muted',
  brand: 'bg-brand-soft text-brand-soft-ink',
}

/** Status pill: always icon + text, never colour alone. */
export function Badge({ tone = 'neutral', icon: Icon, children }: { tone?: Tone; icon?: LucideIcon; children: ReactNode }) {
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap ${TONES[tone]}`}>
      {Icon && <Icon className="size-3.5" aria-hidden />}
      {children}
    </span>
  )
}

export function StatusBadge({ active }: { active: boolean }) {
  return active ? (
    <Badge tone="success" icon={CheckCircle2}>
      Active
    </Badge>
  ) : (
    <Badge tone="neutral" icon={Archive}>
      Archived
    </Badge>
  )
}

const QUOTATION: Record<QuotationStatus, { label: string; tone: Tone; icon: LucideIcon }> = {
  pending: { label: 'Pending approval', tone: 'warning', icon: Clock },
  approved: { label: 'Approved', tone: 'success', icon: CheckCircle2 },
  rejected: { label: 'Rejected', tone: 'danger', icon: XCircle },
  cancelled: { label: 'Cancelled', tone: 'neutral', icon: Ban },
}

export function QuotationStatusBadge({ status }: { status: QuotationStatus }) {
  const { label, tone, icon } = QUOTATION[status]
  return (
    <Badge tone={tone} icon={icon}>
      {label}
    </Badge>
  )
}

export function AccountBadge({
  deleted,
  active,
  locked,
}: {
  deleted: boolean
  active: boolean
  locked: boolean
}) {
  if (deleted)
    return (
      <Badge tone="neutral" icon={Trash2}>
        Deleted
      </Badge>
    )
  if (!active)
    return (
      <Badge tone="danger" icon={Ban}>
        Disabled
      </Badge>
    )
  if (locked)
    return (
      <Badge tone="warning" icon={Lock}>
        Locked
      </Badge>
    )
  return (
    <Badge tone="success" icon={CheckCircle2}>
      Active
    </Badge>
  )
}

export function OnlineDot() {
  return (
    <span className="inline-flex items-center gap-1 text-xs font-medium text-success">
      <Circle className="size-2 fill-current" aria-hidden />
      Online
    </span>
  )
}
