import { ArrowLeft, Check, FileText, X } from 'lucide-react'
import { useState } from 'react'
import { Link, useLoaderData, useRevalidator } from 'react-router'

import { adminApi } from '../../api/admin'
import { Card, ErrorBanner } from '../../components/ui/Card'
import { buttonClass, Field, inputClass, linkButtonClass, secondaryButtonClass } from '../../components/ui/Field'
import { QuotationStatusBadge } from '../../components/ui/QuotationStatusBadge'
import { messageOf } from '../../lib/errors'
import { BASIS_LABEL, formatDate, formatMoney, trimDecimal, UNIT_LABEL } from '../../lib/format'
import type { adminQuotationDetailLoader } from './loaders'

export function AdminQuotationDetailPage() {
  const { quotation: q } = useLoaderData<typeof adminQuotationDetailLoader>()
  const { revalidate } = useRevalidator()
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const money = (v: string) => formatMoney(v, q.currency)
  const b = q.breakdown

  async function review(action: 'approve' | 'reject') {
    if (action === 'reject' && note.trim().length < 3) {
      setError('Please write a short note explaining why this request is rejected.')
      return
    }
    const question =
      action === 'approve'
        ? `Approve and issue the official quotation for ${money(q.total)}?`
        : 'Reject this request? The customer will see your note.'
    if (!window.confirm(question)) return
    setBusy(true)
    setError(null)
    try {
      if (action === 'approve') await adminApi.approveQuotation(q.id, note.trim())
      else await adminApi.rejectQuotation(q.id, note.trim())
      setNote('')
      revalidate()
    } catch (err) {
      setError(messageOf(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <div>
        <Link to="/admin/quotations" className={linkButtonClass}>
          <ArrowLeft className="size-4" aria-hidden />
          All quotations
        </Link>
        <div className="mt-2 flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-semibold">{q.number ?? 'Quotation request'}</h1>
          <QuotationStatusBadge status={q.status} />
        </div>
        <p className="text-sm text-muted">
          Requested {formatDate(q.created_at)}
          {q.reviewed_at && (
            <>
              {' '}
              · reviewed {formatDate(q.reviewed_at)} by {q.reviewed_by_email}
            </>
          )}
          {q.valid_until && <> · valid until {formatDate(q.valid_until)}</>}
        </p>
      </div>

      <ErrorBanner message={error} />

      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Customer">
          <dl className="space-y-1 text-sm">
            <dd className="font-medium">{q.customer.full_name}</dd>
            <dd>{q.customer.address_line}</dd>
            <dd>
              {q.customer.city}, {q.customer.province}
            </dd>
            <dd>{q.customer.contact_number}</dd>
            <dd>
              <a href={`mailto:${q.customer.email}`} className="text-brand-600 hover:underline">
                {q.customer.email}
              </a>
            </dd>
          </dl>
        </Card>
        <Card title="Request">
          <dl className="space-y-1 text-sm">
            <dd className="font-medium">{q.product_name}</dd>
            <dd>
              {trimDecimal(q.input_width)} × {trimDecimal(q.input_height)} {q.input_unit} ({q.width_mm} ×{' '}
              {q.height_mm} mm)
            </dd>
            <dd>Quantity {q.quantity}</dd>
            <dd className="pt-2 text-base font-semibold">Total {money(q.total)}</dd>
          </dl>
        </Card>
      </div>

      <Card title="Internal cost breakdown">
        <p className="mb-3 text-sm text-muted">
          Prices frozen when the customer clicked Process. The customer only sees the unit price, VAT
          and total.
        </p>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm tabular-nums">
            <thead className="border-b border-brand-100 text-muted">
              <tr>
                <th className="py-2 pr-4 font-medium">Line</th>
                <th className="py-2 pr-4 font-medium">Measured by</th>
                <th className="py-2 pr-4 text-right font-medium">Qty</th>
                <th className="py-2 pr-4 text-right font-medium">Price</th>
                <th className="py-2 text-right font-medium">Cost</th>
              </tr>
            </thead>
            <tbody>
              {b.lines.map((l, i) => (
                <tr key={i} className="border-b border-brand-50">
                  <td className="py-2 pr-4">
                    {l.label || l.name} <span className="font-mono text-xs text-muted">{l.code}</span>
                  </td>
                  <td className="py-2 pr-4">{BASIS_LABEL[l.basis]}</td>
                  <td className="py-2 pr-4 text-right">{trimDecimal(l.quantity)}</td>
                  <td className="py-2 pr-4 text-right whitespace-nowrap">
                    {money(l.unit_price)} <span className="text-muted">{UNIT_LABEL[l.unit]}</span>
                  </td>
                  <td className="py-2 text-right">{money(l.cost)}</td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              {[
                ['Cost per piece', b.unit_subtotal],
                [`Customer unit price (+${trimDecimal(b.markup_percent)}% markup)`, b.unit_price],
                [`Cost × ${b.quantity}`, b.subtotal],
                ['Markup', b.markup],
                [`Subtotal (unit price × ${b.quantity})`, b.net],
                [`VAT ${trimDecimal(b.vat_percent)}%`, b.vat],
                ['Total', b.total],
              ].map(([label, value]) => (
                <tr key={label} className={label === 'Total' ? 'text-base font-semibold' : ''}>
                  <td colSpan={4} className="py-1 pr-4 text-right">
                    {label}
                  </td>
                  <td className="py-1 text-right">{money(value)}</td>
                </tr>
              ))}
            </tfoot>
          </table>
        </div>
      </Card>

      {q.review_note && (
        <Card title="Note to customer">
          <p className="whitespace-pre-line">{q.review_note}</p>
        </Card>
      )}

      {q.status === 'pending' && (
        <Card title="Review">
          <div className="space-y-4">
            <Field
              label="Note to customer"
              htmlFor="note"
              hint="Optional when approving (printed on the PDF). Required when rejecting."
            >
              <textarea
                id="note"
                rows={3}
                maxLength={1000}
                value={note}
                onChange={(e) => setNote(e.target.value)}
                className={inputClass}
              />
            </Field>
            <div className="flex flex-wrap gap-3">
              <button type="button" disabled={busy} onClick={() => review('approve')} className={buttonClass}>
                <Check className="size-4" aria-hidden />
                Approve and issue quotation
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => review('reject')}
                className={`${secondaryButtonClass} text-red-700`}
              >
                <X className="size-4" aria-hidden />
                Reject
              </button>
            </div>
          </div>
        </Card>
      )}

      {(q.status === 'pending' || q.status === 'approved') && (
        <div>
          <a href={adminApi.quotationPdfUrl(q.id)} target="_blank" rel="noopener" className={secondaryButtonClass}>
            <FileText className="size-4" aria-hidden />
            {q.status === 'approved' ? 'Official PDF' : 'Draft PDF (what the customer sees)'}
          </a>
        </div>
      )}
    </>
  )
}
