import { zodResolver } from '@hookform/resolvers/zod'
import { Package, Pencil, Plus, Save, X } from 'lucide-react'
import { useState } from 'react'
import { useForm, useWatch } from 'react-hook-form'

import { Button } from '../../components/ui/Button'
import { ErrorBanner, SectionLabel } from '../../components/ui/Card'
import { Field, inputClass } from '../../components/ui/Field'
import { Modal } from '../../components/ui/Modal'
import { messageOf } from '../../lib/errors'
import { PRODUCT_CATEGORY_LABEL } from '../../lib/format'
import { productSchema, type ProductForm as ProductFormValues } from './schemas'
import { useCurrency } from './useCurrency'

const SIZE_FIELDS = [
  ['min_width_mm', 'Min width'],
  ['max_width_mm', 'Max width'],
  ['min_height_mm', 'Min height'],
  ['max_height_mm', 'Max height'],
] as const

interface Props {
  open: boolean
  mode: 'new' | 'edit'
  initial: ProductFormValues
  /** Shown in the title when editing, e.g. the product code. */
  code?: string
  onClose: () => void
  onSave: (values: ProductFormValues) => Promise<void>
}

/** Add / edit a product's details in a dialog. Errors from the server stay inside the dialog. */
export function ProductFormModal({ open, mode, initial, code, onClose, onSave }: Props) {
  const [saving, setSaving] = useState(false)
  const isNew = mode === 'new'
  return (
    <Modal
      open={open}
      onClose={onClose}
      size="lg"
      icon={isNew ? Package : Pencil}
      title={isNew ? 'New product' : `Edit product ${code ?? ''}`}
      description={
        isNew
          ? 'After creating it you will add its materials and labour (its price, or a cost guide).'
          : 'Changes apply to new quotations. Existing quotations keep their details.'
      }
      footer={
        <>
          <Button variant="secondary" icon={X} onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" form="product-form" icon={isNew ? Plus : Save} loading={saving}>
            {isNew ? 'Create and add template' : 'Save changes'}
          </Button>
        </>
      }
    >
      <ProductFields
        initial={initial}
        onSubmit={async (values) => {
          setSaving(true)
          try {
            await onSave(values)
          } finally {
            setSaving(false)
          }
        }}
      />
    </Modal>
  )
}

const METHODS = [
  ['per_sqft', 'Per sq ft', 'You set the selling rate (e.g. sliding windows). Glass types and add-ons can add their own rate. Materials are a cost guide.'],
  ['computed', 'From materials', 'Priced from its materials and labour plus the markup in Settings (e.g. grills: whole bars + labour per grill).'],
] as const

function ProductFields({ initial, onSubmit }: { initial: ProductFormValues; onSubmit: (v: ProductFormValues) => Promise<void> }) {
  const [error, setError] = useState<string | null>(null)
  const currency = useCurrency()
  const { register, handleSubmit, formState, control } = useForm<ProductFormValues>({
    resolver: zodResolver(productSchema),
    defaultValues: initial,
  })
  const { errors, isSubmitting } = formState
  const method = useWatch({ control, name: 'pricing_method' })

  return (
    <form
      id="product-form"
      noValidate
      className="space-y-5"
      onSubmit={handleSubmit(async (values) => {
        setError(null)
        try {
          await onSubmit(productSchema.parse(values))
        } catch (err) {
          setError(messageOf(err))
        }
      })}
    >
      <ErrorBanner message={error} />
      <fieldset disabled={isSubmitting} className="space-y-5">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Code" htmlFor="p-code" required error={errors.code?.message} hint="e.g. SW-2PANEL">
            <input id="p-code" autoFocus className={`${inputClass} font-mono uppercase`} aria-invalid={!!errors.code} {...register('code')} />
          </Field>
          <Field label="Category" htmlFor="p-category" required>
            <select id="p-category" className={inputClass} {...register('category')}>
              {Object.entries(PRODUCT_CATEGORY_LABEL).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Name" htmlFor="p-name" required error={errors.name?.message} className="sm:col-span-2">
            <input id="p-name" className={inputClass} aria-invalid={!!errors.name} {...register('name')} />
          </Field>
          <Field
            label="Description (shown to customers)"
            htmlFor="p-description"
            error={errors.description?.message}
            className="sm:col-span-2"
          >
            <textarea id="p-description" rows={2} className={inputClass} {...register('description')} />
          </Field>
        </div>
        <div className="space-y-3">
          <SectionLabel>How it is priced</SectionLabel>
          <div className="grid gap-3 sm:grid-cols-2" role="radiogroup" aria-label="How it is priced">
            {METHODS.map(([value, label, text]) => (
              <label
                key={value}
                className={`flex cursor-pointer gap-3 rounded-xl border p-3 text-sm ${
                  method === value ? 'border-transparent bg-brand-soft ring-2 ring-ring' : 'border-line hover:bg-surface-2'
                }`}
              >
                <input type="radio" value={value} className="mt-0.5 accent-brand" {...register('pricing_method')} />
                <span>
                  <span className="font-medium">{label}</span>
                  <span className="mt-0.5 block text-xs text-muted">{text}</span>
                </span>
              </label>
            ))}
          </div>
          {method === 'per_sqft' && (
            <Field
              label={`Base rate per sq ft (${currency})`}
              htmlFor="p-rate"
              required
              error={errors.rate_per_sqft?.message}
              hint="VAT included. Each glass type or add-on adds its own rate; 0 if the glass type carries the whole rate."
            >
              <input id="p-rate" inputMode="decimal" className={`${inputClass} tabular-nums sm:w-48`} aria-invalid={!!errors.rate_per_sqft} {...register('rate_per_sqft')} />
            </Field>
          )}
        </div>
        <div className="space-y-3">
          <SectionLabel>Allowed size (millimetres)</SectionLabel>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            {SIZE_FIELDS.map(([name, label]) => (
              <Field key={name} label={label} htmlFor={`p-${name}`} required error={errors[name]?.message}>
                <input
                  id={`p-${name}`}
                  type="number"
                  inputMode="numeric"
                  className={`${inputClass} tabular-nums`}
                  aria-invalid={!!errors[name]}
                  {...register(name, { valueAsNumber: true })}
                />
              </Field>
            ))}
          </div>
        </div>
      </fieldset>
    </form>
  )
}
