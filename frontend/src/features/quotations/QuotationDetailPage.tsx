import {
  Ban,
  CalendarClock,
  CalendarDays,
  CheckCircle2,
  Clock,
  FileDown,
  FileText,
  MessageSquare,
  PackagePlus,
  Ruler,
  XCircle,
  type LucideIcon,
} from 'lucide-react'
import { useState } from 'react'
import { useLoaderData, useRevalidator } from 'react-router'

import { quotationsApi, type QuotationStatus } from '../../api/quotations'
import { QuotationStatusBadge } from '../../components/ui/Badge'
import { Button, ButtonAnchor } from '../../components/ui/Button'
import { Card, PageHeader } from '../../components/ui/Card'
import { messageOf } from '../../lib/errors'
import { formatDate, formatMoney, trimDecimal } from '../../lib/format'
import { confirmAction, toast } from '../../stores/feedback'
import type { quotationDetailLoader } from './loader'

const STATUS: Record<QuotationStatus, { text: string; icon: LucideIcon; cls: string }> = {
  pending: {
    text: 'Your estimate is ready. Our team will review it and issue the official quotation.',
    icon: Clock,
    cls: 'bg-warning-soft text-warning',
  },
  approved: {
    text: 'Your quotation has been approved. You can view and print the official PDF.',
    icon: CheckCircle2,
    cls: 'bg-success-soft text-success',
  },
  rejected: { text: 'This request was not approved. See the note from our team below.', icon: XCircle, cls: 'bg-danger-soft text-danger' },
  cancelled: { text: 'You cancelled this request.', icon: Ban, cls: 'bg-surface-2 text-muted' },
}

export function QuotationDetailPage() {
  const { quotation: q } = useLoaderData<typeof quotationDetailLoader>()
  const { revalidate } = useRevalidator()
  const [cancelling, setCancelling] = useState(false)
  const money = (v: string) => formatMoney(v, q.currency)
  const hasPdf = q.status === 'pending' || q.status === 'approved'
  const status =
    q.status === 'cancelled' && q.cancelled_by_staff
      ? { ...STATUS.cancelled, text: `Our team cancelled this request.${q.review_note ? ' See their note below.' : ''}` }
      : STATUS[q.status]

  async function cancel() {
    const ok = await confirmAction({
      title: 'Cancel this request?',
      message: "Our team won't review it. You can always request a new quotation later.",
      confirmLabel: 'Yes, cancel it',
      cancelLabel: 'No, keep it',
      tone: 'danger',
    })
    if (!ok) return
    setCancelling(true)
    try {
      await quotationsApi.cancel(q.id)
      toast.success('Request cancelled.')
      revalidate()
    } catch (err) {
      toast.error(messageOf(err))
    } finally {
      setCancelling(false)
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        backTo="/app/quotations"
        backLabel="My quotations"
        title={q.number ?? 'Estimate'}
        icon={FileText}
        actions={
          <>
            {q.can_cancel && (
              <Button variant="secondary" icon={Ban} loading={cancelling} onClick={cancel} className="flex-1 sm:flex-none">
                Cancel request
              </Button>
            )}
            {hasPdf && (
              <ButtonAnchor href={quotationsApi.pdfUrl(q.id)} target="_blank" rel="noopener" icon={FileDown} className="flex-1 sm:flex-none">
                {q.status === 'approved' ? 'View / print PDF' : 'View estimate PDF'}
              </ButtonAnchor>
            )}
          </>
        }
      >
        <QuotationStatusBadge status={q.status} />
      </PageHeader>

      <p className={`flex items-start gap-2 rounded-xl p-3 text-sm ${status.cls}`}>
        <status.icon className="mt-0.5 size-4 shrink-0" aria-hidden />
        {status.text}
      </p>

      {q.review_note && (
        <Card title="Note from our team" icon={MessageSquare}>
          <p className="whitespace-pre-line text-sm">{q.review_note}</p>
        </Card>
      )}

      <Card>
        <div className="space-y-5">
          <dl className="grid gap-4 text-sm sm:grid-cols-2">
            <div className="flex items-start gap-3">
              <CalendarDays className="mt-0.5 size-4 text-muted" aria-hidden />
              <div>
                <dt className="text-muted">Requested</dt>
                <dd className="font-medium">{formatDate(q.created_at)}</dd>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <CalendarClock className="mt-0.5 size-4 text-muted" aria-hidden />
              <div>
                <dt className="text-muted">Valid until</dt>
                <dd className="font-medium">{q.valid_until ? formatDate(q.valid_until) : 'Set on approval'}</dd>
              </div>
            </div>
          </dl>

          <ol className="divide-y divide-line border-y border-line">
            {q.items.map((item, i) => (
              <li key={item.position} className="flex gap-3 py-4">
                <span className="grid size-7 shrink-0 place-items-center rounded-full bg-brand-soft text-sm font-semibold text-brand">
                  {i + 1}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-baseline justify-between gap-x-4">
                    <h2 className="font-semibold">{item.product_name}</h2>
                    <span className="font-semibold tabular-nums">{money(item.amount)}</span>
                  </div>
                  {item.product_description && <p className="text-sm text-muted">{item.product_description}</p>}
                  <p className="mt-1 flex flex-wrap items-center gap-x-2 text-sm">
                    <Ruler className="size-4 text-muted" aria-hidden />
                    <span className="font-medium">
                      {trimDecimal(item.input_width)} × {trimDecimal(item.input_height)} {item.input_unit}
                    </span>
                    <span className="text-muted">
                      ({item.width_mm} × {item.height_mm} mm) · qty {item.quantity}
                    </span>
                  </p>
                  <p className="mt-1 text-sm text-muted">Includes: {item.includes.join(', ')}</p>
                  {item.choices.map((c) => (
                    <p key={c.group} className="mt-1 text-sm">
                      <span className="text-muted">{c.group}:</span> <span className="font-medium">{c.name}</span>
                    </p>
                  ))}
                  {item.options.length > 0 && (
                    <p className="mt-1 flex items-center gap-1.5 text-sm font-medium">
                      <PackagePlus className="size-4 shrink-0 text-brand" aria-hidden />
                      With: {item.options.join(', ')}
                    </p>
                  )}
                </div>
              </li>
            ))}
          </ol>

          <dl className="space-y-2 text-sm tabular-nums">
            {Number(q.adjustment) !== 0 && (
              <>
                <div className="flex justify-between gap-4">
                  <dt className="text-muted">Subtotal</dt>
                  <dd>{money(q.subtotal)}</dd>
                </div>
                <div className="flex justify-between gap-4 pb-1">
                  <dt className="text-muted">Adjustment</dt>
                  <dd>
                    {Number(q.adjustment) > 0 ? '+ ' : '- '}
                    {money(q.adjustment.replace('-', ''))}
                  </dd>
                </div>
              </>
            )}
            <div className="bg-brand-gradient flex items-center justify-between gap-4 rounded-xl px-4 py-3 text-white">
              <dt className="font-medium">{q.status === 'approved' ? 'Total amount' : 'Estimated amount'}</dt>
              <dd className="text-xl font-semibold">{money(q.total)}</dd>
            </div>
            <div className="flex justify-between gap-4 pt-2">
              <dt className="text-muted">50% downpayment</dt>
              <dd>{money(q.downpayment)}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-muted">50% upon completion and installation</dt>
              <dd>{money(q.balance)}</dd>
            </div>
          </dl>
        </div>
      </Card>
    </div>
  )
}
