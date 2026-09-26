import {
  Calculator,
  CheckCircle2,
  FileDown,
  FileText,
  Mail,
  MapPin,
  MessageSquare,
  Package,
  Phone,
  UserRound,
  X,
  XCircle,
} from 'lucide-react'
import { useState } from 'react'
import { useLoaderData, useRevalidator } from 'react-router'

import { adminApi } from '../../api/admin'
import { QuotationStatusBadge } from '../../components/ui/Badge'
import { Button, ButtonAnchor } from '../../components/ui/Button'
import { Card, ErrorBanner, PageHeader } from '../../components/ui/Card'
import { Field, inputClass } from '../../components/ui/Field'
import { Modal } from '../../components/ui/Modal'
import { messageOf } from '../../lib/errors'
import { BASIS_LABEL, formatDate, formatMoney, trimDecimal, UNIT_LABEL } from '../../lib/format'
import { toast } from '../../stores/feedback'
import type { adminQuotationDetailLoader } from './loaders'

type Review = 'approve' | 'reject'

export function AdminQuotationDetailPage() {
  const { quotation: q } = useLoaderData<typeof adminQuotationDetailLoader>()
  const { revalidate } = useRevalidator()
  const [review, setReview] = useState<Review | null>(null)
  const money = (v: string) => formatMoney(v, q.currency)
  const b = q.breakdown
  const hasPdf = q.status === 'pending' || q.status === 'approved'

  return (
    <>
      <PageHeader
        backTo="/admin/quotations"
        backLabel="All quotations"
        title={q.number ?? 'Quotation request'}
        icon={FileText}
        description={
          <>
            Requested {formatDate(q.created_at)}
            {q.reviewed_at && ` · reviewed ${formatDate(q.reviewed_at)} by ${q.reviewed_by_email}`}
            {q.valid_until && ` · valid until ${formatDate(q.valid_until)}`}
          </>
        }
        actions={
          <>
            {hasPdf && (
              <ButtonAnchor
                href={adminApi.quotationPdfUrl(q.id)}
                target="_blank"
                rel="noopener"
                variant="secondary"
                icon={FileDown}
                className="flex-1 sm:flex-none"
              >
                {q.status === 'approved' ? 'Official PDF' : 'Draft PDF'}
              </ButtonAnchor>
            )}
            {q.status === 'pending' && (
              <>
                <Button variant="danger-soft" icon={XCircle} onClick={() => setReview('reject')} className="flex-1 sm:flex-none">
                  Reject
                </Button>
                <Button icon={CheckCircle2} onClick={() => setReview('approve')} className="flex-1 sm:flex-none">
                  Approve
                </Button>
              </>
            )}
          </>
        }
      >
        <QuotationStatusBadge status={q.status} />
      </PageHeader>

      {q.review_note && (
        <Card title="Note to customer" icon={MessageSquare}>
          <p className="whitespace-pre-line text-sm">{q.review_note}</p>
        </Card>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Customer" icon={UserRound}>
          <ul className="space-y-2 text-sm">
            <li className="font-medium">{q.customer.full_name}</li>
            <li className="flex items-start gap-2 text-muted">
              <MapPin className="mt-0.5 size-4 shrink-0" aria-hidden />
              <span className="text-ink">
                {q.customer.address_line}, {q.customer.city}, {q.customer.province}
              </span>
            </li>
            <li className="flex items-center gap-2 text-muted">
              <Phone className="size-4 shrink-0" aria-hidden />
              <a href={`tel:${q.customer.contact_number}`} className="text-ink hover:text-brand">
                {q.customer.contact_number}
              </a>
            </li>
            <li className="flex items-center gap-2 text-muted">
              <Mail className="size-4 shrink-0" aria-hidden />
              <a href={`mailto:${q.customer.email}`} className="truncate text-brand hover:underline">
                {q.customer.email}
              </a>
            </li>
          </ul>
        </Card>
        <Card title="Request" icon={Package}>
          <ul className="space-y-2 text-sm">
            <li className="font-medium">{q.product_name}</li>
            <li>
              {trimDecimal(q.input_width)} × {trimDecimal(q.input_height)} {q.input_unit}{' '}
              <span className="text-muted">
                ({q.width_mm} × {q.height_mm} mm)
              </span>
            </li>
            <li>Quantity {q.quantity}</li>
          </ul>
          <div className="bg-brand-gradient mt-4 flex items-center justify-between rounded-xl px-4 py-3 text-white">
            <span className="text-sm">Total incl. VAT</span>
            <span className="text-lg font-semibold tabular-nums">{money(q.total)}</span>
          </div>
        </Card>
      </div>

      <Card title="Internal cost breakdown" icon={Calculator}>
        <p className="mb-3 text-sm text-muted">
          Prices frozen when the customer clicked Process. The customer only sees the unit price, VAT and total.
        </p>
        <div className="overflow-x-auto rounded-xl border border-line">
          <table className="w-full text-left text-sm tabular-nums">
            <thead className="bg-surface-2 text-xs tracking-wide text-muted uppercase">
              <tr>
                <th className="px-3 py-2 font-medium">Line</th>
                <th className="px-3 py-2 font-medium">Measured by</th>
                <th className="px-3 py-2 text-right font-medium">Qty</th>
                <th className="px-3 py-2 text-right font-medium">Price</th>
                <th className="px-3 py-2 text-right font-medium">Cost</th>
              </tr>
            </thead>
            <tbody>
              {b.lines.map((l, i) => (
                <tr key={i} className="border-t border-line">
                  <td className="px-3 py-2">
                    {l.label || l.name} <span className="font-mono text-xs text-muted">{l.code}</span>
                  </td>
                  <td className="px-3 py-2 text-muted">{BASIS_LABEL[l.basis]}</td>
                  <td className="px-3 py-2 text-right">{trimDecimal(l.quantity)}</td>
                  <td className="px-3 py-2 text-right whitespace-nowrap">
                    {money(l.unit_price)} <span className="text-muted">{UNIT_LABEL[l.unit]}</span>
                  </td>
                  <td className="px-3 py-2 text-right">{money(l.cost)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <dl className="mt-4 ml-auto max-w-sm space-y-1.5 text-sm tabular-nums">
          {[
            ['Cost per piece', b.unit_subtotal],
            [`Customer unit price (+${trimDecimal(b.markup_percent)}% markup)`, b.unit_price],
            [`Cost × ${b.quantity}`, b.subtotal],
            ['Markup', b.markup],
            [`Subtotal (unit price × ${b.quantity})`, b.net],
            [`VAT ${trimDecimal(b.vat_percent)}%`, b.vat],
          ].map(([label, value]) => (
            <div key={label} className="flex justify-between gap-4">
              <dt className="text-muted">{label}</dt>
              <dd>{money(value)}</dd>
            </div>
          ))}
          <div className="flex justify-between gap-4 border-t border-line pt-2 text-base font-semibold">
            <dt>Total</dt>
            <dd>{money(b.total)}</dd>
          </div>
        </dl>
      </Card>

      <ReviewModal
        review={review}
        total={money(q.total)}
        customer={q.customer.full_name}
        onClose={() => setReview(null)}
        onSubmit={async (action, note) => {
          if (action === 'approve') {
            const approved = await adminApi.approveQuotation(q.id, note)
            toast.success(`Approved as ${approved.number}. The customer can now print the official PDF.`)
          } else {
            await adminApi.rejectQuotation(q.id, note)
            toast.success('Request rejected. The customer will see your note.')
          }
          setReview(null)
          revalidate()
        }}
      />
    </>
  )
}

function ReviewModal({
  review,
  total,
  customer,
  onClose,
  onSubmit,
}: {
  review: Review | null
  total: string
  customer: string
  onClose: () => void
  onSubmit: (action: Review, note: string) => Promise<void>
}) {
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const approving = review === 'approve'

  function close() {
    setNote('')
    setError(null)
    onClose()
  }

  async function submit() {
    if (!review) return
    if (!approving && note.trim().length < 3) {
      setError('Please write a short note so the customer knows why.')
      return
    }
    setBusy(true)
    setError(null)
    try {
      await onSubmit(review, note.trim())
      setNote('')
    } catch (err) {
      setError(messageOf(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal
      open={review !== null}
      onClose={close}
      icon={approving ? CheckCircle2 : XCircle}
      tone={approving ? 'success' : 'danger'}
      title={approving ? 'Approve and issue quotation' : 'Reject this request'}
      description={
        approving
          ? `${customer} will get an official quotation for ${total} with a quote number.`
          : `${customer} will see the request as rejected, with your note.`
      }
      footer={
        <>
          <Button variant="secondary" icon={X} onClick={close}>
            Cancel
          </Button>
          <Button variant={approving ? 'primary' : 'danger'} icon={approving ? CheckCircle2 : XCircle} loading={busy} onClick={submit}>
            {approving ? 'Approve' : 'Reject request'}
          </Button>
        </>
      }
    >
      <div className="space-y-3">
        <ErrorBanner message={error} />
        <Field
          label={approving ? 'Note to customer (optional)' : 'Reason (required)'}
          htmlFor="review-note"
          hint={approving ? 'Printed on the official PDF.' : 'e.g. “Size too large, please call us.”'}
        >
          <textarea
            id="review-note"
            autoFocus
            rows={4}
            maxLength={1000}
            value={note}
            onChange={(e) => setNote(e.target.value)}
            className={inputClass}
          />
        </Field>
      </div>
    </Modal>
  )
}
