import { Ban, CheckCircle2, ChevronRight, Clock, FilePlus2, FileText, Inbox, Layers, MapPin, Store, XCircle } from 'lucide-react'
import { Link, useLoaderData } from 'react-router'

import { Badge, QuotationStatusBadge } from '../../components/ui/Badge'
import { ButtonLink } from '../../components/ui/Button'
import { Card, EmptyState, PageHeader } from '../../components/ui/Card'
import { formatDate, formatMoney, itemsDetail, itemsTitle } from '../../lib/format'
import type { adminQuotationsLoader } from './loaders'

const TABS = [
  { status: 'pending', label: 'Pending', icon: Clock },
  { status: 'approved', label: 'Approved', icon: CheckCircle2 },
  { status: 'rejected', label: 'Rejected', icon: XCircle },
  { status: 'cancelled', label: 'Cancelled', icon: Ban },
  { status: 'all', label: 'All', icon: Layers },
] as const

export function AdminQuotationsPage() {
  const { status, quotations } = useLoaderData<typeof adminQuotationsLoader>()

  return (
    <>
      <PageHeader
        title="Quotations"
        description="Review customer requests, quote walk-in clients, and issue official quotations."
        icon={FileText}
        actions={
          <ButtonLink to="/admin/quotations/new" icon={FilePlus2} className="flex-1 sm:flex-none">
            New quotation
          </ButtonLink>
        }
      />

      <nav aria-label="Filter by status" className="-mx-1 flex gap-2 overflow-x-auto px-1 pb-1 [scrollbar-width:none]">
        {TABS.map(({ status: s, label, icon: Icon }) => (
          <Link
            key={s}
            to={`/admin/quotations?status=${s}`}
            aria-current={status === s ? 'page' : undefined}
            className={`inline-flex shrink-0 items-center gap-1.5 rounded-full px-3.5 py-2 text-sm font-medium transition ${
              status === s
                ? 'bg-brand-gradient text-white shadow-sm shadow-indigo-500/25'
                : 'border border-line bg-surface text-muted hover:text-ink'
            }`}
          >
            <Icon className="size-4" aria-hidden />
            {label}
          </Link>
        ))}
      </nav>

      <Card className="p-2 sm:p-2">
        {quotations.length === 0 ? (
          <EmptyState
            icon={Inbox}
            title={status === 'pending' ? 'Nothing waiting for review' : 'No quotations here'}
            text={status === 'pending' ? 'New customer requests and walk-in quotations will appear here.' : undefined}
          />
        ) : (
          <ul className="divide-y divide-line">
            {quotations.map((q) => (
              <li key={q.id}>
                <Link
                  to={`/admin/quotations/${q.id}`}
                  className="group flex items-center gap-3 rounded-xl px-3 py-3 hover:bg-surface-2/70 sm:gap-4"
                >
                  <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-brand-soft text-brand">
                    <FileText className="size-5" aria-hidden />
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                      <span className="font-medium">{q.customer_name}</span>
                      {q.walk_in && (
                        <Badge tone="brand" icon={Store}>
                          Walk-in
                        </Badge>
                      )}
                      {q.number && <span className="font-mono text-xs text-muted">{q.number}</span>}
                    </div>
                    <p className="truncate text-sm text-muted">
                      {itemsTitle(q.items)} · {itemsDetail(q.items)}
                    </p>
                    <p className="mt-0.5 flex flex-wrap items-center gap-x-3 text-xs text-muted">
                      <span className="inline-flex items-center gap-1">
                        <MapPin className="size-3.5" aria-hidden />
                        {q.customer_city}, {q.customer_province}
                      </span>
                      <span>{formatDate(q.created_at)}</span>
                    </p>
                  </div>
                  <div className="flex flex-col items-end gap-1.5">
                    <span className="font-semibold tabular-nums whitespace-nowrap">{formatMoney(q.total, q.currency)}</span>
                    <QuotationStatusBadge status={q.status} />
                  </div>
                  <ChevronRight className="hidden size-5 shrink-0 text-muted transition group-hover:translate-x-0.5 sm:block" aria-hidden />
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </>
  )
}
