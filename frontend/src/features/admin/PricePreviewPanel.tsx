import { zodResolver } from '@hookform/resolvers/zod'
import { AlertTriangle } from 'lucide-react'
import { useState } from 'react'
import { useForm } from 'react-hook-form'

import { adminApi, type PricePreview, type ProductDetail } from '../../api/admin'
import { Card, ErrorBanner } from '../../components/ui/Card'
import { buttonClass, Field, inputClass } from '../../components/ui/Field'
import { messageOf } from '../../lib/errors'
import { BASIS_LABEL, formatMoney, trimDecimal, UNIT_LABEL } from '../../lib/format'
import { previewSchema, type PreviewForm } from './schemas'

export function PricePreviewPanel({ product }: { product: ProductDetail }) {
  const [result, setResult] = useState<PricePreview | null>(null)
  const [error, setError] = useState<string | null>(null)
  const { register, handleSubmit, formState } = useForm<PreviewForm>({
    resolver: zodResolver(previewSchema),
    defaultValues: { width: '120', height: '100', unit: 'cm', quantity: 1 },
  })
  const { errors, isSubmitting } = formState

  async function onSubmit(values: PreviewForm) {
    setError(null)
    try {
      setResult(await adminApi.pricePreview(product.id, previewSchema.parse(values)))
    } catch (err) {
      setResult(null)
      setError(messageOf(err))
    }
  }

  const money = (v: string) => (result ? formatMoney(v, result.currency) : v)

  return (
    <Card title="Price preview">
      <p className="mb-4 text-sm text-muted">
        Try sample sizes to check the template. Uses current prices and settings; nothing is saved.
      </p>
      <form onSubmit={handleSubmit(onSubmit)} noValidate className="flex flex-wrap items-end gap-3">
        <Field label="Width" htmlFor="pv-width" error={errors.width?.message}>
          <input id="pv-width" inputMode="decimal" className={`${inputClass} w-28`} {...register('width')} />
        </Field>
        <Field label="Height" htmlFor="pv-height" error={errors.height?.message}>
          <input id="pv-height" inputMode="decimal" className={`${inputClass} w-28`} {...register('height')} />
        </Field>
        <Field label="Unit" htmlFor="pv-unit">
          <select id="pv-unit" className={inputClass} {...register('unit')}>
            <option value="cm">cm</option>
            <option value="in">inch</option>
          </select>
        </Field>
        <Field label="Qty" htmlFor="pv-qty" error={errors.quantity?.message}>
          <input
            id="pv-qty"
            type="number"
            min={1}
            max={100}
            className={`${inputClass} w-20`}
            {...register('quantity', { valueAsNumber: true })}
          />
        </Field>
        <button type="submit" disabled={isSubmitting} className={buttonClass}>
          Calculate
        </button>
      </form>

      <div className="mt-4 space-y-3">
        <ErrorBanner message={error} />
        {result && (
          <>
            {result.warnings.map((w) => (
              <p key={w} className="flex items-center gap-2 rounded-lg bg-amber-50 p-3 text-sm text-amber-800">
                <AlertTriangle className="size-4" aria-hidden /> {w}
              </p>
            ))}
            <p className="text-sm text-muted">
              {result.width_mm} × {result.height_mm} mm, quantity {result.quantity}
            </p>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="border-b border-brand-100 text-muted">
                  <tr>
                    <th className="py-2 pr-4 font-medium">Line</th>
                    <th className="py-2 pr-4 font-medium">Measured by</th>
                    <th className="py-2 pr-4 text-right font-medium">Qty</th>
                    <th className="py-2 pr-4 text-right font-medium">Price</th>
                    <th className="py-2 text-right font-medium">Cost</th>
                  </tr>
                </thead>
                <tbody className="tabular-nums">
                  {result.lines.map((l, i) => (
                    <tr key={i} className="border-b border-brand-50">
                      <td className="py-2 pr-4">{l.label || l.name}</td>
                      <td className="py-2 pr-4">{BASIS_LABEL[l.basis]}</td>
                      <td className="py-2 pr-4 text-right">{trimDecimal(l.quantity)}</td>
                      <td className="py-2 pr-4 text-right whitespace-nowrap">
                        {money(l.unit_price)} <span className="text-muted">{UNIT_LABEL[l.unit]}</span>
                      </td>
                      <td className="py-2 text-right">{money(l.cost)}</td>
                    </tr>
                  ))}
                </tbody>
                <tfoot className="tabular-nums">
                  <SummaryRow label="Cost per unit" value={money(result.unit_subtotal)} />
                  <SummaryRow label={`Subtotal (× ${result.quantity})`} value={money(result.subtotal)} />
                  <SummaryRow label={`Markup ${trimDecimal(result.markup_percent)}%`} value={money(result.markup)} />
                  <SummaryRow label={`VAT ${trimDecimal(result.vat_percent)}%`} value={money(result.vat)} />
                  <SummaryRow label="Total" value={money(result.total)} strong />
                </tfoot>
              </table>
            </div>
          </>
        )}
      </div>
    </Card>
  )
}

function SummaryRow({ label, value, strong }: { label: string; value: string; strong?: boolean }) {
  return (
    <tr className={strong ? 'text-base font-semibold' : ''}>
      <td colSpan={4} className="py-1 pr-4 text-right">
        {label}
      </td>
      <td className="py-1 text-right">{value}</td>
    </tr>
  )
}
