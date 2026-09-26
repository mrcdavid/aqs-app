import { Plus } from 'lucide-react'
import { Link, useLoaderData } from 'react-router'

import { Card, PageHeader } from '../../components/ui/Card'
import { buttonClass } from '../../components/ui/Field'
import { QuotationStatusBadge } from '../../components/ui/QuotationStatusBadge'
import { formatDate, formatMoney } from '../../lib/format'
import type { quotationsLoader } from './loader'

export function QuotationsPage() {
  const { quotations } = useLoaderData<typeof quotationsLoader>()

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <PageHeader title="My quotations" description="Your requests and their approval status." />
        <Link to="/app/quotations/new" className={buttonClass}>
          <Plus className="size-4" aria-hidden />
          New quotation
        </Link>
      </div>

      <Card>
        {quotations.length === 0 ? (
          <div className="py-6 text-center">
            <p className="text-muted">You haven't requested a quotation yet.</p>
            <Link to="/app/quotations/new" className="mt-2 inline-block text-brand-600 hover:underline">
              Get your first quotation
            </Link>
          </div>
        ) : (
          <ul className="divide-y divide-brand-50">
            {quotations.map((q) => (
              <li key={q.id}>
                <Link
                  to={`/app/quotations/${q.id}`}
                  className="flex flex-wrap items-center gap-x-4 gap-y-1 rounded-lg px-2 py-3 hover:bg-brand-50"
                >
                  <div className="min-w-0 flex-1">
                    <p className="font-medium">{q.product_name}</p>
                    <p className="text-sm text-muted">
                      {q.width_mm} × {q.height_mm} mm · qty {q.quantity} · {formatDate(q.created_at)}
                      {q.number && <> · {q.number}</>}
                    </p>
                  </div>
                  <span className="font-medium tabular-nums">{formatMoney(q.total, q.currency)}</span>
                  <QuotationStatusBadge status={q.status} />
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  )
}
