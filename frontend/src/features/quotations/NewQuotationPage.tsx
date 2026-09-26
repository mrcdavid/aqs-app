import { zodResolver } from '@hookform/resolvers/zod'
import { Calculator } from 'lucide-react'
import { useState } from 'react'
import { useForm, useWatch } from 'react-hook-form'
import { Link, useLoaderData, useNavigate } from 'react-router'
import { z } from 'zod'

import { quotationsApi, type CatalogProduct, type LengthUnit } from '../../api/quotations'
import { Card, ErrorBanner, PageHeader } from '../../components/ui/Card'
import { buttonClass, Field, inputClass } from '../../components/ui/Field'
import { messageOf } from '../../lib/errors'
import { PRODUCT_CATEGORY_LABEL } from '../../lib/format'
import type { newQuotationLoader } from './loader'

const MM_PER: Record<LengthUnit, number> = { cm: 10, in: 25.4 }

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

export function NewQuotationPage() {
  const { products } = useLoaderData<typeof newQuotationLoader>()
  const navigate = useNavigate()
  const [error, setError] = useState<string | null>(null)

  const { register, handleSubmit, control, setError: setFieldError, formState } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { product_id: '', unit: 'cm', width: '', height: '', quantity: 1 },
  })
  const { errors, isSubmitting } = formState
  const productId = useWatch({ control, name: 'product_id' })
  const unit = useWatch({ control, name: 'unit' })
  const product: CatalogProduct | undefined = products.find((p) => p.id === productId)

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
      navigate(`/app/quotations/${created.id}`)
    } catch (err) {
      setError(messageOf(err))
    }
  }

  if (products.length === 0) {
    return (
      <div className="space-y-6">
        <PageHeader title="New quotation" />
        <Card>
          <p className="text-muted">No products are available right now. Please check back later.</p>
        </Card>
      </div>
    )
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-6">
      <PageHeader title="New quotation" description="Choose a product, enter the size, and click Process." />
      <ErrorBanner message={error} />

      <Card title="1. Choose a product">
        <fieldset>
          <legend className="sr-only">Product</legend>
          <div className="grid gap-3 sm:grid-cols-2">
            {products.map((p) => (
              <label
                key={p.id}
                className="flex cursor-pointer gap-3 rounded-lg border border-brand-100 p-4 has-checked:border-brand-600 has-checked:ring-2 has-checked:ring-brand-100"
              >
                <input type="radio" value={p.id} className="mt-1 accent-brand-600" {...register('product_id')} />
                <span>
                  <span className="block font-medium">{p.name}</span>
                  <span className="block text-sm text-muted">{PRODUCT_CATEGORY_LABEL[p.category]}</span>
                  {p.description && <span className="mt-1 block text-sm">{p.description}</span>}
                </span>
              </label>
            ))}
          </div>
          {errors.product_id && (
            <p role="alert" className="mt-2 text-sm text-red-600">
              {errors.product_id.message}
            </p>
          )}
        </fieldset>
      </Card>

      <Card title="2. Enter the size">
        <div className="space-y-4">
          <fieldset className="flex gap-2">
            <legend className="mb-1 text-sm font-medium">Unit</legend>
            {(['cm', 'in'] as const).map((u) => (
              <label
                key={u}
                className="cursor-pointer rounded-lg border border-brand-100 px-4 py-2 text-sm has-checked:border-brand-600 has-checked:bg-brand-600 has-checked:text-white"
              >
                <input type="radio" value={u} className="sr-only" {...register('unit')} />
                {u === 'cm' ? 'Centimetres' : 'Inches'}
              </label>
            ))}
          </fieldset>
          <div className="grid gap-4 sm:grid-cols-3">
            <Field
              label={`Width (${unit})`}
              htmlFor="width"
              error={errors.width?.message}
              hint={product ? `${fromMm(product.min_width_mm, unit)}–${fromMm(product.max_width_mm, unit)} ${unit}` : undefined}
            >
              <input id="width" inputMode="decimal" className={inputClass} aria-invalid={!!errors.width} {...register('width')} />
            </Field>
            <Field
              label={`Height (${unit})`}
              htmlFor="height"
              error={errors.height?.message}
              hint={product ? `${fromMm(product.min_height_mm, unit)}–${fromMm(product.max_height_mm, unit)} ${unit}` : undefined}
            >
              <input id="height" inputMode="decimal" className={inputClass} aria-invalid={!!errors.height} {...register('height')} />
            </Field>
            <Field label="Quantity" htmlFor="quantity" error={errors.quantity?.message}>
              <input
                id="quantity"
                type="number"
                min={1}
                max={100}
                className={inputClass}
                aria-invalid={!!errors.quantity}
                {...register('quantity', { valueAsNumber: true })}
              />
            </Field>
          </div>
        </div>
      </Card>

      <div className="flex flex-wrap items-center gap-3">
        <button type="submit" disabled={isSubmitting} className={buttonClass}>
          <Calculator className="size-4" aria-hidden />
          {isSubmitting ? 'Processing…' : 'Process'}
        </button>
        <Link to="/app/quotations" className="text-sm text-brand-600 hover:underline">
          Cancel
        </Link>
      </div>
    </form>
  )
}
