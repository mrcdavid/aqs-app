import { Link, NavLink, useLoaderData } from 'react-router'

import { Card, PageHeader } from '../../components/ui/Card'
import { QuotationStatusBadge } from '../../components/ui/QuotationStatusBadge'
import { formatDate, formatMoney } from '../../lib/format'
import type { adminQuotationsLoader } from './loaders'

const TABS = [
  { status: 'pending', label: 'Pending' },
  { status: 'approved', label: 'Approved' },
  { status: 'rejected', label: 'Rejected' },
  { status: 'cancelled', label: 'Cancelled' },
  { status: 'all', label: 'All' },
] as const

export function AdminQuotationsPage() {
  const { status, quotations } = useLoaderData<typeof adminQuotationsLoader>()

  return (
    <>
      <PageHeader title="Quotations" description="Review customer requests and issue official quotations." />

      <nav aria-label="Filter by status" className="flex gap-1 overflow-x-auto">
        {TABS.map((t) => (
          <NavLink
            key={t.status}
            to={`/admin/quotations?status=${t.status}`}
            className={`whitespace-nowrap rounded-lg px-3 py-1.5 text-sm ${
              status === t.status ? 'bg-brand-600 text-white' : 'bg-white hover:bg-brand-100'
            }`}
          >
            {t.label}
          </NavLink>
        ))}
      </nav>

      <Card>
        {quotations.length === 0 ? (
          <p className="text-muted">No quotations here.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-brand-100 text-muted">
                <tr>
                  <th className="py-2 pr-4 font-medium">Requested</th>
                  <th className="py-2 pr-4 font-medium">Customer</th>
                  <th className="py-2 pr-4 font-medium">Product</th>
                  <th className="py-2 pr-4 text-right font-medium">Total</th>
                  <th className="py-2 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {quotations.map((q) => (
                  <tr key={q.id} className="border-b border-brand-50 last:border-0 hover:bg-brand-50">
                    <td className="py-2 pr-4 whitespace-nowrap">
                      <Link to={`/admin/quotations/${q.id}`} className="text-brand-600 hover:underline">
                        {formatDate(q.created_at)}
                      </Link>
                      {q.number && <div className="font-mono text-xs text-muted">{q.number}</div>}
                    </td>
                    <td className="py-2 pr-4">
                      <div>{q.customer_name}</div>
                      <div className="text-xs text-muted">
                        {q.customer_city}, {q.customer_province}
                      </div>
                    </td>
                    <td className="py-2 pr-4">
                      <div>{q.product_name}</div>
                      <div className="text-xs text-muted">
                        {q.width_mm} × {q.height_mm} mm · qty {q.quantity}
                      </div>
                    </td>
                    <td className="py-2 pr-4 text-right tabular-nums whitespace-nowrap">
                      {formatMoney(q.total, q.currency)}
                    </td>
                    <td className="py-2">
                      <QuotationStatusBadge status={q.status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </>
  )
}
