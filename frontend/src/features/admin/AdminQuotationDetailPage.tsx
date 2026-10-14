import {
  Calculator,
  CheckCircle2,
  FileDown,
  FileText,
  Mail,
  MapPin,
  MessageSquare,
  Package,
  PackagePlus,
  Phone,
  Store,
  UserRound,
  X,
  XCircle,
} from 'lucide-react'
import { useState } from 'react'
import { useLoaderData, useRevalidator } from 'react-router'

import { adminApi } from '../../api/admin'
import { Badge, QuotationStatusBadge } from '../../components/ui/Badge'
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
  const who = q.walk_in ? 'client' : 'customer'

  return (
    <>
      <PageHeader
        backTo="/admin/quotations"
        backLabel="All quotations"
        title={q.number ?? 'Quotation request'}
        icon={FileText}
        description={
          <>
            {q.walk_in ? `Created ${formatDate(q.created_at)} by ${q.created_by_email}` : `Requested ${formatDate(q.created_at)}`}
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
        <Card title={`Note to ${who}`} icon={MessageSquare}>
          <p className="whitespace-pre-line text-sm">{q.review_note}</p>
        </Card>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <Card title={q.walk_in ? 'Client' : 'Customer'} icon={UserRound}>
          <ul className="space-y-2 text-sm">
            <li className="flex flex-wrap items-center gap-2 font-medium">
              {q.customer.full_name}
              {q.walk_in && (
                <Badge tone="brand" icon={Store}>
                  Walk-in · no account
                </Badge>
              )}
            </li>
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
            {q.customer.email && (
              <li className="flex items-center gap-2 text-muted">
                <Mail className="size-4 shrink-0" aria-hidden />
                <a href={`mailto:${q.customer.email}`} className="truncate text-brand hover:underline">
                  {q.customer.email}
                </a>
              </li>
            )}
          </ul>
        </Card>
        <Card title="Request" icon={Package}>
          <ul className="space-y-2 text-sm">
            <li className="font-medium">{q.product_name}</li>
            {q.choices.map((c) => (
              <li key={c.group}>
                <span className="text-muted">{c.group}:</span> {c.name}
              </li>
            ))}
            {q.options.length > 0 && (
              <li className="flex items-center gap-1.5">
                <PackagePlus className="size-4 shrink-0 text-brand" aria-hidden />
                With: {q.options.join(', ')}
              </li>
            )}
            <li>
              {trimDecimal(q.input_width)} × {trimDecimal(q.input_height)} {q.input_unit}{' '}
              <span className="text-muted">
                ({q.width_mm} × {q.height_mm} mm)
              </span>
            </li>
            <li>Quantity {q.quantity}</li>
          </ul>
          <div className="bg-brand-gradient mt-4 flex items-center justify-between rounded-xl px-4 py-3 text-white">
            <span className="text-sm">
              Quoted amount
              {q.total_adjusted && <span className="block text-xs text-white/80">Adjusted from {money(b.rounded_total)}</span>}
            </span>
            <span className="text-lg font-semibold tabular-nums">{money(q.total)}</span>
          </div>
          <dl className="mt-3 space-y-1.5 text-sm tabular-nums">
            <div className="flex justify-between gap-4">
              <dt className="text-muted">50% downpayment</dt>
              <dd>{money(q.downpayment)}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-muted">50% upon completion and installation</dt>
              <dd>{money(q.balance)}</dd>
            </div>
          </dl>
        </Card>
      </div>

      <Card title="Internal cost breakdown" icon={Calculator}>
        <p className="mb-3 text-sm text-muted">
          Prices frozen when the quotation was processed. The {who} only sees the quoted amount (VAT included, not shown)
          and the 50/50 payment split.
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
                    {l.label || l.name} <span className="font-mono text-xs text-muted">{l.code}</span>{' '}
                    {l.option && (
                      <Badge tone="brand" icon={PackagePlus}>
                        {l.option}
                      </Badge>
                    )}
                  </td>
                  <td className="px-3 py-2 text-muted">
                    {BASIS_LABEL[l.basis]}
                    {l.width_mm !== null && (l.width_mm !== b.width_mm || l.height_mm !== b.height_mm) && (
                      <span className="block text-xs">
                        at {l.width_mm} × {l.height_mm} mm
                      </span>
                    )}
                  </td>
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
            ['Total incl. VAT', b.total],
            [`Rounded up to the next ${trimDecimal(b.rounding_step)}`, b.rounding],
          ].map(([label, value]) => (
            <div key={label} className="flex justify-between gap-4">
              <dt className="text-muted">{label}</dt>
              <dd>{money(value)}</dd>
            </div>
          ))}
          <div className="flex justify-between gap-4 border-t border-line pt-2 text-base font-semibold">
            <dt>Calculated price</dt>
            <dd>{money(b.rounded_total)}</dd>
          </div>
          {q.total_adjusted && (
            <div className="flex justify-between gap-4 text-base font-semibold text-brand">
              <dt>Adjusted on approval</dt>
              <dd>{money(q.total)}</dd>
            </div>
          )}
        </dl>
      </Card>

      <ReviewModal
        review={review}
        total={q.total}
        calculated={money(b.rounded_total)}
        customer={q.customer.full_name}
        walkIn={q.walk_in}
        onClose={() => setReview(null)}
        onSubmit={async (action, note, amount) => {
          if (action === 'approve') {
            const approved = await adminApi.approveQuotation(q.id, note, amount === q.total ? undefined : amount)
            toast.success(
              q.walk_in
                ? `Approved as ${approved.number}. Open the official PDF to print it for the client.`
                : `Approved as ${approved.number}. The customer can now print the official PDF.`,
            )
          } else {
            await adminApi.rejectQuotation(q.id, note)
            toast.success(q.walk_in ? 'Request rejected.' : 'Request rejected. The customer will see your note.')
          }
          setReview(null)
          revalidate()
        }}
      />
    </>
  )
}

const AMOUNT = /^\d{1,10}(\.\d{1,2})?$/

function ReviewModal({
  review,
  total,
  calculated,
  customer,
  walkIn,
  onClose,
  onSubmit,
}: {
  review: Review | null
  /** Current quoted amount, a decimal string like "21500.00" */
  total: string
  /** Formatted calculated (rounded-up) price, for the hint */
  calculated: string
  customer: string
  walkIn: boolean
  onClose: () => void
  onSubmit: (action: Review, note: string, amount: string) => Promise<void>
}) {
  const [note, setNote] = useState('')
  const [amount, setAmount] = useState(total)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const approving = review === 'approve'
  const who = walkIn ? 'client' : 'customer'

  function close() {
    setNote('')
    setAmount(total)
    setError(null)
    onClose()
  }

  async function submit() {
    if (!review) return
    if (!approving && note.trim().length < 3) {
      setError(`Please write a short note so the ${who} knows why.`)
      return
    }
    const finalAmount = amount.trim().replace(/,/g, '')
    if (approving && (!AMOUNT.test(finalAmount) || Number(finalAmount) <= 0)) {
      setError('Enter the final amount, like 21500 or 21500.50.')
      return
    }
    setBusy(true)
    setError(null)
    try {
      await onSubmit(review, note.trim(), finalAmount)
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
          ? `${customer} will get an official quotation with a quote number for the amount below.`
          : walkIn
            ? 'The request will be marked as rejected, with your note.'
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
        {approving && (
          <Field
            label="Final amount"
            htmlFor="review-amount"
            required
            hint={`Calculated price: ${calculated}. Change it to adjust the amount printed on the quotation.`}
          >
            <input
              id="review-amount"
              inputMode="decimal"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              className={`${inputClass} text-lg font-semibold tabular-nums`}
            />
          </Field>
        )}
        <Field
          label={approving ? `Note to ${who} (optional)` : 'Reason'}
          htmlFor="review-note"
          required={!approving}
          hint={approving ? 'Printed on the official PDF.' : 'e.g. “Size too large, please call us.”'}
        >
          <textarea
            id="review-note"
            autoFocus={!approving}
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
