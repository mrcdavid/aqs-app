// The items of a quotation: for each, a product picker (with its choices and add-ons), the size and
// quantity. Shared by the customer's form and the staff walk-in form; both wrap <QuoteItems> in a
// react-hook-form <FormProvider> whose values include QuoteFormValues (see quoteItem.ts).

import {
  AppWindow,
  CheckCircle2,
  DoorOpen,
  Grid3x3,
  ListChecks,
  Minus,
  Package,
  PackagePlus,
  Plus,
  Trash2,
  type LucideIcon,
} from 'lucide-react'
import { useEffect, type ReactNode } from 'react'
import { useFieldArray, useFormContext, useWatch } from 'react-hook-form'

import type { ProductCategory } from '../../api/admin'
import type { CatalogProduct } from '../../api/quotations'
import { Button, IconButton } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Field, inputClass, RequiredMark, segmentClass } from '../../components/ui/Field'
import { areaSqft, PRODUCT_CATEGORY_LABEL } from '../../lib/format'
import { EMPTY_QUOTE_ITEM, fromMm, MAX_ITEMS, type QuoteFormValues } from './quoteItem'

const CATEGORY_ICON: Record<ProductCategory, LucideIcon> = {
  sliding_window: AppWindow,
  sliding_door: DoorOpen,
  window_grill: Grid3x3,
  other: Package,
}

export function Step({ n, title, required, children }: { n: number; title: string; required?: boolean; children: ReactNode }) {
  return (
    <Card>
      <h2 className="mb-4 flex items-center gap-3 text-base font-semibold">
        <span className="bg-brand-gradient grid size-7 place-items-center rounded-full text-sm text-white">{n}</span>
        <span>
          {title}
          {required && <RequiredMark />}
        </span>
      </h2>
      {children}
    </Card>
  )
}

/** All items, with "Add another item". */
export function QuoteItems({ products }: { products: CatalogProduct[] }) {
  const { control, getValues } = useFormContext<QuoteFormValues>()
  const { fields, append, remove } = useFieldArray({ control, name: 'items' })

  function addItem() {
    // Start from the previous item's unit: people usually measure everything the same way.
    const last = getValues(`items.${fields.length - 1}`)
    append({ ...EMPTY_QUOTE_ITEM, unit: last?.unit ?? 'cm' }, { shouldFocus: false })
  }

  return (
    <div className="space-y-6">
      {fields.map((field, index) => (
        <ItemCard
          key={field.id}
          index={index}
          products={products}
          onRemove={fields.length > 1 ? () => remove(index) : undefined}
        />
      ))}
      <div className="flex flex-wrap items-center gap-3">
        <Button variant="secondary" icon={Plus} onClick={addItem} disabled={fields.length >= MAX_ITEMS}>
          Add another item
        </Button>
        <p className="text-sm text-muted">
          {fields.length >= MAX_ITEMS
            ? `Up to ${MAX_ITEMS} items per quotation.`
            : 'e.g. two windows and a door: one quotation, one total.'}
        </p>
      </div>
    </div>
  )
}

function ItemCard({ index, products, onRemove }: { index: number; products: CatalogProduct[]; onRemove?: () => void }) {
  const { register, control, formState } = useFormContext<QuoteFormValues>()
  const errors = formState.errors.items?.[index]
  const productId = useWatch({ control, name: `items.${index}.product_id` })
  const product = products.find((p) => p.id === productId)

  return (
    <Card>
      <div className="mb-4 flex items-center justify-between gap-3">
        <h2 className="flex items-center gap-3 text-base font-semibold">
          <span className="bg-brand-gradient grid size-7 place-items-center rounded-full text-sm text-white">{index + 1}</span>
          {product ? product.name : `Item ${index + 1}`}
        </h2>
        {onRemove && <IconButton icon={Trash2} tone="danger" label={`Remove item ${index + 1}`} onClick={onRemove} />}
      </div>

      <fieldset>
        <legend className="mb-3 text-sm font-medium">
          Product
          <RequiredMark />
        </legend>
        <div className="grid gap-3 sm:grid-cols-2">
          {products.map((p) => {
            const Icon = CATEGORY_ICON[p.category]
            return (
              <label
                key={p.id}
                className="group relative flex cursor-pointer gap-3 rounded-2xl border border-line bg-surface p-4 transition hover:border-line-strong has-checked:border-transparent has-checked:bg-brand-soft has-checked:ring-2 has-checked:ring-ring has-focus-visible:ring-2 has-focus-visible:ring-ring"
              >
                <input type="radio" value={p.id} className="sr-only" {...register(`items.${index}.product_id`)} />
                <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-surface-2 text-brand group-has-checked:bg-brand-gradient group-has-checked:text-white">
                  <Icon className="size-5" aria-hidden />
                </span>
                <span className="min-w-0 pr-6">
                  <span className="block font-medium">{p.name}</span>
                  <span className="block text-xs text-muted">{PRODUCT_CATEGORY_LABEL[p.category]}</span>
                  {p.description && <span className="mt-1 block text-sm text-muted">{p.description}</span>}
                </span>
                <CheckCircle2 className="absolute top-3 right-3 hidden size-5 text-brand group-has-checked:block" aria-hidden />
              </label>
            )
          })}
        </div>
        {errors?.product_id && (
          <p role="alert" className="mt-2 text-sm text-danger">
            {errors.product_id.message}
          </p>
        )}
      </fieldset>

      {product && product.choice_groups.length > 0 && <Choices index={index} product={product} />}
      {product && product.options.length > 0 && <AddOns index={index} product={product} />}
      <Size index={index} product={product} />
    </Card>
  )
}

const optionCard =
  'flex cursor-pointer gap-3 rounded-2xl border border-line bg-surface p-4 transition hover:border-line-strong ' +
  'has-checked:border-transparent has-checked:bg-brand-soft has-checked:ring-2 has-checked:ring-ring has-focus-visible:ring-2 has-focus-visible:ring-ring'

/** One required pick per group (e.g. Glass type). The first choice is pre-selected. */
function Choices({ index, product }: { index: number; product: CatalogProduct }) {
  const { register, getValues, setValue } = useFormContext<QuoteFormValues>()

  // Pick the first choice of each group when a product is chosen (keep a valid earlier pick).
  useEffect(() => {
    for (const g of product.choice_groups) {
      if (!g.choices.some((c) => c.id === getValues(`items.${index}.choices.${g.id}`))) {
        setValue(`items.${index}.choices.${g.id}`, g.choices[0].id)
      }
    }
  }, [index, product, getValues, setValue])

  return product.choice_groups.map((g) => (
    <div key={g.id} className="mt-5 border-t border-line pt-4">
      <fieldset>
        <legend className="mb-3 flex items-center gap-2 text-sm font-medium">
          <ListChecks className="size-4 text-brand" aria-hidden />
          <span>
            {g.name}
            <RequiredMark />
          </span>
        </legend>
        <div className="grid gap-3 sm:grid-cols-2">
          {g.choices.map((c) => (
            <label key={c.id} className={optionCard}>
              <input
                type="radio"
                value={c.id}
                className="mt-0.5 size-4 shrink-0 accent-brand"
                {...register(`items.${index}.choices.${g.id}`)}
              />
              <span className="min-w-0">
                <span className="block font-medium">{c.name}</span>
                {c.description && <span className="mt-0.5 block text-sm text-muted">{c.description}</span>}
              </span>
            </label>
          ))}
        </div>
      </fieldset>
    </div>
  ))
}

/** Optional extras of the chosen product, e.g. an open back aluminum frame. Unticked by default. */
function AddOns({ index, product }: { index: number; product: CatalogProduct }) {
  const { control, setValue } = useFormContext<QuoteFormValues>()
  const optionIds = useWatch({ control, name: `items.${index}.option_ids` })
  // A plain list in the form state; toggled by hand (a lone checkbox would register as a boolean).
  const toggle = (id: string) =>
    setValue(`items.${index}.option_ids`, optionIds.includes(id) ? optionIds.filter((x) => x !== id) : [...optionIds, id], {
      shouldDirty: true,
    })

  return (
    <div className="mt-5 border-t border-line pt-4">
      <fieldset>
        <legend className="mb-3 flex items-center gap-2 text-sm font-medium">
          <PackagePlus className="size-4 text-brand" aria-hidden />
          Add-ons (optional)
        </legend>
        <div className="grid gap-3 sm:grid-cols-2">
          {product.options.map((o) => (
            <label key={o.id} className={optionCard}>
              <input type="checkbox" className="mt-0.5 size-4 shrink-0 accent-brand" checked={optionIds.includes(o.id)} onChange={() => toggle(o.id)} />
              <span className="min-w-0">
                <span className="block font-medium">{o.name}</span>
                {o.description && <span className="mt-0.5 block text-sm text-muted">{o.description}</span>}
              </span>
            </label>
          ))}
        </div>
      </fieldset>
    </div>
  )
}

function Size({ index, product }: { index: number; product: CatalogProduct | undefined }) {
  const { register, control, setValue, formState } = useFormContext<QuoteFormValues>()
  const errors = formState.errors.items?.[index]
  const [unit, quantity, width, height] = useWatch({
    control,
    name: [`items.${index}.unit`, `items.${index}.quantity`, `items.${index}.width`, `items.${index}.height`],
  })
  const area = areaSqft(width, height, unit)
  const setQty = (q: number) => setValue(`items.${index}.quantity`, Math.min(100, Math.max(1, q || 1)), { shouldValidate: true })
  const range = (min: number, max: number) => `${fromMm(min, unit)}–${fromMm(max, unit)} ${unit}`
  const id = (name: string) => `item-${index}-${name}`

  return (
    <div className="mt-5 space-y-4 border-t border-line pt-4">
      <div>
        <p className="mb-1.5 text-sm font-medium" id={id('unit')}>
          Unit
          <RequiredMark />
        </p>
        <div role="radiogroup" aria-labelledby={id('unit')} className="inline-flex rounded-xl bg-surface-2 p-1">
          {(['in', 'cm'] as const).map((u) => (
            <label key={u} className={segmentClass}>
              <input type="radio" value={u} className="sr-only" {...register(`items.${index}.unit`)} />
              {u === 'cm' ? 'Centimetres' : 'Inches'}
            </label>
          ))}
        </div>
      </div>
      <div className="grid gap-4 sm:grid-cols-3">
        <Field
          label={`Width (${unit})`}
          htmlFor={id('width')}
          required
          error={errors?.width?.message}
          hint={product ? `Allowed: ${range(product.min_width_mm, product.max_width_mm)}` : 'Choose a product to see the allowed range'}
        >
          <input
            id={id('width')}
            inputMode="decimal"
            placeholder={unit === 'in' ? 'e.g. 48' : 'e.g. 120'}
            className={`${inputClass} tabular-nums`}
            aria-invalid={!!errors?.width}
            {...register(`items.${index}.width`)}
          />
        </Field>
        <Field
          label={`Height (${unit})`}
          htmlFor={id('height')}
          required
          error={errors?.height?.message}
          hint={product ? `Allowed: ${range(product.min_height_mm, product.max_height_mm)}` : undefined}
        >
          <input
            id={id('height')}
            inputMode="decimal"
            placeholder={unit === 'in' ? 'e.g. 48' : 'e.g. 120'}
            className={`${inputClass} tabular-nums`}
            aria-invalid={!!errors?.height}
            {...register(`items.${index}.height`)}
          />
        </Field>
        <Field label="Quantity" htmlFor={id('quantity')} required error={errors?.quantity?.message}>
          <div className="flex items-center gap-2">
            <Button variant="secondary" icon={Minus} aria-label="One fewer" className="w-11 shrink-0 px-0" onClick={() => setQty((quantity || 1) - 1)} />
            <input
              id={id('quantity')}
              type="number"
              min={1}
              max={100}
              className={`${inputClass} text-center tabular-nums`}
              aria-invalid={!!errors?.quantity}
              {...register(`items.${index}.quantity`, { valueAsNumber: true })}
            />
            <Button variant="secondary" icon={Plus} aria-label="One more" className="w-11 shrink-0 px-0" onClick={() => setQty((quantity || 0) + 1)} />
          </div>
        </Field>
      </div>
      {area && (
        <p className="text-sm text-muted" aria-live="polite">
          About <strong className="text-ink tabular-nums">{area} sq ft</strong> per piece
        </p>
      )}
    </div>
  )
}
