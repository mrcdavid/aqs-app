import {
  Ban,
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
  Trash2,
  UserRound,
  X,
  XCircle,
} from 'lucide-react'
import { useState } from 'react'
import { useLoaderData, useNavigate, useRevalidator } from 'react-router'

import { adminApi, type AdminQuotationItem } from '../../api/admin'
import { Badge, QuotationStatusBadge } from '../../components/ui/Badge'
import { Button, ButtonAnchor } from '../../components/ui/Button'
import { Card, ErrorBanner, PageHeader } from '../../components/ui/Card'
import { Field, inputClass } from '../../components/ui/Field'
import { Modal } from '../../components/ui/Modal'
import { messageOf } from '../../lib/errors'
import { BASIS_LABEL, formatDate, formatMoney, trimDecimal, UNIT_LABEL } from '../../lib/format'
import { confirmAction, toast } from '../../stores/feedback'
import type { adminQuotationDetailLoader } from './loaders'

type Review = 'approve' | 'reject' | 'cancel'

export function AdminQuotationDetailPage() {
  const { quotation: q, me } = useLoaderData<typeof adminQuotationDetailLoader>()
  const { revalidate } = useRevalidator()
  const navigate = useNavigate()
  const [review, setReview] = useState<Review | null>(null)
  const [deleting, setDeleting] = useState(false)
  const money = (v: string) => formatMoney(v, q.currency)
  const hasPdf = q.status === 'pending' || q.status === 'approved'
  const who = q.walk_in ? 'client' : 'customer'

  async function remove() {
    const ok = await confirmAction({
      title: 'Delete this quotation?',
      message: `${q.number ?? 'This request'} for ${q.customer.full_name} (${q.status}) will disappear from every list, the dashboard${
        q.walk_in ? '' : " and the customer's account"
      }. It stays in the database and the audit log.`,
      confirmLabel: 'Yes, delete it',
      cancelLabel: 'No',
      tone: 'danger',
    })
    if (!ok) return
    setDeleting(true)
    try {
      await adminApi.deleteQuotation(q.id)
      toast.success('Quotation deleted.')
      navigate('/admin/quotations')
    } catch (err) {
      toast.error(messageOf(err))
      setDeleting(false)
    }
  }

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
            {q.reviewed_at && ` · ${q.status} ${formatDate(q.reviewed_at)} by ${q.reviewed_by_email}`}
            {q.status === 'cancelled' && !q.reviewed_at && ` · cancelled by the customer`}
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
            {me.role === 'super_admin' && (
              <Button variant="danger-soft" icon={Trash2} loading={deleting} onClick={remove} className="flex-1 sm:flex-none">
                Delete
              </Button>
            )}
            {q.status === 'pending' && (
              <>
                <Button variant="secondary" icon={Ban} onClick={() => setReview('cancel')} className="flex-1 sm:flex-none">
                  Cancel
                </Button>
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
        <Card title={q.items.length === 1 ? 'Item' : `Items (${q.items.length})`} icon={Package}>
          <ol className="space-y-3 text-sm">
            {q.items.map((item, i) => (
              <li key={item.position} className="flex gap-3">
                <span className="grid size-6 shrink-0 place-items-center rounded-full bg-brand-soft text-xs font-semibold text-brand">
                  {i + 1}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex justify-between gap-3">
                    <span className="font-medium">{item.product_name}</span>
                    <span className="font-medium tabular-nums">{money(item.amount)}</span>
                  </div>
                  <p className="text-muted">
                    {trimDecimal(item.input_width)} × {trimDecimal(item.input_height)} {item.input_unit} ({item.width_mm} ×{' '}
                    {item.height_mm} mm) · qty {item.quantity}
                  </p>
                  {item.choices.map((c) => (
                    <p key={c.group}>
                      <span className="text-muted">{c.group}:</span> {c.name}
                    </p>
                  ))}
                  {item.options.length > 0 && (
                    <p className="flex items-center gap-1.5">
                      <PackagePlus className="size-4 shrink-0 text-brand" aria-hidden />
                      With: {item.options.join(', ')}
                    </p>
                  )}
                </div>
              </li>
            ))}
          </ol>
          {q.total_adjusted && (
            <dl className="mt-4 space-y-1 border-t border-line pt-3 text-sm tabular-nums">
              <div className="flex justify-between gap-4">
                <dt className="text-muted">Items total</dt>
                <dd>{money(q.subtotal)}</dd>
              </div>
              <div className="flex justify-between gap-4">
                <dt className="text-muted">Adjusted on approval</dt>
                <dd>
                  {Number(q.adjustment) > 0 ? '+ ' : '- '}
                  {money(q.adjustment.replace('-', ''))}
                </dd>
              </div>
            </dl>
          )}
          <div className="bg-brand-gradient mt-4 flex items-center justify-between rounded-xl px-4 py-3 text-white">
            <span className="text-sm">Quoted amount</span>
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

      <p className="text-sm text-muted">
        Prices below were frozen when the quotation was processed. The {who} only sees each item&apos;s amount and the
        total (VAT included, not shown), and the 50/50 payment split.
      </p>
      {q.items.map((item, i) => (
        <ItemBreakdown key={item.position} item={item} title={q.items.length === 1 ? 'Internal cost breakdown' : `Cost breakdown · item ${i + 1}: ${item.product_name}`} money={money} />
      ))}

      <ReviewModal
        review={review}
        total={q.total}
        currency={q.currency}
        calculated={money(q.subtotal)}
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
          } else if (action === 'reject') {
            await adminApi.rejectQuotation(q.id, note)
            toast.success(q.walk_in ? 'Request rejected.' : 'Request rejected. The customer will see your note.')
          } else {
            await adminApi.cancelQuotation(q.id, note)
            toast.success('Request cancelled.')
          }
          setReview(null)
          revalidate()
        }}
      />
    </>
  )
}

/** One item's frozen cost breakdown: lines, markup, VAT and rounding (staff only). */
function ItemBreakdown({ item, title, money }: { item: AdminQuotationItem; title: string; money: (v: string) => string }) {
  const b = item.breakdown
  return (
    <Card title={title} icon={Calculator}>
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
          <dt>Item amount</dt>
          <dd>{money(item.amount)}</dd>
        </div>
      </dl>
    </Card>
  )
}

const AMOUNT = /^\d{1,10}(\.\d{1,2})?$/

function ReviewModal({
  review,
  total,
  currency,
  calculated,
  customer,
  walkIn,
  onClose,
  onSubmit,
}: {
  review: Review | null
  /** Current quoted amount, a decimal string like "21500.00" */
  total: string
  currency: string
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
  const who = walkIn ? 'client' : 'customer'
  const approving = review === 'approve'

  const text = {
    approve: {
      icon: CheckCircle2,
      tone: 'success' as const,
      title: 'Approve and issue quotation',
      description: `${customer} will get an official quotation with a quote number for the amount below.`,
      button: 'Approve',
      noteLabel: `Note to ${who} (optional)`,
      noteHint: 'Printed on the official PDF.',
    },
    reject: {
      icon: XCircle,
      tone: 'danger' as const,
      title: 'Reject this request',
      description: walkIn
        ? 'The request will be marked as rejected, with your note.'
        : `${customer} will see the request as rejected, with your note.`,
      button: 'Reject request',
      noteLabel: 'Reason',
      noteHint: 'e.g. “Size too large, please call us.”',
    },
    cancel: {
      icon: Ban,
      tone: 'danger' as const,
      title: 'Cancel this request',
      description: `Use this when the ${who} no longer needs the quotation. It is marked as cancelled, not rejected.`,
      button: 'Cancel request',
      noteLabel: `Reason (optional)`,
      noteHint: walkIn ? 'For your records.' : 'The customer will see this.',
    },
  }[review ?? 'approve']

  function close() {
    setNote('')
    setAmount(total)
    setError(null)
    onClose()
  }

  async function submit() {
    if (!review) return
    if (review === 'reject' && note.trim().length < 3) {
      setError(`Please write a short note so the ${who} knows why.`)
      return
    }
    const finalAmount = amount.trim().replace(/,/g, '')
    if (approving && (!AMOUNT.test(finalAmount) || Number(finalAmount) <= 0)) {
      setError('Enter the final amount, like 21500 or 21500.50.')
      return
    }

    // Yes / No before anything is saved; "No" goes back to this dialog with the inputs kept.
    const ok = await confirmAction(
      {
        approve: {
          title: 'Approve this quotation?',
          message: `${customer} gets an official quotation for ${formatMoney(finalAmount, currency)}. Approved quotations can't be changed.`,
          confirmLabel: 'Yes, approve',
          cancelLabel: 'No',
        },
        reject: {
          title: 'Reject this request?',
          message: `The request from ${customer} will be marked as rejected. This can't be undone.`,
          confirmLabel: 'Yes, reject',
          cancelLabel: 'No',
          tone: 'danger' as const,
        },
        cancel: {
          title: 'Cancel this request?',
          message: `The request from ${customer} will be cancelled. This can't be undone.`,
          confirmLabel: 'Yes, cancel it',
          cancelLabel: 'No, keep it',
          tone: 'danger' as const,
        },
      }[review],
    )
    if (!ok) return

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
      icon={text.icon}
      tone={text.tone}
      title={text.title}
      description={text.description}
      footer={
        <>
          <Button variant="secondary" icon={X} onClick={close}>
            Close
          </Button>
          <Button variant={approving ? 'primary' : 'danger'} icon={text.icon} loading={busy} onClick={submit}>
            {text.button}
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
        <Field label={text.noteLabel} htmlFor="review-note" required={review === 'reject'} hint={text.noteHint}>
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
