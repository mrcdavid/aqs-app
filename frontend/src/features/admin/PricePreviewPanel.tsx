import { zodResolver } from '@hookform/resolvers/zod'
import { AlertTriangle, Calculator, PackagePlus } from 'lucide-react'
import { useState } from 'react'
import { useForm } from 'react-hook-form'

import { adminApi, type PricePreview, type ProductDetail } from '../../api/admin'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card, ErrorBanner } from '../../components/ui/Card'
import { Field, inputClass } from '../../components/ui/Field'
import { messageOf } from '../../lib/errors'
import { BASIS_LABEL, formatMoney, trimDecimal, UNIT_LABEL } from '../../lib/format'
import { previewSchema, type PreviewForm } from './schemas'

export function PricePreviewPanel({ product }: { product: ProductDetail }) {
  const [result, setResult] = useState<PricePreview | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [optionIds, setOptionIds] = useState<string[]>([])
  const [picks, setPicks] = useState<Record<string, string>>({})
  const addOns = product.options.filter((o) => o.group_id === null)
  const hasLines = (optionId: string) => product.components.some((c) => c.option_id === optionId)
  const groups = product.option_groups
    .map((g) => ({ ...g, choices: product.options.filter((o) => o.group_id === g.id) }))
    .filter((g) => g.choices.length > 0)
  type Group = (typeof groups)[number]
  // The picked choice of a group, or its first one (like the quotation form).
  const pickOf = (g: Group, chosen: Record<string, string>) =>
    g.choices.find((c) => c.id === chosen[g.id])?.id ?? g.choices[0].id
  const { register, handleSubmit, formState } = useForm<PreviewForm>({
    resolver: zodResolver(previewSchema),
    defaultValues: { width: '120', height: '100', unit: 'cm', quantity: 1 },
  })
  const { errors, isSubmitting } = formState

  async function calculate(values: PreviewForm, ids: string[], chosen: Record<string, string>) {
    setError(null)
    try {
      // One choice per group, plus the ticked add-ons that still exist.
      const option_ids = [...groups.map((g) => pickOf(g, chosen)), ...ids.filter((id) => addOns.some((o) => o.id === id))]
      setResult(await adminApi.pricePreview(product.id, { ...previewSchema.parse(values), option_ids }))
    } catch (err) {
      setResult(null)
      setError(messageOf(err))
    }
  }

  // Ticking an add-on or switching a choice re-prices straight away, with the size typed above.
  // The new values are passed in directly: state set in the same click isn't readable yet.
  function recalculate(ids: string[], chosen: Record<string, string>) {
    void handleSubmit((values) => calculate(values, ids, chosen))()
  }

  function toggle(id: string) {
    const next = optionIds.includes(id) ? optionIds.filter((x) => x !== id) : [...optionIds, id]
    setOptionIds(next)
    recalculate(next, picks)
  }

  function choose(groupId: string, optionId: string) {
    const next = { ...picks, [groupId]: optionId }
    setPicks(next)
    recalculate(optionIds, next)
  }

  const money = (v: string) => (result ? formatMoney(v, result.currency) : v)

  return (
    <Card title="Price preview" icon={Calculator}>
      <p className="mb-4 text-sm text-muted">
        Try sample sizes to check the template. Ticking an add-on or changing a choice updates the price straight
        away. Uses current prices and settings; nothing is saved.
      </p>
      <form onSubmit={handleSubmit((values) => calculate(values, optionIds, picks))} noValidate className="grid grid-cols-2 items-end gap-3 sm:grid-cols-5">
        <Field label="Width" htmlFor="pv-width" required error={errors.width?.message}>
          <input id="pv-width" inputMode="decimal" className={`${inputClass} tabular-nums`} {...register('width')} />
        </Field>
        <Field label="Height" htmlFor="pv-height" required error={errors.height?.message}>
          <input id="pv-height" inputMode="decimal" className={`${inputClass} tabular-nums`} {...register('height')} />
        </Field>
        <Field label="Unit" htmlFor="pv-unit" required>
          <select id="pv-unit" className={inputClass} {...register('unit')}>
            <option value="cm">cm</option>
            <option value="in">inch</option>
          </select>
        </Field>
        <Field label="Qty" htmlFor="pv-qty" required error={errors.quantity?.message}>
          <input
            id="pv-qty"
            type="number"
            min={1}
            max={100}
            className={`${inputClass} tabular-nums`}
            {...register('quantity', { valueAsNumber: true })}
          />
        </Field>
        <Button type="submit" icon={Calculator} loading={isSubmitting} className="col-span-2 sm:col-span-1">
          Calculate
        </Button>
      </form>
      {groups.length > 0 && (
        <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 text-sm">
          {groups.map((g) => (
            <label key={g.id} className="inline-flex items-center gap-2">
              <span className="text-muted">{g.name}:</span>
              <select
                className={`${inputClass} w-auto py-1.5 sm:py-1.5`}
                value={pickOf(g, picks)}
                onChange={(e) => choose(g.id, e.target.value)}
              >
                {g.choices.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </label>
          ))}
        </div>
      )}
      {addOns.length > 0 && (
        <fieldset className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 text-sm">
          <legend className="sr-only">Add-ons to include</legend>
          <span className="text-muted">Include add-ons:</span>
          {addOns.map((o) => (
            <label key={o.id} className="inline-flex cursor-pointer items-center gap-2">
              <input type="checkbox" className="size-4 accent-brand" checked={optionIds.includes(o.id)} onChange={() => toggle(o.id)} />
              {o.name}
              {!hasLines(o.id) && <span className="text-xs text-muted">(no lines yet, adds nothing)</span>}
            </label>
          ))}
        </fieldset>
      )}

      <div className="mt-5 space-y-3">
        <ErrorBanner message={error} />
        {result && (
          <div className="animate-fade-up space-y-3">
            {result.warnings.map((w) => (
              <p key={w} className="flex items-center gap-2 rounded-xl bg-warning-soft p-3 text-sm text-warning">
                <AlertTriangle className="size-4 shrink-0" aria-hidden /> {w}
              </p>
            ))}
            <p className="text-sm text-muted">
              {result.width_mm} × {result.height_mm} mm · quantity {result.quantity}
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
                  {result.lines.map((l, i) => (
                    <tr key={i} className="border-t border-line">
                      <td className="px-3 py-2">
                        {l.label || l.name}{' '}
                        {l.option && (
                          <Badge tone="brand" icon={PackagePlus}>
                            {l.option}
                          </Badge>
                        )}
                      </td>
                      <td className="px-3 py-2 text-muted">
                        {BASIS_LABEL[l.basis]}
                        {l.width_mm !== null && (l.width_mm !== result.width_mm || l.height_mm !== result.height_mm) && (
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
            <dl className="ml-auto max-w-sm space-y-1.5 text-sm tabular-nums">
              {[
                ['Cost per piece', result.unit_subtotal],
                [`Customer unit price (+${trimDecimal(result.markup_percent)}% markup)`, result.unit_price],
                [`Subtotal (× ${result.quantity})`, result.net],
                [`VAT ${trimDecimal(result.vat_percent)}%`, result.vat],
                ['Total incl. VAT', result.total],
                [`Rounded up to the next ${trimDecimal(result.rounding_step)}`, result.rounding],
              ].map(([label, value]) => (
                <div key={label} className="flex justify-between gap-4">
                  <dt className="text-muted">{label}</dt>
                  <dd>{money(value)}</dd>
                </div>
              ))}
              <div className="bg-brand-gradient mt-2 flex justify-between gap-4 rounded-xl px-4 py-3 text-base font-semibold text-white">
                <dt>Customer pays</dt>
                <dd>{money(result.rounded_total)}</dd>
              </div>
            </dl>
          </div>
        )}
      </div>
    </Card>
  )
}
