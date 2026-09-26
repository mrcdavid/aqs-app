import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { useLoaderData, useRevalidator } from 'react-router'

import { adminApi, type Material } from '../../api/admin'
import { Card, ErrorBanner, PageHeader, StatusBadge } from '../../components/ui/Card'
import {
  buttonClass,
  Field,
  inputClass,
  linkButtonClass,
  secondaryButtonClass,
} from '../../components/ui/Field'
import { messageOf } from '../../lib/errors'
import { formatMoney, MATERIAL_CATEGORY_LABEL, UNIT_LABEL } from '../../lib/format'
import type { materialsLoader } from './loaders'
import { materialSchema, type MaterialForm } from './schemas'
import { useCurrency } from './useCurrency'

const EMPTY: MaterialForm = { code: '', name: '', category: 'glass', unit: 'sqm', unit_price: '' }

export function MaterialsPage() {
  const { materials } = useLoaderData<typeof materialsLoader>()
  const { revalidate } = useRevalidator()
  const currency = useCurrency()
  const [editing, setEditing] = useState<Material | null>(null)
  const [error, setError] = useState<string | null>(null)

  const form = useForm<MaterialForm>({ resolver: zodResolver(materialSchema), defaultValues: EMPTY })
  const { register, handleSubmit, reset, formState } = form
  const { errors, isSubmitting } = formState

  function startEdit(m: Material) {
    setEditing(m)
    setError(null)
    reset({ code: m.code, name: m.name, category: m.category, unit: m.unit, unit_price: m.unit_price })
  }

  function cancelEdit() {
    setEditing(null)
    setError(null)
    reset(EMPTY)
  }

  async function onSubmit(values: MaterialForm) {
    setError(null)
    try {
      const body = materialSchema.parse(values)
      if (editing) await adminApi.updateMaterial(editing.id, body)
      else await adminApi.createMaterial(body)
      cancelEdit()
      revalidate()
    } catch (err) {
      setError(messageOf(err))
    }
  }

  async function toggleActive(m: Material) {
    setError(null)
    try {
      await adminApi.updateMaterial(m.id, { is_active: !m.is_active })
      revalidate()
    } catch (err) {
      setError(messageOf(err))
    }
  }

  return (
    <>
      <PageHeader
        title="Materials"
        description="Glass, aluminum, metal and hardware with their current prices."
      />

      <Card title={editing ? `Edit ${editing.code}` : 'Add material'}>
        <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-4">
          <ErrorBanner message={error} />
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
            <Field label="Code" htmlFor="code" error={errors.code?.message} hint="e.g. GL-6MM">
              <input id="code" className={inputClass} aria-invalid={!!errors.code} {...register('code')} />
            </Field>
            <div className="lg:col-span-2">
              <Field label="Name" htmlFor="name" error={errors.name?.message}>
                <input id="name" className={inputClass} aria-invalid={!!errors.name} {...register('name')} />
              </Field>
            </div>
            <Field label="Category" htmlFor="category">
              <select id="category" className={inputClass} {...register('category')}>
                {Object.entries(MATERIAL_CATEGORY_LABEL).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Priced" htmlFor="unit">
              <select id="unit" className={inputClass} {...register('unit')}>
                {Object.entries(UNIT_LABEL).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </Field>
            <Field label={`Price (${currency})`} htmlFor="unit_price" error={errors.unit_price?.message}>
              <input
                id="unit_price"
                inputMode="decimal"
                className={inputClass}
                aria-invalid={!!errors.unit_price}
                {...register('unit_price')}
              />
            </Field>
          </div>
          <div className="flex gap-2">
            <button type="submit" disabled={isSubmitting} className={buttonClass}>
              {editing ? 'Save changes' : 'Add material'}
            </button>
            {editing && (
              <button type="button" onClick={cancelEdit} className={secondaryButtonClass}>
                Cancel
              </button>
            )}
          </div>
        </form>
      </Card>

      <Card>
        {materials.length === 0 ? (
          <p className="text-muted">No materials yet. Add your first one above.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-brand-100 text-muted">
                <tr>
                  <th className="py-2 pr-4 font-medium">Code</th>
                  <th className="py-2 pr-4 font-medium">Name</th>
                  <th className="py-2 pr-4 font-medium">Category</th>
                  <th className="py-2 pr-4 text-right font-medium">Price</th>
                  <th className="py-2 pr-4 font-medium">Status</th>
                  <th className="py-2 font-medium">
                    <span className="sr-only">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {materials.map((m) => (
                  <tr key={m.id} className="border-b border-brand-50 last:border-0">
                    <td className="py-2 pr-4 font-mono text-xs">{m.code}</td>
                    <td className="py-2 pr-4">{m.name}</td>
                    <td className="py-2 pr-4">{MATERIAL_CATEGORY_LABEL[m.category]}</td>
                    <td className="py-2 pr-4 text-right tabular-nums whitespace-nowrap">
                      {formatMoney(m.unit_price, currency)}{' '}
                      <span className="text-muted">{UNIT_LABEL[m.unit]}</span>
                    </td>
                    <td className="py-2 pr-4">
                      <StatusBadge active={m.is_active} />
                    </td>
                    <td className="py-2 text-right whitespace-nowrap">
                      <button type="button" className={linkButtonClass} onClick={() => startEdit(m)}>
                        Edit
                      </button>
                      <button type="button" className={linkButtonClass} onClick={() => toggleActive(m)}>
                        {m.is_active ? 'Archive' : 'Restore'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </>
  )
}
