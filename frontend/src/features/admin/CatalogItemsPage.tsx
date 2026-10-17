import { zodResolver } from '@hookform/resolvers/zod'
import {
  Archive,
  ArchiveRestore,
  Pencil,
  Plus,
  Save,
  Search,
  Trash2,
  X,
  type LucideIcon,
} from 'lucide-react'
import { useState } from 'react'
import { useForm, useWatch } from 'react-hook-form'
import { useRevalidator } from 'react-router'

import type { MaterialCategory, PriceUnit, StockUnit } from '../../api/admin'
import { StatusBadge } from '../../components/ui/Badge'
import { Button, IconButton } from '../../components/ui/Button'
import { Card, EmptyState, ErrorBanner, PageHeader } from '../../components/ui/Card'
import { Field, inputClass, segmentClass } from '../../components/ui/Field'
import { Modal } from '../../components/ui/Modal'
import { messageOf } from '../../lib/errors'
import { barLabel, formatMoney, MATERIAL_CATEGORY_LABEL, trimDecimal, UNIT_LABEL } from '../../lib/format'
import { confirmAction, toast } from '../../stores/feedback'
import { priceItemSchema, type PriceItemForm } from './schemas'
import { useCurrency } from './useCurrency'

/** A material or labour rate, normalised so one page component can manage both. */
export interface CatalogItem {
  id: string
  code: string
  name: string
  unit: PriceUnit
  price: string
  category?: MaterialCategory
  /** Bars only */
  stock_length?: string | null
  stock_length_unit?: StockUnit | null
  is_active: boolean
}

interface Props {
  title: string
  description: string
  icon: LucideIcon
  singular: string // "material" / "labour rate"
  codeHint: string
  withCategory: boolean
  /** Units this kind of item can be priced in (labour: never per kilo or per bar) */
  units: PriceUnit[]
  items: CatalogItem[]
  create: (values: PriceItemForm) => Promise<unknown>
  update: (id: string, values: Partial<PriceItemForm> & { is_active?: boolean }) => Promise<unknown>
  remove: (id: string) => Promise<unknown>
}

type Filter = 'all' | 'active' | 'archived'

export function CatalogItemsPage(props: Props) {
  const { title, description, icon, singular, items, withCategory } = props
  const { revalidate } = useRevalidator()
  const currency = useCurrency()
  // null = closed, 'new' = adding, item = editing that item
  const [editing, setEditing] = useState<CatalogItem | 'new' | null>(null)
  const [busyId, setBusyId] = useState<string | null>(null)
  const [filter, setFilter] = useState<Filter>('all')
  const [query, setQuery] = useState('')

  const q = query.trim().toLowerCase()
  const shown = items.filter(
    (i) =>
      (filter === 'all' || (filter === 'active') === i.is_active) &&
      (!q || i.code.toLowerCase().includes(q) || i.name.toLowerCase().includes(q)),
  )
  const counts = { all: items.length, active: items.filter((i) => i.is_active).length }
  const editingId = editing && editing !== 'new' ? editing.id : null

  async function run(item: CatalogItem, action: () => Promise<unknown>, done: string) {
    setBusyId(item.id)
    try {
      await action()
      toast.success(done)
      revalidate()
    } catch (err) {
      toast.error(messageOf(err))
    } finally {
      setBusyId(null)
    }
  }

  async function onDelete(item: CatalogItem) {
    const ok = await confirmAction({
      title: `Delete ${item.code}?`,
      message: `This permanently removes “${item.name}”. It can't be undone. If you only want to stop using it in new templates, choose Archive instead — archived items can be restored.`,
      confirmLabel: 'Delete permanently',
      tone: 'danger',
    })
    if (ok) await run(item, () => props.remove(item.id), `${item.code} deleted.`)
  }

  function actions(item: CatalogItem) {
    const busy = busyId === item.id
    return (
      <div className="flex items-center justify-end gap-1">
        <IconButton icon={Pencil} tone="brand" label={`Edit ${item.code}`} onClick={() => setEditing(item)} disabled={busy} />
        {item.is_active ? (
          <IconButton
            icon={Archive}
            label={`Archive ${item.code}`}
            loading={busy}
            onClick={() => run(item, () => props.update(item.id, { is_active: false }), `${item.code} archived. It stays in old quotations and can be restored.`)}
          />
        ) : (
          <IconButton
            icon={ArchiveRestore}
            label={`Restore ${item.code}`}
            loading={busy}
            onClick={() => run(item, () => props.update(item.id, { is_active: true }), `${item.code} restored.`)}
          />
        )}
        <IconButton icon={Trash2} tone="danger" label={`Delete ${item.code}`} onClick={() => onDelete(item)} disabled={busy} />
      </div>
    )
  }

  const price = (i: CatalogItem) => (
    <span className="tabular-nums whitespace-nowrap">
      {formatMoney(i.price, currency)}{' '}
      <span className="text-muted">
        {i.unit === 'bar' ? `per ${barLabel(i.stock_length, i.stock_length_unit)}` : UNIT_LABEL[i.unit]}
      </span>
    </span>
  )

  return (
    <>
      <PageHeader
        title={title}
        description={description}
        icon={icon}
        actions={
          <Button icon={Plus} onClick={() => setEditing('new')} className="w-full sm:w-auto">
            Add {singular}
          </Button>
        }
      />

      <Card>
        <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="inline-flex self-start rounded-xl bg-surface-2 p-1" role="radiogroup" aria-label="Show">
            {(
              [
                ['all', `All (${counts.all})`],
                ['active', `Active (${counts.active})`],
                ['archived', `Archived (${counts.all - counts.active})`],
              ] as const
            ).map(([value, label]) => (
              <label key={value} className={segmentClass}>
                <input type="radio" name="filter" className="sr-only" checked={filter === value} onChange={() => setFilter(value)} />
                {label}
              </label>
            ))}
          </div>
          <div className="relative sm:w-64">
            <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted" aria-hidden />
            <input
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search code or name"
              aria-label={`Search ${title.toLowerCase()}`}
              className={`${inputClass} pl-9`}
            />
          </div>
        </div>

        {items.length === 0 ? (
          <EmptyState
            icon={icon}
            title={`No ${title.toLowerCase()} yet`}
            text={`Add your first ${singular} to use it in product price templates.`}
            action={
              <Button icon={Plus} onClick={() => setEditing('new')}>
                Add {singular}
              </Button>
            }
          />
        ) : shown.length === 0 ? (
          <p className="py-8 text-center text-sm text-muted">Nothing matches this filter.</p>
        ) : (
          <>
            {/* Phones: cards */}
            <ul className="space-y-3 md:hidden">
              {shown.map((i) => (
                <li
                  key={i.id}
                  className={`rounded-xl border p-3 ${editingId === i.id ? 'border-transparent ring-2 ring-ring' : 'border-line'}`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="font-mono text-xs text-muted">{i.code}</p>
                      <p className="font-medium">{i.name}</p>
                      {withCategory && i.category && <p className="text-xs text-muted">{MATERIAL_CATEGORY_LABEL[i.category]}</p>}
                    </div>
                    <StatusBadge active={i.is_active} />
                  </div>
                  <div className="mt-2 flex items-center justify-between gap-2">
                    <span className="text-sm">{price(i)}</span>
                    {actions(i)}
                  </div>
                </li>
              ))}
            </ul>

            {/* Tablet/desktop: table */}
            <div className="hidden overflow-x-auto md:block">
              <table className="w-full text-left text-sm">
                <thead className="text-xs tracking-wide text-muted uppercase">
                  <tr className="border-b border-line">
                    <th className="py-3 pr-4 font-medium">Code</th>
                    <th className="py-3 pr-4 font-medium">Name</th>
                    {withCategory && <th className="py-3 pr-4 font-medium">Category</th>}
                    <th className="py-3 pr-4 text-right font-medium">Price</th>
                    <th className="py-3 pr-4 font-medium">Status</th>
                    <th className="py-3 text-right font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {shown.map((i) => (
                    <tr
                      key={i.id}
                      className={`border-b border-line last:border-0 ${
                        editingId === i.id ? 'bg-brand-soft outline-2 -outline-offset-2 outline-ring' : 'hover:bg-surface-2/60'
                      }`}
                    >
                      <td className="py-2.5 pr-4 font-mono text-xs">{i.code}</td>
                      <td className="py-2.5 pr-4 font-medium">{i.name}</td>
                      {withCategory && (
                        <td className="py-2.5 pr-4 text-muted">{i.category ? MATERIAL_CATEGORY_LABEL[i.category] : ''}</td>
                      )}
                      <td className="py-2.5 pr-4 text-right">{price(i)}</td>
                      <td className="py-2.5 pr-4">
                        <StatusBadge active={i.is_active} />
                      </td>
                      <td className="py-1.5">{actions(i)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </Card>

      <ItemModal {...props} editing={editing} currency={currency} onClose={() => setEditing(null)} onSaved={revalidate} />
    </>
  )
}

function ItemModal({
  editing,
  currency,
  onClose,
  onSaved,
  singular,
  codeHint,
  withCategory,
  units,
  create,
  update,
}: Props & { editing: CatalogItem | 'new' | null; currency: string; onClose: () => void; onSaved: () => void }) {
  const isNew = editing === 'new'
  const item = editing && editing !== 'new' ? editing : null
  const [saving, setSaving] = useState(false)
  return (
    <Modal
      open={editing !== null}
      onClose={onClose}
      icon={isNew ? Plus : Pencil}
      title={isNew ? `Add ${singular}` : `Edit ${singular} ${item?.code ?? ''}`}
      description={
        isNew
          ? 'It becomes available in product price templates right away.'
          : 'New prices apply to new quotations. Existing quotations keep the prices they were given.'
      }
      footer={
        <>
          <Button variant="secondary" icon={X} onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" form="catalog-item-form" icon={isNew ? Plus : Save} loading={saving}>
            {isNew ? `Add ${singular}` : 'Save changes'}
          </Button>
        </>
      }
    >
      {editing !== null && (
        <ItemForm
          item={item}
          currency={currency}
          codeHint={codeHint}
          withCategory={withCategory}
          units={units}
          onSubmit={async (values) => {
            setSaving(true)
            try {
              if (item) await update(item.id, values)
              else await create(values)
            } finally {
              setSaving(false)
            }
            toast.success(item ? `${values.code} saved.` : `${values.code} added.`)
            onClose()
            onSaved()
          }}
        />
      )}
    </Modal>
  )
}

const UNIT_HINT: Record<PriceUnit, string> = {
  piece: 'Counted per window, e.g. handles, rollers',
  kg: 'e.g. jamb rubber, vinyl: kilos per foot, per sq ft or per window',
  ft: 'Measured by length',
  sqft: 'Measured by area, e.g. glass',
  bar: 'Whole bars of a fixed length, e.g. 21-ft profiles, 6-m square bars',
}

function ItemForm({
  item,
  currency,
  withCategory,
  units,
  codeHint,
  onSubmit,
}: {
  item: CatalogItem | null
  currency: string
  codeHint: string
  withCategory: boolean
  units: PriceUnit[]
  onSubmit: (values: PriceItemForm) => Promise<void>
}) {
  const [error, setError] = useState<string | null>(null)
  const { register, handleSubmit, formState, control } = useForm<PriceItemForm>({
    resolver: zodResolver(priceItemSchema),
    defaultValues: {
      code: item?.code ?? '',
      name: item?.name ?? '',
      category: item?.category ?? 'glass',
      unit: item?.unit ?? units[0],
      price: item?.price ?? '',
      stock_length: item?.stock_length ? trimDecimal(item.stock_length) : '',
      stock_length_unit: item?.stock_length_unit ?? 'ft',
    },
  })
  const { errors, isSubmitting } = formState
  const unit = useWatch({ control, name: 'unit' })

  return (
    <form
      id="catalog-item-form"
      noValidate
      className="space-y-4"
      onSubmit={handleSubmit(async (values) => {
        setError(null)
        try {
          await onSubmit(priceItemSchema.parse(values))
        } catch (err) {
          setError(messageOf(err))
        }
      })}
    >
      <ErrorBanner message={error} />
      <fieldset disabled={isSubmitting} className="grid gap-4 sm:grid-cols-2">
        <Field label="Code" htmlFor="ci-code" required error={errors.code?.message} hint={codeHint}>
          <input id="ci-code" autoFocus className={`${inputClass} font-mono uppercase`} aria-invalid={!!errors.code} {...register('code')} />
        </Field>
        <Field label="Name" htmlFor="ci-name" required error={errors.name?.message}>
          <input id="ci-name" className={inputClass} aria-invalid={!!errors.name} {...register('name')} />
        </Field>
        {withCategory && (
          <Field label="Category" htmlFor="ci-category" required>
            <select id="ci-category" className={inputClass} {...register('category')}>
              {Object.entries(MATERIAL_CATEGORY_LABEL).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </Field>
        )}
        <Field label="Priced" htmlFor="ci-unit" required hint={UNIT_HINT[unit]}>
          <select id="ci-unit" className={inputClass} {...register('unit')}>
            {units.map((value) => (
              <option key={value} value={value}>
                {UNIT_LABEL[value]}
              </option>
            ))}
          </select>
        </Field>
        <Field
          label={unit === 'bar' ? `Price of one bar (${currency})` : `Price (${currency})`}
          htmlFor="ci-price"
          required
          error={errors.price?.message}
          className={withCategory ? '' : 'sm:col-span-2'}
        >
          <input id="ci-price" inputMode="decimal" placeholder="e.g. 850.00" className={`${inputClass} tabular-nums`} aria-invalid={!!errors.price} {...register('price')} />
        </Field>
        {unit === 'bar' && (
          <Field
            label="Bar length"
            htmlFor="ci-length"
            required
            error={errors.stock_length?.message}
            hint="The length one bar is sold in; templates count whole bars, rounded up"
            className="sm:col-span-2"
          >
            <div className="flex gap-2">
              <input
                id="ci-length"
                inputMode="decimal"
                placeholder="e.g. 21"
                className={`${inputClass} tabular-nums`}
                aria-invalid={!!errors.stock_length}
                {...register('stock_length')}
              />
              <select aria-label="Bar length unit" className={`${inputClass} w-28`} {...register('stock_length_unit')}>
                <option value="ft">feet</option>
                <option value="m">metres</option>
              </select>
            </div>
          </Field>
        )}
      </fieldset>
    </form>
  )
}
