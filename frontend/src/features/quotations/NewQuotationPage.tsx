import { zodResolver } from '@hookform/resolvers/zod'
import {
  AppWindow,
  Calculator,
  CheckCircle2,
  DoorOpen,
  FilePlus2,
  Grid3x3,
  Minus,
  Package,
  PackageX,
  Plus,
  X,
  type LucideIcon,
} from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { useForm, useWatch } from 'react-hook-form'
import { useLoaderData, useNavigate } from 'react-router'
import { z } from 'zod'

import type { ProductCategory } from '../../api/admin'
import { quotationsApi, type CatalogProduct, type LengthUnit } from '../../api/quotations'
import { Button, ButtonLink } from '../../components/ui/Button'
import { Card, EmptyState, ErrorBanner, PageHeader } from '../../components/ui/Card'
import { Field, inputClass, segmentClass } from '../../components/ui/Field'
import { messageOf } from '../../lib/errors'
import { PRODUCT_CATEGORY_LABEL } from '../../lib/format'
import { toast } from '../../stores/feedback'
import type { newQuotationLoader } from './loader'

const MM_PER: Record<LengthUnit, number> = { cm: 10, in: 25.4 }

const CATEGORY_ICON: Record<ProductCategory, LucideIcon> = {
  sliding_window: AppWindow,
  sliding_door: DoorOpen,
  window_grill: Grid3x3,
  other: Package,
}

/** Display-only conversion for the allowed range hint. The server converts authoritatively. */
function fromMm(mm: number, unit: LengthUnit): string {
  return String(Math.round((mm / MM_PER[unit]) * 10) / 10)
}

const size = z.string().trim().regex(/^\d{1,5}(\.\d{1,2})?$/, 'Enter a number like 120 or 120.5')

const schema = z.object({
  product_id: z.string().min(1, 'Choose a product'),
  unit: z.enum(['cm', 'in']),
  width: size,
  height: size,
  quantity: z.number({ error: 'Enter a quantity' }).int().min(1).max(100),
})
type FormValues = z.input<typeof schema>

function rangeError(value: string, unit: LengthUnit, min: number, max: number, what: string) {
  const mm = Number(value) * MM_PER[unit]
  if (Number.isNaN(mm) || (mm >= min - 0.5 && mm <= max + 0.5)) return null
  return `${what} must be ${fromMm(min, unit)}–${fromMm(max, unit)} ${unit}`
}

function Step({ n, title, children }: { n: number; title: string; children: ReactNode }) {
  return (
    <Card>
      <h2 className="mb-4 flex items-center gap-3 text-base font-semibold">
        <span className="bg-brand-gradient grid size-7 place-items-center rounded-full text-sm text-white">{n}</span>
        {title}
      </h2>
      {children}
    </Card>
  )
}

export function NewQuotationPage() {
  const { products } = useLoaderData<typeof newQuotationLoader>()
  const navigate = useNavigate()
  const [error, setError] = useState<string | null>(null)

  const { register, handleSubmit, control, setValue, setError: setFieldError, formState } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { product_id: '', unit: 'cm', width: '', height: '', quantity: 1 },
  })
  const { errors, isSubmitting } = formState
  const productId = useWatch({ control, name: 'product_id' })
  const unit = useWatch({ control, name: 'unit' })
  const quantity = useWatch({ control, name: 'quantity' })
  const width = useWatch({ control, name: 'width' })
  const height = useWatch({ control, name: 'height' })
  const product: CatalogProduct | undefined = products.find((p) => p.id === productId)
  const setQty = (n: number) => setValue('quantity', Math.min(100, Math.max(1, n || 1)), { shouldValidate: true })

  async function onSubmit(values: FormValues) {
    setError(null)
    if (!product) return
    const widthErr = rangeError(values.width, values.unit, product.min_width_mm, product.max_width_mm, 'Width')
    const heightErr = rangeError(values.height, values.unit, product.min_height_mm, product.max_height_mm, 'Height')
    if (widthErr) setFieldError('width', { message: widthErr })
    if (heightErr) setFieldError('height', { message: heightErr })
    if (widthErr || heightErr) return
    try {
      const created = await quotationsApi.create(schema.parse(values))
      toast.success('Your estimate is ready.')
      navigate(`/app/quotations/${created.id}`)
    } catch (err) {
      setError(messageOf(err))
    }
  }

  if (products.length === 0) {
    return (
      <div className="space-y-6">
        <PageHeader title="New quotation" icon={FilePlus2} backTo="/app/quotations" backLabel="My quotations" />
        <Card>
          <EmptyState icon={PackageX} title="No products available right now" text="Please check back later, or contact the shop." />
        </Card>
      </div>
    )
  }

  const range = (min: number, max: number) => `${fromMm(min, unit)}–${fromMm(max, unit)} ${unit}`

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-6 pb-24 sm:pb-0">
      <PageHeader
        title="New quotation"
        description="Choose a product, enter the size, and click Process to get your estimate."
        icon={FilePlus2}
        backTo="/app/quotations"
        backLabel="My quotations"
      />
      <ErrorBanner message={error} />

      <fieldset disabled={isSubmitting} className="space-y-6">
        <Step n={1} title="Choose a product">
          <div role="radiogroup" aria-label="Product" className="grid gap-3 sm:grid-cols-2">
            {products.map((p) => {
              const Icon = CATEGORY_ICON[p.category]
              return (
                <label
                  key={p.id}
                  className="group relative flex cursor-pointer gap-3 rounded-2xl border border-line bg-surface p-4 transition hover:border-line-strong has-checked:border-transparent has-checked:bg-brand-soft has-checked:ring-2 has-checked:ring-ring has-focus-visible:ring-2 has-focus-visible:ring-ring"
                >
                  <input type="radio" value={p.id} className="sr-only" {...register('product_id')} />
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
          {errors.product_id && (
            <p role="alert" className="mt-2 text-sm text-danger">
              {errors.product_id.message}
            </p>
          )}
        </Step>

        <Step n={2} title="Enter the size">
          <div className="space-y-4">
            <div>
              <p className="mb-1.5 text-sm font-medium" id="unit-label">
                Unit
              </p>
              <div role="radiogroup" aria-labelledby="unit-label" className="inline-flex rounded-xl bg-surface-2 p-1">
                {(['cm', 'in'] as const).map((u) => (
                  <label key={u} className={segmentClass}>
                    <input type="radio" value={u} className="sr-only" {...register('unit')} />
                    {u === 'cm' ? 'Centimetres' : 'Inches'}
                  </label>
                ))}
              </div>
            </div>
            <div className="grid gap-4 sm:grid-cols-3">
              <Field
                label={`Width (${unit})`}
                htmlFor="width"
                error={errors.width?.message}
                hint={product ? `Allowed: ${range(product.min_width_mm, product.max_width_mm)}` : 'Choose a product to see the allowed range'}
              >
                <input id="width" inputMode="decimal" placeholder="e.g. 120" className={`${inputClass} tabular-nums`} aria-invalid={!!errors.width} {...register('width')} />
              </Field>
              <Field
                label={`Height (${unit})`}
                htmlFor="height"
                error={errors.height?.message}
                hint={product ? `Allowed: ${range(product.min_height_mm, product.max_height_mm)}` : undefined}
              >
                <input id="height" inputMode="decimal" placeholder="e.g. 100" className={`${inputClass} tabular-nums`} aria-invalid={!!errors.height} {...register('height')} />
              </Field>
              <Field label="Quantity" htmlFor="quantity" error={errors.quantity?.message}>
                <div className="flex items-center gap-2">
                  <Button variant="secondary" icon={Minus} aria-label="One fewer" className="w-11 shrink-0 px-0" onClick={() => setQty((quantity || 1) - 1)} />
                  <input
                    id="quantity"
                    type="number"
                    min={1}
                    max={100}
                    className={`${inputClass} text-center tabular-nums`}
                    aria-invalid={!!errors.quantity}
                    {...register('quantity', { valueAsNumber: true })}
                  />
                  <Button variant="secondary" icon={Plus} aria-label="One more" className="w-11 shrink-0 px-0" onClick={() => setQty((quantity || 0) + 1)} />
                </div>
              </Field>
            </div>
          </div>
        </Step>
      </fieldset>

      {/* Actions: sticky above the phone tab bar, inline on larger screens */}
      <div className="fixed inset-x-0 bottom-16 z-20 border-t border-line bg-surface/95 px-4 py-3 backdrop-blur sm:static sm:border-0 sm:bg-transparent sm:p-0 sm:backdrop-blur-none">
        <div className="mx-auto flex max-w-5xl items-center gap-3 sm:justify-end">
          <p className="min-w-0 flex-1 truncate text-sm text-muted sm:hidden">
            {product ? `${product.name}${width && height ? ` · ${width} × ${height} ${unit}` : ''}` : 'Choose a product'}
          </p>
          <ButtonLink to="/app/quotations" variant="secondary" icon={X} className="max-sm:hidden">
            Cancel
          </ButtonLink>
          <Button type="submit" icon={Calculator} loading={isSubmitting} className="shrink-0">
            {isSubmitting ? 'Processing…' : 'Process'}
          </Button>
        </div>
      </div>
    </form>
  )
}
