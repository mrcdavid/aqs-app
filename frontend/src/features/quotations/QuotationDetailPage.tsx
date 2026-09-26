import { ArrowLeft, FileText } from 'lucide-react'
import { useState } from 'react'
import { Link, useLoaderData, useRevalidator } from 'react-router'

import { quotationsApi } from '../../api/quotations'
import { Card, ErrorBanner } from '../../components/ui/Card'
import { buttonClass, linkButtonClass, secondaryButtonClass } from '../../components/ui/Field'
import { QuotationStatusBadge } from '../../components/ui/QuotationStatusBadge'
import { messageOf } from '../../lib/errors'
import { formatDate, formatMoney, trimDecimal } from '../../lib/format'
import type { quotationDetailLoader } from './loader'

const STATUS_TEXT = {
  pending: 'Your estimate is ready. Our team will review it and issue the official quotation.',
  approved: 'Your quotation has been approved. You can view and print the official PDF.',
  rejected: 'This request was not approved. See the note below.',
  cancelled: 'You cancelled this request.',
} as const

export function QuotationDetailPage() {
  const { quotation: q } = useLoaderData<typeof quotationDetailLoader>()
  const { revalidate } = useRevalidator()
  const [error, setError] = useState<string | null>(null)
  const money = (v: string) => formatMoney(v, q.currency)
  const hasPdf = q.status === 'pending' || q.status === 'approved'

  async function cancel() {
    if (!window.confirm('Cancel this quotation request?')) return
    setError(null)
    try {
      await quotationsApi.cancel(q.id)
      revalidate()
    } catch (err) {
      setError(messageOf(err))
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <Link to="/app/quotations" className={linkButtonClass}>
          <ArrowLeft className="size-4" aria-hidden />
          My quotations
        </Link>
        <div className="mt-2 flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-semibold">{q.number ?? 'Estimate'}</h1>
          <QuotationStatusBadge status={q.status} />
        </div>
        <p className="mt-1 text-muted">{STATUS_TEXT[q.status]}</p>
      </div>

      <ErrorBanner message={error} />

      {q.review_note && (
        <Card title="Note from our team">
          <p className="whitespace-pre-line">{q.review_note}</p>
        </Card>
      )}

      <Card>
        <div className="space-y-4">
          <div>
            <h2 className="text-lg font-semibold">{q.product_name}</h2>
            {q.product_description && <p className="text-sm text-muted">{q.product_description}</p>}
            <p className="mt-1 text-sm text-muted">Includes: {q.includes.join(', ')}</p>
          </div>

          <dl className="grid gap-3 text-sm sm:grid-cols-3">
            <div>
              <dt className="text-muted">Size</dt>
              <dd>
                {trimDecimal(q.input_width)} × {trimDecimal(q.input_height)} {q.input_unit}{' '}
                <span className="text-muted">
                  ({q.width_mm} × {q.height_mm} mm)
                </span>
              </dd>
            </div>
            <div>
              <dt className="text-muted">Requested</dt>
              <dd>{formatDate(q.created_at)}</dd>
            </div>
            <div>
              <dt className="text-muted">Valid until</dt>
              <dd>{q.valid_until ? formatDate(q.valid_until) : 'Set on approval'}</dd>
            </div>
          </dl>

          <table className="w-full text-sm tabular-nums">
            <tbody>
              <tr className="border-t border-brand-50">
                <td className="py-2">Unit price × {q.quantity}</td>
                <td className="py-2 text-right">
                  {money(q.unit_price)} × {q.quantity}
                </td>
              </tr>
              <tr className="border-t border-brand-50">
                <td className="py-2">Subtotal</td>
                <td className="py-2 text-right">{money(q.amount)}</td>
              </tr>
              <tr className="border-t border-brand-50">
                <td className="py-2">VAT {trimDecimal(q.vat_percent)}%</td>
                <td className="py-2 text-right">{money(q.vat)}</td>
              </tr>
              <tr className="border-t-2 border-ink text-base font-semibold">
                <td className="py-2">Total</td>
                <td className="py-2 text-right">{money(q.total)}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </Card>

      <div className="flex flex-wrap gap-3">
        {hasPdf && (
          <a href={quotationsApi.pdfUrl(q.id)} target="_blank" rel="noopener" className={buttonClass}>
            <FileText className="size-4" aria-hidden />
            {q.status === 'approved' ? 'View / print quotation PDF' : 'View / print estimate PDF'}
          </a>
        )}
        {q.can_cancel && (
          <button type="button" onClick={cancel} className={secondaryButtonClass}>
            Cancel request
          </button>
        )}
      </div>
    </div>
  )
}
