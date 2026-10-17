import { zodResolver } from '@hookform/resolvers/zod'
import { AlertTriangle, Calculator } from 'lucide-react'
import { useState } from 'react'
import { useForm } from 'react-hook-form'

import { adminApi, type PricePreview, type ProductDetail } from '../../api/admin'
import { Button } from '../../components/ui/Button'
import { Card, ErrorBanner } from '../../components/ui/Card'
import { Field, inputClass } from '../../components/ui/Field'
import { messageOf } from '../../lib/errors'
import { formatMoney } from '../../lib/format'
import { BreakdownLines, BreakdownSize, BreakdownSums } from './PriceBreakdown'
import { previewSchema, type PreviewForm } from './schemas'

export function PricePreviewPanel({ product }: { product: ProductDetail }) {
  const [result, setResult] = useState<PricePreview | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [optionIds, setOptionIds] = useState<string[]>([])
  const [picks, setPicks] = useState<Record<string, string>>({})
  const addOns = product.options.filter((o) => o.group_id === null)
  const perSqft = product.pricing_method === 'per_sqft'
  // An add-on adds nothing until it has a line (or, sold per sq ft, a rate).
  const addsNothing = (o: (typeof addOns)[number]) =>
    !product.components.some((c) => c.option_id === o.id) && !(perSqft && Number(o.rate_per_sqft) > 0)
  const groups = product.option_groups
    .map((g) => ({ ...g, choices: product.options.filter((o) => o.group_id === g.id) }))
    .filter((g) => g.choices.length > 0)
  type Group = (typeof groups)[number]
  // The picked choice of a group, or its first one (like the quotation form).
  const pickOf = (g: Group, chosen: Record<string, string>) =>
    g.choices.find((c) => c.id === chosen[g.id])?.id ?? g.choices[0].id
  const { register, handleSubmit, formState } = useForm<PreviewForm>({
    resolver: zodResolver(previewSchema),
    defaultValues: { width: '48', height: '48', unit: 'in', quantity: 1 },
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
        Try sample sizes to check the price
        {perSqft ? ', the cost guide and your margin' : ' and the template'}. Ticking an add-on or changing a choice
        updates it straight away. Uses current prices and settings; nothing is saved.
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
            <option value="in">inch</option>
            <option value="cm">cm</option>
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
              {addsNothing(o) && <span className="text-xs text-muted">(adds nothing yet)</span>}
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
            <p className="text-sm text-muted"><BreakdownSize b={result} /></p>
            <BreakdownLines b={result} money={money} />
            <BreakdownSums b={result} money={money} amountLabel="Customer pays" amount={result.rounded_total} />
          </div>
        )}
      </div>
    </Card>
  )
}
