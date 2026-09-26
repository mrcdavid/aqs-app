import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'

import { ErrorBanner } from '../../components/ui/Card'
import { buttonClass, Field, inputClass, secondaryButtonClass } from '../../components/ui/Field'
import { PRODUCT_CATEGORY_LABEL } from '../../lib/format'
import { productSchema, type ProductForm as ProductFormValues } from './schemas'

interface Props {
  initial: ProductFormValues
  submitLabel: string
  error: string | null
  onSubmit: (values: ProductFormValues) => Promise<void>
  onCancel?: () => void
}

const SIZE_FIELDS = [
  ['min_width_mm', 'Min width (mm)'],
  ['max_width_mm', 'Max width (mm)'],
  ['min_height_mm', 'Min height (mm)'],
  ['max_height_mm', 'Max height (mm)'],
] as const

export function ProductForm({ initial, submitLabel, error, onSubmit, onCancel }: Props) {
  const { register, handleSubmit, formState } = useForm<ProductFormValues>({
    resolver: zodResolver(productSchema),
    defaultValues: initial,
  })
  const { errors, isSubmitting } = formState

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-4">
      <ErrorBanner message={error} />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Field label="Code" htmlFor="p-code" error={errors.code?.message} hint="e.g. SW-2PANEL">
          <input id="p-code" className={inputClass} aria-invalid={!!errors.code} {...register('code')} />
        </Field>
        <div className="lg:col-span-2">
          <Field label="Name" htmlFor="p-name" error={errors.name?.message}>
            <input id="p-name" className={inputClass} aria-invalid={!!errors.name} {...register('name')} />
          </Field>
        </div>
        <Field label="Category" htmlFor="p-category">
          <select id="p-category" className={inputClass} {...register('category')}>
            {Object.entries(PRODUCT_CATEGORY_LABEL).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </Field>
        {SIZE_FIELDS.map(([name, label]) => (
          <Field key={name} label={label} htmlFor={`p-${name}`} error={errors[name]?.message}>
            <input
              id={`p-${name}`}
              type="number"
              inputMode="numeric"
              className={inputClass}
              aria-invalid={!!errors[name]}
              {...register(name, { valueAsNumber: true })}
            />
          </Field>
        ))}
        <div className="sm:col-span-2 lg:col-span-4">
          <Field
            label="Description (shown to customers)"
            htmlFor="p-description"
            error={errors.description?.message}
          >
            <textarea id="p-description" rows={2} className={inputClass} {...register('description')} />
          </Field>
        </div>
      </div>
      <div className="flex gap-2">
        <button type="submit" disabled={isSubmitting} className={buttonClass}>
          {submitLabel}
        </button>
        {onCancel && (
          <button type="button" onClick={onCancel} className={secondaryButtonClass}>
            Cancel
          </button>
        )}
      </div>
    </form>
  )
}
