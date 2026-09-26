import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { useRevalidator, useRouteLoaderData } from 'react-router'

import { adminApi, type PricingSettings } from '../../api/admin'
import { Card, ErrorBanner, PageHeader } from '../../components/ui/Card'
import { buttonClass, Field, inputClass } from '../../components/ui/Field'
import { messageOf } from '../../lib/errors'
import { settingsSchema, type SettingsForm } from './schemas'

export function PricingSettingsPage() {
  const { settings } = useRouteLoaderData('admin') as { settings: PricingSettings }
  const { revalidate } = useRevalidator()
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)

  const { register, handleSubmit, formState } = useForm<SettingsForm>({
    resolver: zodResolver(settingsSchema),
    defaultValues: {
      markup_percent: settings.markup_percent,
      vat_percent: settings.vat_percent,
      currency: settings.currency,
      quote_validity_days: settings.quote_validity_days,
      business_name: settings.business_name,
      business_address: settings.business_address,
      business_contact: settings.business_contact,
      quote_terms: settings.quote_terms,
    },
  })
  const { errors, isSubmitting } = formState

  async function onSubmit(values: SettingsForm) {
    setError(null)
    setSaved(false)
    try {
      await adminApi.updatePricingSettings(settingsSchema.parse(values))
      setSaved(true)
      revalidate()
    } catch (err) {
      setError(messageOf(err))
    }
  }

  return (
    <>
      <PageHeader
        title="Settings"
        description="Pricing applied to new quotations, and the business details printed on PDFs."
      />
      <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-6">
          <ErrorBanner message={error} />
          {saved && (
            <p role="status" className="rounded-lg bg-green-50 p-3 text-sm text-green-700">
              Saved. New quotations and approvals use these settings.
            </p>
          )}
      <Card title="Pricing">
        <div className="max-w-md space-y-4">
          <Field label="Markup (%)" htmlFor="markup" error={errors.markup_percent?.message}>
            <input id="markup" inputMode="decimal" className={inputClass} {...register('markup_percent')} />
          </Field>
          <Field label="VAT (%)" htmlFor="vat" error={errors.vat_percent?.message}>
            <input id="vat" inputMode="decimal" className={inputClass} {...register('vat_percent')} />
          </Field>
          <Field label="Currency" htmlFor="currency" error={errors.currency?.message}>
            <input id="currency" className={inputClass} maxLength={3} {...register('currency')} />
          </Field>
          <Field
            label="Quotation valid for (days)"
            htmlFor="validity"
            error={errors.quote_validity_days?.message}
          >
            <input
              id="validity"
              type="number"
              min={1}
              max={365}
              className={inputClass}
              {...register('quote_validity_days', { valueAsNumber: true })}
            />
          </Field>
        </div>
      </Card>
      <Card title="Business details on PDFs">
        <div className="max-w-xl space-y-4">
          <Field label="Business name" htmlFor="b-name" error={errors.business_name?.message}>
            <input id="b-name" className={inputClass} {...register('business_name')} />
          </Field>
          <Field label="Address" htmlFor="b-address" error={errors.business_address?.message}>
            <input id="b-address" className={inputClass} {...register('business_address')} />
          </Field>
          <Field
            label="Contact"
            htmlFor="b-contact"
            hint="e.g. 0917 123 4567 · sales@example.com"
            error={errors.business_contact?.message}
          >
            <input id="b-contact" className={inputClass} {...register('business_contact')} />
          </Field>
          <Field label="Terms and conditions" htmlFor="b-terms" error={errors.quote_terms?.message}>
            <textarea id="b-terms" rows={5} className={inputClass} {...register('quote_terms')} />
          </Field>
        </div>
      </Card>
      <button type="submit" disabled={isSubmitting} className={buttonClass}>
        Save settings
      </button>
      </form>
    </>
  )
}
