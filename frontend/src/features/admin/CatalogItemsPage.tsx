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
import { useForm } from 'react-hook-form'
import { useRevalidator } from 'react-router'

import type { MaterialCategory, PriceUnit } from '../../api/admin'
import { StatusBadge } from '../../components/ui/Badge'
import { Button, IconButton } from '../../components/ui/Button'
import { Card, EmptyState, ErrorBanner, PageHeader } from '../../components/ui/Card'
import { Field, inputClass, segmentClass } from '../../components/ui/Field'
import { Modal } from '../../components/ui/Modal'
import { messageOf } from '../../lib/errors'
import { formatMoney, MATERIAL_CATEGORY_LABEL, UNIT_LABEL } from '../../lib/format'
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
  is_active: boolean
}

interface Props {
  title: string
  description: string
  icon: LucideIcon
  singular: string // "material" / "labour rate"
  codeHint: string
  withCategory: boolean
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
      {formatMoney(i.price, currency)} <span className="text-muted">{UNIT_LABEL[i.unit]}</span>
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

function ItemForm({
  item,
  currency,
  withCategory,
  codeHint,
  onSubmit,
}: {
  item: CatalogItem | null
  currency: string
  codeHint: string
  withCategory: boolean
  onSubmit: (values: PriceItemForm) => Promise<void>
}) {
  const [error, setError] = useState<string | null>(null)
  const { register, handleSubmit, formState } = useForm<PriceItemForm>({
    resolver: zodResolver(priceItemSchema),
    defaultValues: item
      ? { code: item.code, name: item.name, category: item.category ?? 'glass', unit: item.unit, price: item.price }
      : { code: '', name: '', category: 'glass', unit: 'sqm', price: '' },
  })
  const { errors, isSubmitting } = formState

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
        <Field label="Code" htmlFor="ci-code" error={errors.code?.message} hint={codeHint}>
          <input id="ci-code" autoFocus className={`${inputClass} font-mono uppercase`} aria-invalid={!!errors.code} {...register('code')} />
        </Field>
        <Field label="Name" htmlFor="ci-name" error={errors.name?.message}>
          <input id="ci-name" className={inputClass} aria-invalid={!!errors.name} {...register('name')} />
        </Field>
        {withCategory && (
          <Field label="Category" htmlFor="ci-category">
            <select id="ci-category" className={inputClass} {...register('category')}>
              {Object.entries(MATERIAL_CATEGORY_LABEL).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </Field>
        )}
        <Field label="Priced" htmlFor="ci-unit" hint="Decides how templates measure it">
          <select id="ci-unit" className={inputClass} {...register('unit')}>
            {Object.entries(UNIT_LABEL).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </Field>
        <Field label={`Price (${currency})`} htmlFor="ci-price" error={errors.price?.message} className={withCategory ? '' : 'sm:col-span-2'}>
          <input id="ci-price" inputMode="decimal" placeholder="e.g. 850.00" className={`${inputClass} tabular-nums`} aria-invalid={!!errors.price} {...register('price')} />
        </Field>
      </fieldset>
    </form>
  )
}
