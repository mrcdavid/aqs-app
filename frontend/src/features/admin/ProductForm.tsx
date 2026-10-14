import { zodResolver } from '@hookform/resolvers/zod'
import { Package, Pencil, Plus, Save, X } from 'lucide-react'
import { useState } from 'react'
import { useForm } from 'react-hook-form'

import { Button } from '../../components/ui/Button'
import { ErrorBanner, SectionLabel } from '../../components/ui/Card'
import { Field, inputClass } from '../../components/ui/Field'
import { Modal } from '../../components/ui/Modal'
import { messageOf } from '../../lib/errors'
import { PRODUCT_CATEGORY_LABEL } from '../../lib/format'
import { productSchema, type ProductForm as ProductFormValues } from './schemas'

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
          ? 'After creating it you will add its price template (materials and labour).'
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

function ProductFields({ initial, onSubmit }: { initial: ProductFormValues; onSubmit: (v: ProductFormValues) => Promise<void> }) {
  const [error, setError] = useState<string | null>(null)
  const { register, handleSubmit, formState } = useForm<ProductFormValues>({
    resolver: zodResolver(productSchema),
    defaultValues: initial,
  })
  const { errors, isSubmitting } = formState

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
