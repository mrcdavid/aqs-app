import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { useLoaderData, useRevalidator } from 'react-router'

import { adminApi, type LaborRate } from '../../api/admin'
import { Card, ErrorBanner, PageHeader, StatusBadge } from '../../components/ui/Card'
import {
  buttonClass,
  Field,
  inputClass,
  linkButtonClass,
  secondaryButtonClass,
} from '../../components/ui/Field'
import { messageOf } from '../../lib/errors'
import { formatMoney, UNIT_LABEL } from '../../lib/format'
import type { laborRatesLoader } from './loaders'
import { laborRateSchema, type LaborRateForm } from './schemas'
import { useCurrency } from './useCurrency'

const EMPTY: LaborRateForm = { code: '', name: '', unit: 'sqm', rate: '' }

export function LaborRatesPage() {
  const { laborRates } = useLoaderData<typeof laborRatesLoader>()
  const { revalidate } = useRevalidator()
  const currency = useCurrency()
  const [editing, setEditing] = useState<LaborRate | null>(null)
  const [error, setError] = useState<string | null>(null)

  const { register, handleSubmit, reset, formState } = useForm<LaborRateForm>({
    resolver: zodResolver(laborRateSchema),
    defaultValues: EMPTY,
  })
  const { errors, isSubmitting } = formState

  function startEdit(r: LaborRate) {
    setEditing(r)
    setError(null)
    reset({ code: r.code, name: r.name, unit: r.unit, rate: r.rate })
  }

  function cancelEdit() {
    setEditing(null)
    setError(null)
    reset(EMPTY)
  }

  async function onSubmit(values: LaborRateForm) {
    setError(null)
    try {
      const body = laborRateSchema.parse(values)
      if (editing) await adminApi.updateLaborRate(editing.id, body)
      else await adminApi.createLaborRate(body)
      cancelEdit()
      revalidate()
    } catch (err) {
      setError(messageOf(err))
    }
  }

  async function toggleActive(r: LaborRate) {
    setError(null)
    try {
      await adminApi.updateLaborRate(r.id, { is_active: !r.is_active })
      revalidate()
    } catch (err) {
      setError(messageOf(err))
    }
  }

  return (
    <>
      <PageHeader
        title="Labour rates"
        description="Fabrication and installation charges, per m², per metre, or per piece."
      />

      <Card title={editing ? `Edit ${editing.code}` : 'Add labour rate'}>
        <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-4">
          <ErrorBanner message={error} />
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Field label="Code" htmlFor="code" error={errors.code?.message} hint="e.g. INSTALL">
              <input id="code" className={inputClass} aria-invalid={!!errors.code} {...register('code')} />
            </Field>
            <Field label="Name" htmlFor="name" error={errors.name?.message}>
              <input id="name" className={inputClass} aria-invalid={!!errors.name} {...register('name')} />
            </Field>
            <Field label="Charged" htmlFor="unit">
              <select id="unit" className={inputClass} {...register('unit')}>
                {Object.entries(UNIT_LABEL).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </Field>
            <Field label={`Rate (${currency})`} htmlFor="rate" error={errors.rate?.message}>
              <input
                id="rate"
                inputMode="decimal"
                className={inputClass}
                aria-invalid={!!errors.rate}
                {...register('rate')}
              />
            </Field>
          </div>
          <div className="flex gap-2">
            <button type="submit" disabled={isSubmitting} className={buttonClass}>
              {editing ? 'Save changes' : 'Add labour rate'}
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
        {laborRates.length === 0 ? (
          <p className="text-muted">No labour rates yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-brand-100 text-muted">
                <tr>
                  <th className="py-2 pr-4 font-medium">Code</th>
                  <th className="py-2 pr-4 font-medium">Name</th>
                  <th className="py-2 pr-4 text-right font-medium">Rate</th>
                  <th className="py-2 pr-4 font-medium">Status</th>
                  <th className="py-2 font-medium">
                    <span className="sr-only">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {laborRates.map((r) => (
                  <tr key={r.id} className="border-b border-brand-50 last:border-0">
                    <td className="py-2 pr-4 font-mono text-xs">{r.code}</td>
                    <td className="py-2 pr-4">{r.name}</td>
                    <td className="py-2 pr-4 text-right tabular-nums whitespace-nowrap">
                      {formatMoney(r.rate, currency)}{' '}
                      <span className="text-muted">{UNIT_LABEL[r.unit]}</span>
                    </td>
                    <td className="py-2 pr-4">
                      <StatusBadge active={r.is_active} />
                    </td>
                    <td className="py-2 text-right whitespace-nowrap">
                      <button type="button" className={linkButtonClass} onClick={() => startEdit(r)}>
                        Edit
                      </button>
                      <button type="button" className={linkButtonClass} onClick={() => toggleActive(r)}>
                        {r.is_active ? 'Archive' : 'Restore'}
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
