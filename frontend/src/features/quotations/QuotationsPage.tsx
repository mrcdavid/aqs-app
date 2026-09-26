import { ChevronRight, FilePlus2, FileText } from 'lucide-react'
import { Link, useLoaderData } from 'react-router'

import { QuotationStatusBadge } from '../../components/ui/Badge'
import { ButtonLink } from '../../components/ui/Button'
import { Card, EmptyState, PageHeader } from '../../components/ui/Card'
import { formatDate, formatMoney } from '../../lib/format'
import type { quotationsLoader } from './loader'

export function QuotationsPage() {
  const { quotations } = useLoaderData<typeof quotationsLoader>()

  return (
    <div className="space-y-6">
      <PageHeader
        title="My quotations"
        description="Your requests and their approval status."
        icon={FileText}
        actions={
          <ButtonLink to="/app/quotations/new" icon={FilePlus2} className="w-full sm:w-auto">
            New quotation
          </ButtonLink>
        }
      />

      <Card className="p-2 sm:p-2">
        {quotations.length === 0 ? (
          <EmptyState
            icon={FileText}
            title="No quotations yet"
            text="Pick a product, enter the size, and get an instant estimate."
            action={
              <ButtonLink to="/app/quotations/new" icon={FilePlus2}>
                Get your first quotation
              </ButtonLink>
            }
          />
        ) : (
          <ul className="divide-y divide-line">
            {quotations.map((q) => (
              <li key={q.id}>
                <Link to={`/app/quotations/${q.id}`} className="group flex items-center gap-3 rounded-xl px-3 py-3 hover:bg-surface-2/70 sm:gap-4">
                  <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-brand-soft text-brand">
                    <FileText className="size-5" aria-hidden />
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-medium">{q.product_name}</p>
                    <p className="truncate text-sm text-muted">
                      {q.width_mm} × {q.height_mm} mm · qty {q.quantity} · {formatDate(q.created_at)}
                    </p>
                    {q.number && <p className="font-mono text-xs text-muted">{q.number}</p>}
                  </div>
                  <div className="flex flex-col items-end gap-1.5">
                    <span className="font-semibold tabular-nums whitespace-nowrap">{formatMoney(q.total, q.currency)}</span>
                    <QuotationStatusBadge status={q.status} />
                  </div>
                  <ChevronRight className="hidden size-5 text-muted transition group-hover:translate-x-0.5 sm:block" aria-hidden />
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  )
}
