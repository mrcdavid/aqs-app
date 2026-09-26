import { zodResolver } from '@hookform/resolvers/zod'
import { AlertTriangle, Boxes, HardHat, Layers, Pencil, Plus, Save, Trash2, X } from 'lucide-react'
import { useState } from 'react'
import { useForm, useWatch } from 'react-hook-form'

import {
  adminApi,
  type Basis,
  type Component,
  type LaborRate,
  type Material,
  type PriceUnit,
  type ProductDetail,
} from '../../api/admin'
import { Badge } from '../../components/ui/Badge'
import { Button, ButtonLink, IconButton } from '../../components/ui/Button'
import { Card, EmptyState, ErrorBanner } from '../../components/ui/Card'
import { Field, inputClass } from '../../components/ui/Field'
import { Modal } from '../../components/ui/Modal'
import { messageOf } from '../../lib/errors'
import { BASES_FOR_UNIT, BASIS_LABEL, formatMoney, trimDecimal, UNIT_LABEL } from '../../lib/format'
import { confirmAction, toast } from '../../stores/feedback'
import { componentSchema, type ComponentForm } from './schemas'
import { useCurrency } from './useCurrency'

interface Props {
  product: ProductDetail
  materials: Material[]
  laborRates: LaborRate[]
  onChanged: () => void
}

export function TemplateEditor({ product, materials, laborRates, onChanged }: Props) {
  const currency = useCurrency()
  // null = closed, 'new' = adding a line, component = editing that line
  const [editing, setEditing] = useState<Component | 'new' | null>(null)
  const [busyId, setBusyId] = useState<string | null>(null)
  const hasItems = materials.some((m) => m.is_active) || laborRates.some((r) => r.is_active)
  const editingId = editing && editing !== 'new' ? editing.id : null

  async function remove(c: Component) {
    const ok = await confirmAction({
      title: `Remove ${c.item_code}?`,
      message: `“${c.label || c.item_name}” will no longer be part of this product's price. The material or labour rate itself is not deleted.`,
      confirmLabel: 'Remove line',
      tone: 'danger',
    })
    if (!ok) return
    setBusyId(c.id)
    try {
      await adminApi.removeComponent(product.id, c.id)
      toast.success(`${c.item_code} removed from the template.`)
      onChanged()
    } catch (err) {
      toast.error(messageOf(err))
    } finally {
      setBusyId(null)
    }
  }

  const lineActions = (c: Component) => (
    <div className="flex justify-end gap-1">
      <IconButton icon={Pencil} tone="brand" label={`Edit line ${c.item_code}`} onClick={() => setEditing(c)} />
      <IconButton icon={Trash2} tone="danger" label={`Remove line ${c.item_code}`} loading={busyId === c.id} onClick={() => remove(c)} />
    </div>
  )

  const itemCell = (c: Component) => (
    <div className="min-w-0">
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="font-mono text-xs text-muted">{c.item_code}</span>
        <Badge tone={c.kind === 'labor' ? 'brand' : 'neutral'} icon={c.kind === 'labor' ? HardHat : Boxes}>
          {c.kind === 'labor' ? 'Labour' : 'Material'}
        </Badge>
        {!c.item_active && (
          <Badge tone="warning" icon={AlertTriangle}>
            Archived
          </Badge>
        )}
      </div>
      <p className="font-medium">{c.label || c.item_name}</p>
    </div>
  )

  return (
    <Card
      title="Price template"
      icon={Layers}
      actions={
        hasItems && (
          <Button size="sm" icon={Plus} onClick={() => setEditing('new')}>
            Add line
          </Button>
        )
      }
    >
      <p className="mb-4 rounded-xl bg-surface-2 p-3 text-sm text-muted">
        Each line costs <strong className="text-ink">measurement × factor × (1 + waste %) × price</strong>. Example: two tracks
        along the width → <em>Width</em>, factor <em>2</em>.
      </p>

      {!hasItems && (
        <div className="mb-4 rounded-xl border border-warning/30 bg-warning-soft p-4 text-sm text-warning">
          <p className="flex items-center gap-2 font-medium">
            <AlertTriangle className="size-4" aria-hidden /> No materials or labour rates yet
          </p>
          <p className="mt-1">Add them first, then come back to build this template.</p>
          <div className="mt-3 flex flex-wrap gap-2">
            <ButtonLink to="/admin/materials" size="sm" variant="secondary" icon={Boxes}>
              Go to Materials
            </ButtonLink>
            <ButtonLink to="/admin/labor-rates" size="sm" variant="secondary" icon={HardHat}>
              Go to Labour rates
            </ButtonLink>
          </div>
        </div>
      )}

      {product.components.length === 0 ? (
        hasItems && (
          <EmptyState
            icon={Layers}
            title="This template is empty"
            text="Add the materials and labour that make up one piece of this product."
            action={
              <Button icon={Plus} onClick={() => setEditing('new')}>
                Add first line
              </Button>
            }
          />
        )
      ) : (
        <>
          <ul className="space-y-3 md:hidden">
            {product.components.map((c) => (
              <li
                key={c.id}
                className={`rounded-xl border p-3 ${editingId === c.id ? 'border-transparent ring-2 ring-ring' : 'border-line'}`}
              >
                {itemCell(c)}
                <p className="mt-2 text-sm text-muted">
                  {BASIS_LABEL[c.basis]} × {trimDecimal(c.factor)} · waste {trimDecimal(c.waste_percent)}%
                </p>
                <div className="mt-1 flex items-center justify-between">
                  <span className="text-sm tabular-nums">
                    {formatMoney(c.item_price, currency)} <span className="text-muted">{UNIT_LABEL[c.item_unit]}</span>
                  </span>
                  {lineActions(c)}
                </div>
              </li>
            ))}
          </ul>
          <div className="hidden overflow-x-auto md:block">
            <table className="w-full text-left text-sm">
              <thead className="text-xs tracking-wide text-muted uppercase">
                <tr className="border-b border-line">
                  <th className="py-3 pr-4 font-medium">Item</th>
                  <th className="py-3 pr-4 font-medium">Measured by</th>
                  <th className="py-3 pr-4 text-right font-medium">Factor</th>
                  <th className="py-3 pr-4 text-right font-medium">Waste</th>
                  <th className="py-3 pr-4 text-right font-medium">Price</th>
                  <th className="py-3 text-right font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {product.components.map((c) => (
                  <tr
                    key={c.id}
                    className={`border-b border-line last:border-0 ${
                      editingId === c.id ? 'bg-brand-soft outline-2 -outline-offset-2 outline-ring' : 'hover:bg-surface-2/60'
                    }`}
                  >
                    <td className="py-2.5 pr-4">{itemCell(c)}</td>
                    <td className="py-2.5 pr-4">{BASIS_LABEL[c.basis]}</td>
                    <td className="py-2.5 pr-4 text-right tabular-nums">{trimDecimal(c.factor)}</td>
                    <td className="py-2.5 pr-4 text-right tabular-nums">{trimDecimal(c.waste_percent)}%</td>
                    <td className="py-2.5 pr-4 text-right tabular-nums whitespace-nowrap">
                      {formatMoney(c.item_price, currency)} <span className="text-muted">{UNIT_LABEL[c.item_unit]}</span>
                    </td>
                    <td className="py-1.5">{lineActions(c)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      <LineModal
        editing={editing}
        product={product}
        materials={materials}
        laborRates={laborRates}
        onClose={() => setEditing(null)}
        onSaved={() => {
          setEditing(null)
          onChanged()
        }}
      />
    </Card>
  )
}

function LineModal({
  editing,
  product,
  materials,
  laborRates,
  onClose,
  onSaved,
}: Omit<Props, 'onChanged'> & { editing: Component | 'new' | null; onClose: () => void; onSaved: () => void }) {
  const [saving, setSaving] = useState(false)
  const line = editing && editing !== 'new' ? editing : null
  return (
    <Modal
      open={editing !== null}
      onClose={onClose}
      icon={line ? Pencil : Plus}
      title={line ? `Edit line ${line.item_code}` : 'Add a line'}
      description={line ? `${line.item_name} — the item can't be changed; remove the line and add a new one instead.` : `Part of ${product.name}.`}
      footer={
        <>
          <Button variant="secondary" icon={X} onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" form="line-form" icon={line ? Save : Plus} loading={saving}>
            {line ? 'Save line' : 'Add line'}
          </Button>
        </>
      }
    >
      <LineForm
        line={line}
        materials={materials}
        laborRates={laborRates}
        onSubmit={async (values) => {
          const { item, ...rest } = componentSchema.parse(values)
          setSaving(true)
          try {
            if (line) {
              await adminApi.updateComponent(product.id, line.id, rest)
            } else {
              const [kind, id] = item.split(':')
              await adminApi.addComponent(product.id, {
                ...rest,
                [kind === 'material' ? 'material_id' : 'labor_rate_id']: id,
                sort_order: product.components.length,
              })
            }
          } finally {
            setSaving(false)
          }
          toast.success(line ? 'Line saved.' : 'Line added.')
          onSaved()
        }}
      />
    </Modal>
  )
}

function LineForm({
  line,
  materials,
  laborRates,
  onSubmit,
}: {
  line: Component | null
  materials: Material[]
  laborRates: LaborRate[]
  onSubmit: (values: ComponentForm) => Promise<void>
}) {
  const [error, setError] = useState<string | null>(null)
  const { register, handleSubmit, setValue, control, formState } = useForm<ComponentForm>({
    resolver: zodResolver(componentSchema),
    defaultValues: line
      ? {
          item: line.material_id ? `material:${line.material_id}` : `labor:${line.labor_rate_id}`,
          basis: line.basis,
          factor: trimDecimal(line.factor),
          waste_percent: trimDecimal(line.waste_percent),
          label: line.label,
        }
      : { item: '', basis: 'area', factor: '1', waste_percent: '0', label: '' },
  })
  const { errors, isSubmitting } = formState

  // The chosen item's pricing unit decides which measurements make sense.
  const units = new Map<string, PriceUnit>([
    ...materials.map((m) => [`material:${m.id}`, m.unit] as const),
    ...laborRates.map((r) => [`labor:${r.id}`, r.unit] as const),
  ])
  const selectedUnit = units.get(useWatch({ control, name: 'item' }))
  const allowedBases: Basis[] = selectedUnit ? BASES_FOR_UNIT[selectedUnit] : []
  const itemField = register('item', {
    onChange: (e: React.ChangeEvent<HTMLSelectElement>) => {
      const unit = units.get(e.target.value)
      if (unit) setValue('basis', BASES_FOR_UNIT[unit][0])
    },
  })

  return (
    <form
      id="line-form"
      noValidate
      className="space-y-4"
      onSubmit={handleSubmit(async (values) => {
        setError(null)
        try {
          await onSubmit(values)
        } catch (err) {
          setError(messageOf(err))
        }
      })}
    >
      <ErrorBanner message={error} />
      <fieldset disabled={isSubmitting} className="grid gap-4 sm:grid-cols-2">
        <Field label="Material or labour" htmlFor="c-item" error={errors.item?.message} className="sm:col-span-2">
          <select id="c-item" className={inputClass} disabled={!!line} aria-invalid={!!errors.item} {...itemField}>
            <option value="">Choose…</option>
            <optgroup label="Materials">
              {materials
                .filter((m) => m.is_active || line?.material_id === m.id)
                .map((m) => (
                  <option key={m.id} value={`material:${m.id}`}>
                    {m.code} – {m.name} ({UNIT_LABEL[m.unit]})
                  </option>
                ))}
            </optgroup>
            <optgroup label="Labour">
              {laborRates
                .filter((r) => r.is_active || line?.labor_rate_id === r.id)
                .map((r) => (
                  <option key={r.id} value={`labor:${r.id}`}>
                    {r.code} – {r.name} ({UNIT_LABEL[r.unit]})
                  </option>
                ))}
            </optgroup>
          </select>
        </Field>
        <Field
          label="Measured by"
          htmlFor="c-basis"
          hint={selectedUnit ? undefined : 'Choose a material or labour first'}
          error={errors.basis?.message}
          className="sm:col-span-2"
        >
          <select id="c-basis" className={inputClass} disabled={!selectedUnit} {...register('basis')}>
            {allowedBases.map((b) => (
              <option key={b} value={b}>
                {BASIS_LABEL[b]}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Factor" htmlFor="c-factor" hint="How many (e.g. 2 tracks)" error={errors.factor?.message}>
          <input id="c-factor" data-autofocus={line ? true : undefined} inputMode="decimal" className={`${inputClass} tabular-nums`} {...register('factor')} />
        </Field>
        <Field label="Waste (%)" htmlFor="c-waste" hint="Extra for cutting loss" error={errors.waste_percent?.message}>
          <input id="c-waste" inputMode="decimal" className={`${inputClass} tabular-nums`} {...register('waste_percent')} />
        </Field>
        <Field
          label="Label (optional)"
          htmlFor="c-label"
          hint="Shown on the quotation instead of the item name, e.g. “Top and bottom track”"
          error={errors.label?.message}
          className="sm:col-span-2"
        >
          <input id="c-label" className={inputClass} {...register('label')} />
        </Field>
      </fieldset>
    </form>
  )
}
