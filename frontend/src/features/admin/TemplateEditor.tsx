import { zodResolver } from '@hookform/resolvers/zod'
import { AlertTriangle } from 'lucide-react'
import { useState } from 'react'
import { useForm, useWatch } from 'react-hook-form'
import { Link } from 'react-router'

import {
  adminApi,
  type Basis,
  type Component,
  type LaborRate,
  type Material,
  type PriceUnit,
  type ProductDetail,
} from '../../api/admin'
import { Card, ErrorBanner } from '../../components/ui/Card'
import {
  buttonClass,
  Field,
  inputClass,
  linkButtonClass,
  secondaryButtonClass,
} from '../../components/ui/Field'
import { messageOf } from '../../lib/errors'
import { BASES_FOR_UNIT, BASIS_LABEL, formatMoney, trimDecimal, UNIT_LABEL } from '../../lib/format'
import { componentSchema, type ComponentForm } from './schemas'
import { useCurrency } from './useCurrency'

interface Props {
  product: ProductDetail
  materials: Material[]
  laborRates: LaborRate[]
  onChanged: () => void
}

const EMPTY: ComponentForm = { item: '', basis: 'area', factor: '1', waste_percent: '0', label: '' }

export function TemplateEditor({ product, materials, laborRates, onChanged }: Props) {
  const currency = useCurrency()
  const [editing, setEditing] = useState<Component | null>(null)
  const [error, setError] = useState<string | null>(null)

  const { register, handleSubmit, reset, setValue, control, formState } = useForm<ComponentForm>({
    resolver: zodResolver(componentSchema),
    defaultValues: EMPTY,
  })
  const { errors, isSubmitting } = formState

  // Unit of the chosen item decides which measurements make sense.
  const units = new Map<string, PriceUnit>([
    ...materials.map((m) => [`material:${m.id}`, m.unit] as const),
    ...laborRates.map((r) => [`labor:${r.id}`, r.unit] as const),
  ])
  const selectedUnit = units.get(useWatch({ control, name: 'item' }))
  const allowedBases: Basis[] = selectedUnit ? BASES_FOR_UNIT[selectedUnit] : []
  const hasItems = materials.some((m) => m.is_active) || laborRates.some((r) => r.is_active)

  const itemField = register('item', {
    onChange: (e: React.ChangeEvent<HTMLSelectElement>) => {
      const unit = units.get(e.target.value)
      if (unit) setValue('basis', BASES_FOR_UNIT[unit][0])
    },
  })

  function startEdit(c: Component) {
    setEditing(c)
    setError(null)
    reset({
      item: c.material_id ? `material:${c.material_id}` : `labor:${c.labor_rate_id}`,
      basis: c.basis,
      factor: trimDecimal(c.factor),
      waste_percent: trimDecimal(c.waste_percent),
      label: c.label,
    })
  }

  function cancelEdit() {
    setEditing(null)
    setError(null)
    reset(EMPTY)
  }

  async function onSubmit(values: ComponentForm) {
    setError(null)
    const { item, ...rest } = componentSchema.parse(values)
    try {
      if (editing) {
        await adminApi.updateComponent(product.id, editing.id, rest)
      } else {
        const [kind, id] = item.split(':')
        await adminApi.addComponent(product.id, {
          ...rest,
          [kind === 'material' ? 'material_id' : 'labor_rate_id']: id,
          sort_order: product.components.length,
        })
      }
      cancelEdit()
      onChanged()
    } catch (err) {
      setError(messageOf(err))
    }
  }

  async function remove(c: Component) {
    if (!window.confirm(`Remove ${c.item_code} from this template?`)) return
    setError(null)
    try {
      await adminApi.removeComponent(product.id, c.id)
      if (editing?.id === c.id) cancelEdit()
      onChanged()
    } catch (err) {
      setError(messageOf(err))
    }
  }

  return (
    <Card title="Price template">
      <p className="mb-4 text-sm text-muted">
        Each line is priced as <strong>measurement × factor × (1 + waste %)</strong> × the item's
        price. Example: 2 tracks along the width → Width, factor 2.
      </p>
      <ErrorBanner message={error} />

      {product.components.length === 0 ? (
        <p className="my-4 text-muted">No lines yet. Add materials and labour below.</p>
      ) : (
        <div className="my-4 overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-brand-100 text-muted">
              <tr>
                <th className="py-2 pr-4 font-medium">Item</th>
                <th className="py-2 pr-4 font-medium">Measured by</th>
                <th className="py-2 pr-4 text-right font-medium">Factor</th>
                <th className="py-2 pr-4 text-right font-medium">Waste</th>
                <th className="py-2 pr-4 text-right font-medium">Price</th>
                <th className="py-2 font-medium">
                  <span className="sr-only">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {product.components.map((c) => (
                <tr
                  key={c.id}
                  className={`border-b border-brand-50 last:border-0 ${editing?.id === c.id ? 'bg-brand-50' : ''}`}
                >
                  <td className="py-2 pr-4">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs">{c.item_code}</span>
                      {c.kind === 'labor' && (
                        <span className="rounded bg-brand-100 px-1.5 text-xs">labour</span>
                      )}
                      {!c.item_active && (
                        <span className="inline-flex items-center gap-1 text-xs text-amber-700">
                          <AlertTriangle className="size-3" aria-hidden /> archived
                        </span>
                      )}
                    </div>
                    <div className="text-muted">{c.label || c.item_name}</div>
                  </td>
                  <td className="py-2 pr-4">{BASIS_LABEL[c.basis]}</td>
                  <td className="py-2 pr-4 text-right tabular-nums">{trimDecimal(c.factor)}</td>
                  <td className="py-2 pr-4 text-right tabular-nums">{trimDecimal(c.waste_percent)}%</td>
                  <td className="py-2 pr-4 text-right tabular-nums whitespace-nowrap">
                    {formatMoney(c.item_price, currency)}{' '}
                    <span className="text-muted">{UNIT_LABEL[c.item_unit]}</span>
                  </td>
                  <td className="py-2 text-right whitespace-nowrap">
                    <button type="button" className={linkButtonClass} onClick={() => startEdit(c)}>
                      Edit
                    </button>
                    <button type="button" className={linkButtonClass} onClick={() => remove(c)}>
                      Remove
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {!hasItems && !editing ? (
        <div className="space-y-1 border-t border-brand-100 pt-4 text-sm">
          <h3 className="font-medium">Add a line</h3>
          <p className="rounded-lg bg-amber-50 p-3 text-amber-800">
            There are no active materials or labour rates to choose from yet. Add them first on the{' '}
            <Link to="/admin/materials" className="font-medium underline">
              Materials
            </Link>{' '}
            and{' '}
            <Link to="/admin/labor-rates" className="font-medium underline">
              Labour rates
            </Link>{' '}
            pages, then come back here.
          </p>
        </div>
      ) : (
      <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-4 border-t border-brand-100 pt-4">
        <h3 className="font-medium">{editing ? `Edit line: ${editing.item_code}` : 'Add a line'}</h3>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
          <div className="lg:col-span-2">
            <Field label="Material or labour" htmlFor="c-item" error={errors.item?.message}>
              <select
                id="c-item"
                className={inputClass}
                disabled={!!editing}
                aria-invalid={!!errors.item}
                {...itemField}
              >
                <option value="">Choose…</option>
                <optgroup label="Materials">
                  {materials
                    .filter((m) => m.is_active || editing?.material_id === m.id)
                    .map((m) => (
                      <option key={m.id} value={`material:${m.id}`}>
                        {m.code} – {m.name} ({UNIT_LABEL[m.unit]})
                      </option>
                    ))}
                </optgroup>
                <optgroup label="Labour">
                  {laborRates
                    .filter((r) => r.is_active || editing?.labor_rate_id === r.id)
                    .map((r) => (
                      <option key={r.id} value={`labor:${r.id}`}>
                        {r.code} – {r.name} ({UNIT_LABEL[r.unit]})
                      </option>
                    ))}
                </optgroup>
              </select>
            </Field>
          </div>
          <Field
            label="Measured by"
            htmlFor="c-basis"
            hint={selectedUnit ? undefined : 'Choose a material or labour first'}
            error={errors.basis?.message}
          >
            <select id="c-basis" className={inputClass} disabled={!selectedUnit} {...register('basis')}>
              {allowedBases.map((b) => (
                <option key={b} value={b}>
                  {BASIS_LABEL[b]}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Factor" htmlFor="c-factor" error={errors.factor?.message}>
            <input id="c-factor" inputMode="decimal" className={inputClass} {...register('factor')} />
          </Field>
          <Field label="Waste (%)" htmlFor="c-waste" error={errors.waste_percent?.message}>
            <input id="c-waste" inputMode="decimal" className={inputClass} {...register('waste_percent')} />
          </Field>
          <div className="sm:col-span-2 lg:col-span-5">
            <Field
              label="Label (optional)"
              htmlFor="c-label"
              hint="Shown on the quotation instead of the item name, e.g. “Top and bottom track”"
              error={errors.label?.message}
            >
              <input id="c-label" className={inputClass} {...register('label')} />
            </Field>
          </div>
        </div>
        <div className="flex gap-2">
          <button type="submit" disabled={isSubmitting} className={buttonClass}>
            {editing ? 'Save line' : 'Add line'}
          </button>
          {editing && (
            <button type="button" onClick={cancelEdit} className={secondaryButtonClass}>
              Cancel
            </button>
          )}
        </div>
      </form>
      )}
    </Card>
  )
}
